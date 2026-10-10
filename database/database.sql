CREATE TABLE sample_entity_status(
    id		                        SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(enumerator)
);

INSERT INTO sample_entity_status (enumerator) VALUES
('created'),
('pending'),
('success'),
('failed');

CREATE TABLE sample_entity(
    id                              SERIAL PRIMARY KEY,
    sample_entity_key               CHAR(36) NOT NULL,
    status_id                       INTEGER NOT NULL REFERENCES sample_entity_status(id),
    sample_entity_data              JSONB NOT NULL,
    name                            VARCHAR(255) NOT NULL,
    email                           VARCHAR(255) NOT NULL,
    document_number                 CHAR(14) NOT NULL,
    birthdate                       DATE NOT NULL,
    counter                         INTEGER NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(sample_entity_key),
    UNIQUE(document_number),
    UNIQUE(email)
);

CREATE TABLE sample_entity_status_event(
    id                              SERIAL PRIMARY KEY,
    sample_entity_id                INTEGER NOT NULL REFERENCES sample_entity(id),
    status_id                       INTEGER NOT NULL REFERENCES sample_entity_status(id),
    event_datetime                  TIMESTAMP NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW())
);

-- --------------------------------------------------------------------
-- Nucleo do banco (customer, account, transaction, ledger_entry)
-- --------------------------------------------------------------------
-- Segue o diagrama do RFC. As rotas que usam estas tabelas sao as de
-- cliente, conta, deposito, transferencia, pagamento e extrato.

CREATE TABLE customer(
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_number                 CHAR(14) NOT NULL,
    name                            VARCHAR(255) NOT NULL,
    nationality                     VARCHAR(100) NOT NULL,
    email                           VARCHAR(255) NOT NULL,
    birth_date                      DATE NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    UNIQUE(document_number)
);

CREATE TABLE account(
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id                     UUID NOT NULL REFERENCES customer(id),
    balance                         NUMERIC(15,2) NOT NULL DEFAULT 0 CHECK (balance >= 0),
    status                          VARCHAR(20) NOT NULL DEFAULT 'ATIVA'
                                        CHECK (status IN ('ATIVA', 'SUSPENSA', 'ENCERRADA')),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    UNIQUE(customer_id)
);

CREATE TABLE transaction(
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type                            VARCHAR(30) NOT NULL
                                        CHECK (type IN ('DEPOSIT', 'TRANSFER', 'FEE', 'PAYMENT',
                                                        'BOX_RETENTION', 'BOX_RELEASE', 'BOX_WITHDRAWAL')),
    -- A conta dona da operacao: a de origem na TRANSFER e no PAYMENT, a
    -- que recebe no DEPOSIT, a que paga na FEE, a dona da caixinha nas
    -- BOX_*. E nela que a idempotency_key vale.
    account_out_id                  UUID NOT NULL REFERENCES account(id),
    -- Preenchida so na TRANSFER: a conta de destino.
    account_in_id                   UUID REFERENCES account(id),
    value                           NUMERIC(15,2) NOT NULL CHECK (value > 0),
    idempotency_key                 VARCHAR(255) NOT NULL,
    request_hash                    CHAR(64) NOT NULL,
    -- Na FEE, a transferencia que gerou a tarifa. O UNIQUE garante uma
    -- tarifa por transferencia, no maximo.
    related_transaction_id          UUID REFERENCES transaction(id),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    UNIQUE(account_out_id, idempotency_key),
    UNIQUE(related_transaction_id)
);

CREATE TABLE ledger_entry(
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id                  UUID NOT NULL REFERENCES transaction(id),
    account_id                      UUID NOT NULL REFERENCES account(id),
    direction                       VARCHAR(10) NOT NULL CHECK (direction IN ('DEBITO', 'CREDITO')),
    value                           NUMERIC(15,2) NOT NULL CHECK (value > 0),
    balance_after                   NUMERIC(15,2) NOT NULL,
    -- clock_timestamp(), e nao NOW(): o NOW() e o inicio da transacao de
    -- banco, igual para todos os lancamentos dela. A transferencia grava
    -- o debito e a tarifa na mesma transacao, e o extrato precisa saber
    -- qual veio primeiro.
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT(clock_timestamp())
);

-- Duas consultas leem os lancamentos de UMA conta por periodo: o extrato
-- e a renda do dia da caixinha. As duas usam este indice.
CREATE INDEX ledger_entry_account_created_at ON ledger_entry(account_id, created_at);


-- --------------------------------------------------------------------
-- Caixinha de Equilibrio
-- --------------------------------------------------------------------

CREATE TABLE smoothing_box(
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    box_key                         UUID NOT NULL DEFAULT gen_random_uuid(),
    account_id                      UUID NOT NULL REFERENCES account(id),
    balance                         NUMERIC(15,2) NOT NULL DEFAULT 0 CHECK (balance >= 0),
    retention_pct                   SMALLINT NOT NULL CHECK (retention_pct BETWEEN 20 AND 80),
    status                          VARCHAR(10) NOT NULL DEFAULT 'ACTIVE'
                                        CHECK (status IN ('ACTIVE', 'PAUSED')),
    activated_on                    DATE NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    UNIQUE(box_key),
    UNIQUE(account_id)
);

CREATE TABLE box_entry(
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    box_id                          UUID NOT NULL REFERENCES smoothing_box(id),
    transaction_id                  UUID NOT NULL REFERENCES transaction(id),
    direction                       VARCHAR(10) NOT NULL CHECK (direction IN ('DEBITO', 'CREDITO')),
    origin                          VARCHAR(15) NOT NULL
                                        CHECK (origin IN ('RETENTION', 'RELEASE', 'WITHDRAWAL')),
    value                           NUMERIC(15,2) NOT NULL CHECK (value > 0),
    balance_after                   NUMERIC(15,2) NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    UNIQUE(transaction_id)
);

CREATE TABLE daily_closing(
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    closing_key                     UUID NOT NULL DEFAULT gen_random_uuid(),
    box_id                          UUID NOT NULL REFERENCES smoothing_box(id),
    reference_date                  DATE NOT NULL,
    income                          NUMERIC(15,2) NOT NULL,
    baseline                        NUMERIC(15,2) NOT NULL,
    window_days                     SMALLINT NOT NULL,
    lower_bound                     NUMERIC(15,2) NOT NULL,
    upper_bound                     NUMERIC(15,2) NOT NULL,
    band                            VARCHAR(10) NOT NULL
                                        CHECK (band IN ('WARMUP', 'ABOVE', 'NEUTRAL', 'BELOW', 'PAUSED')),
    amount_calculated               NUMERIC(15,2) NOT NULL,
    amount_moved                    NUMERIC(15,2) NOT NULL CHECK (amount_moved >= 0),
    transaction_id                  UUID REFERENCES transaction(id),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    UNIQUE(closing_key),
    -- Um fechamento por caixinha por dia: a ultima linha de defesa da
    -- idempotencia do fechamento (o RFC explica a primeira, que e a trava).
    UNIQUE(box_id, reference_date)
);
