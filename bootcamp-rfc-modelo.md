# RFC — o banco dos entregadores de aplicativos

| | |
|---|---|
| **Time** | Fernando Mendes · Victor Kazunori · Matheus Reis |
| **Data** | 10/10/2026 |
| **Versão** | 3 |

## Contextualização


### Entendendo o problema

O banco deve fornecer os produtos bancários básicos: cadastro de cliente com conta vinculada, consulta de saldo, depósito, realizar e receber transferências (cinco isentas por mês; a partir da sexta, tarifa de 1% do valor com mínimo de R$ 1,00), realizar pagamentos e consultar o extrato paginado de transações. Além disso, o banco implementa a solução da Caixinha do Equilíbrio. O entregador recebe por dia, e o valor de cada dia é imprevisível: um sábado de chuva vale o triplo de uma terça parada. A Caixinha de Equilíbrio dá previsibilidade a essa renda: fecha cada dia, compara a renda do dia com a média recente do próprio cliente, guarda parte do que passou da média e, nos dias abaixo dela, devolve o suficiente para chegar a um piso. Quem chama o serviço são outros sistemas, identificados por um token interno.

A solução precisa sustentar as seguintes garantias:
- **Cadastro único**: um cliente só poderá ser cadastrado uma única vez, identificado por seus dados cadastrais, e terá uma única conta ativa associada.
- **Garantia financeira**: uma transação só poderá ser concluída quando houver saldo suficiente na conta de origem e a conta de destino, quando aplicável, for válida e estiver ativa. A operação deverá ser atômica, garantindo que seus lançamentos ocorram integralmente ou não ocorram.
- **Ciclo de vida da conta**: uma conta poderá assumir os status ATIVA, SUSPENSA ou ENCERRADA, respeitando as regras de transição definidas pelo sistema.
- **Tarifa junto com a transferência**: quando há tarifa, ela é cobrada no mesmo commit da transferência; não existe transferência que passa com a tarifa ficando devendo, e o saldo da origem precisa cobrir os dois. A franquia mensal é contada com a conta travada: dois pedidos simultâneos nunca usam a mesma isenção.
- **Rastreabilidade financeira**: toda movimentação concluída deverá possuir registro suficiente para permitir a consulta e reconstrução do histórico da operação.
- **Consistência do saldo**: operações concorrentes sobre uma mesma conta devem ser serializadas ou controladas de forma que o saldo nunca seja comprometido por operações além dos recursos disponíveis.
- **Conservação do dinheiro:** o dinheiro só anda entre a conta e a caixinha do mesmo cliente; toda retenção, liberação e resgate é uma `transaction` do time, com lançamento na conta e na caixinha na mesma transação de banco. Se falhar, o saldo some de um lado sem aparecer no outro.
- **Um fechamento por dia:** cada dia de cada caixinha é fechado uma vez só; repetir o fechamento não retém nem libera de novo. Se falhar, o agendador que reenvia o pedido retém duas vezes.
- **Regra reproduzível:** a média, o piso e o teto usados em cada fechamento ficam gravados; o mesmo dia, refeito no papel, dá o mesmo valor. Se falhar, não há como explicar ao cliente por que o banco reteve R$ 50.
- **Nunca negativo:** a retenção não deixa a conta negativa e a liberação não passa do saldo da caixinha, mesmo com uma transferência do cliente chegando no mesmo instante.
- **Liquidez:** o cliente resgata o saldo da caixinha quando quiser; o dinheiro é dele.
- **Idempotência**: uma mesma solicitação de operação financeira não poderá produzir mais de uma transação efetiva, mesmo que a requisição seja reenviada.

A receita do banco vem de duas fontes: a tarifa das transferências além da franquia mensal e o *float*: o saldo somado das caixinhas fica parado em média vários dias e é aplicado pela tesouraria em ativos de liquidez diária.

Fora do escopo desta entrega: a aplicação financeira do saldo (tesouraria), rendimento repassado ao cliente, o agendador em si, encerramento da caixinha, seguro de moto/vida/trabalho.

### Explicando a solução de forma macro

A solução é composta por sete entidades principais — `customer`, `account`, `transaction`, `ledger_entry`, `smoothing_box`, `box_entry` e `daily_closing`. O cliente possui uma conta bancária, que mantém seu saldo e ciclo de vida, e pode possuir uma `smoothing_box` (caixinha), que mantém um saldo próprio e um percentual de retenção definido pelo cliente.

Cada operação financeira é registrada como uma `transaction` e gera um ou mais lançamentos sobre as contas e, quando aplicável, sobre a caixinha. Uma transferência interna gera um débito e um crédito. As cinco primeiras transferências que uma conta faz em cada mês (no fuso de São Paulo) são isentas; a partir da sexta, a tarifa é 1% do valor, arredondado ao centavo, com mínimo de R$ 1,00. Quando há tarifa, ela é uma segunda `transaction`, do tipo `FEE`, ligada à transferência por `related_transaction_id`, com o débito na conta de origem, gravada no mesmo commit. Um depósito gera apenas o crédito, e um pagamento externo apenas o débito na conta do cliente. O extrato lê os lançamentos (`ledger_entry`) da conta, do mais novo para o mais antigo, em páginas de `limit` linhas. As operações são processadas de forma atômica, com controle de concorrência sobre os saldos, e utilizam uma chave de idempotência para impedir que uma mesma solicitação produza mais de uma operação financeira. Restrições de unicidade garantem o cadastro único, enquanto os lançamentos preservam o histórico necessário para rastrear as movimentações.

Uma vez por dia, um agendador solicita o fechamento do dia anterior da caixinha. A API trava a conta e a caixinha, calcula a renda do dia a partir dos créditos registrados no `ledger_entry`, considera os últimos 28 fechamentos realizados, calcula a média e classifica o dia como `ACIMA`, `NEUTRO` ou `ABAIXO`. Quando o resultado está acima da média, parte do excedente é transferida da conta para a caixinha; quando está abaixo, a caixinha libera para a conta o valor necessário para atingir o piso definido pela regra.

Esses movimentos reutilizam as entidades `transaction` e `ledger_entry` da solução bancária. Cada fechamento é registrado em `daily_closing`, armazenando os parâmetros utilizados no cálculo e o valor efetivamente movimentado. A restrição `UNIQUE(box_id, reference_date)` garante que cada caixinha possua no máximo um fechamento para cada dia.


Alternativas descartadas:

- **Calcular o saldo apenas a partir dos lançamentos:** descartado porque cada consulta de saldo exigiria a agregação do histórico e aumentaria o custo das consultas; seria uma alternativa interessante em um sistema com menor frequência de consulta ou forte necessidade de reconstrução do saldo.
- **Modelar transferência como dois registros independentes:** descartado porque permitiria que débito e crédito fossem tratados separadamente; a transação única garante que os dois lados sejam confirmados ou revertidos juntos.
- **Permitir reprocessamento de uma mesma requisição:** descartado porque uma falha de comunicação poderia levar o sistema externo a reenviar a operação e movimentar o mesmo valor mais de uma vez; seria aceitável apenas para operações explicitamente tolerantes a duplicidade.
- **Controlar saldo exclusivamente na aplicação:** descartado porque múltiplas requisições concorrentes poderiam validar o mesmo saldo antes de atualizá-lo; seria uma alternativa viável apenas com outro mecanismo de serialização ou controle de concorrência.
- **Reter a cada crédito, em tempo real** — descartada porque a média do dia só se conhece quando o dia
  acaba, e cada crédito disputaria a trava da conta com as transferências. Ganharia se os clientes
  gastassem quase tudo antes do fim do dia, a ponto de o fechamento não achar saldo para reter.
- **Recalcular a média direto do ledger a cada fechamento** — descartada porque relê 28 dias de
  lançamentos a cada pedido e o resultado muda se um crédito antigo for estornado; o dia já fechado
  deixaria de bater. Ganharia se a regra mudasse e fosse preciso recalcular o histórico.
- **Faixas por desvio-padrão em vez de ±10% da média** — descartada porque com 14 a 28 dias o desvio é
  instável e difícil de explicar ao cliente. Ganharia com histórico longo e renda mais regular.
- **Tarifa fixa em toda transferência:** descartada porque pesa demais em quem faz transferências pequenas, que é o caso do entregador: R$ 2,00 sobre R$ 20,00 é 10%. A franquia mensal cobre o uso do dia a dia sem custo, e o percentual cobra mais de quem movimenta mais. Ganharia se o banco precisasse de uma tarifa que o cliente calcula de cabeça.
- **Percentual sem mínimo:** descartado porque 1% de uma transferência de R$ 5,00 seria R$ 0,05, menos que o custo de processá-la. Ganharia se o banco quisesse incentivar transferências pequenas também fora da franquia.
- **Franquia guardada num contador na `account`:** descartada porque o contador precisaria ser zerado todo mês (um agendador a mais) e poderia divergir das transferências gravadas. Contar as `TRANSFER` do mês direto na tabela usa o que já está gravado e não tem o que dessincronizar. Ganharia com contas de volume muito alto, em que a contagem pesasse.
- **Tarifa como campo `fee` da própria transferência:** descartada porque o extrato mostraria uma linha com dois valores, e a "transferência de R$ 200" passaria a debitar R$ 202; com a `transaction` `FEE` separada, cada linha do extrato tem um valor e um motivo, e a receita de tarifas é uma soma simples por tipo. Ganharia se o banco quisesse exatamente uma linha por pedido do cliente.
- **Creditar a tarifa numa conta de receita do banco:** descartada porque toda transferência do banco travaria a mesma linha de `account` com `FOR UPDATE`, e o banco inteiro passaria a andar em fila por ela; além disso, `account` exige um `customer`. A tarifa sai da conta do cliente para fora das contas de clientes, como um pagamento. Ganharia se fosse preciso conciliar a receita pelo saldo de uma conta.
- **Extrato paginado por cursor (`created_at`, `id`) em vez de `page`:** descartada para manter o mesmo envelope `data`/`limit`/`page`/`is_last_page` dos fechamentos da caixinha. Ganharia com extratos de milhares de linhas, em que o `OFFSET` das últimas páginas fica caro.
- **Caixinha como segunda `account` do cliente** — descartada porque quebra a garantia de uma única
  conta ativa por cliente e deixaria a caixinha receber transferências de terceiros. Ganharia se o
  banco tivesse vários produtos com saldo separado.

## Implementação

### Rotas

| Método | Caminho | O que faz | Entrada (campos que importam) | Saídas (status e quando) |
|---|---|---|---|---|
| `GET` | `/` | Diz qual serviço é este. <br> Aberta, sem token | - | `200`|
| `GET` | `/health_check` | Diz se o serviço está de pé. <br> Aberta, sem token | - | `204`|
| `POST` | `/customers` | Cadastra o cliente e sua conta, no mesmo commit. A conta nasce `ATIVA` e com saldo zero. <br> Repetir não cria outro cliente: `UNIQUE(document_number)` | `name`, `nationality`, `document_number` (CPF `000.000.000-00`), `email`, `birth_date` (`AAAA-MM-DD`) | `201` com `customer_id` e `account_id`; `400` `EB000001` corpo fora do formato, incluindo CPF ausente ou fora da máscara e data de nascimento inexistente ou futura; `409` `EB001004` CPF já cadastrado; `422` `EB001003` CPF com dígitos verificadores que não batem|
| `GET` | `/customers/` <br> `{customer_id}` | Devolve um cliente, com `document_number` e `account_id` | `customer_id` no caminho | `200`; `404` `EB001001` cliente inexistente |
| `GET` | `/accounts/` <br> `{account_id}` | Consulta o saldo e o status da conta | `account_id` no caminho | `200` com `balance` e `status`; `404` `EB001002` conta inexistente |
| `PATCH` | `/accounts/` <br> `{account_id}` | Muda o status da conta: `ATIVA` ⇄ `SUSPENSA`, e qualquer uma delas → `ENCERRADA`, que é final | `status` | `200`; `400` `EB000001` status desconhecido; `404` `EB001002`; `409` `EB001010` transição não permitida (inclui pedir o status atual e sair de `ENCERRADA`); `422` `EB001011` encerrar com saldo na conta ou na caixinha |
| `POST` | `/accounts/{account_id}/` <br> `deposits` | Credita dinheiro que chega de fora do banco. <br> Idempotente: `UNIQUE(account_out_id, idempotency_key)` | `value` (texto, > 0, até duas casas: `"50.00"`) e `idempotency_key` no corpo | `201` com `transaction_id` e `balance_after` (reenvio com a mesma chave devolve o `201` original); `400` `EB000001` valor inválido; `404` `EB001002` conta inexistente; `409` `EB001006` conta não está `ATIVA`; `409` `EB001007` chave reutilizada com outro payload |
| `POST` | `/accounts/{account_id_out}/` <br> `transfers` | Realiza uma transferência para outra conta do banco. **Tarifa**: as 5 primeiras do mês são isentas; depois, 1% do valor com mínimo de R$ 1,00, cobrado da origem no mesmo commit. <br> Idempotente: `UNIQUE(account_out_id, idempotency_key)` | `account_id_out` no caminho, `account_id_in`, `value` e `idempotency_key` no corpo | `201` com `transaction_id`, `fee` (`"0.00"` quando isenta), `fee_transaction_id` (nulo quando isenta), `total_debited` e `balance_after` (reenvio com a mesma chave devolve o `201` original); `400` `EB000001` valor inválido; `404` `EB001002` conta de origem inexistente; `404` `EB001005` conta de destino inexistente; `409` `EB001006` alguma das contas não está `ATIVA`; `409` `EB001007` chave reutilizada com outro payload; `422` `EB001008` saldo não cobre valor + tarifa; `422` `EB001009` origem e destino são a mesma conta |
| `POST` | `/accounts/{account_id_out}/` <br> `payments` | Realiza um pagamento para fora do banco. Sem tarifa. <br> Idempotente: `UNIQUE(account_out_id, idempotency_key)` | `account_id_out` no caminho, `value` e `idempotency_key` no corpo | `201` com `transaction_id` e `balance_after` (reenvio com a mesma chave devolve o `201` original); `400` `EB000001` valor inválido; `404` `EB001002` conta de origem inexistente; `409` `EB001006` conta não está `ATIVA`; `409` `EB001007` chave reutilizada com outro payload; `422` `EB001008` saldo insuficiente |
| `GET` | `/accounts/{account_id}/` <br> `transactions` | Extrato **paginado** da conta, do lançamento mais novo para o mais antigo | `account_id` no caminho; `start_date`, `end_date` (opcionais, dias de São Paulo), `limit` (padrão 10, até 100), `page` (padrão 0) | `200` com `data`, `limit`, `page` e `is_last_page`; `400` `EB000001` parâmetro fora do formato ou desconhecido; `400` `EB000010` `start_date` posterior a `end_date`; `404` `EB001002` conta inexistente; `409` `EB001006` conta não está `ATIVA` |
| `POST` | `/accounts/{account_id}/smoothing-box` | Ativa a caixinha da conta. Repetir não cria outra: `UNIQUE(account_id)` | `retention_pct` (inteiro de 20 a 80, padrão 50) | `201` com `box_key`, `status`, `activated_on`; `400 EB000001` corpo fora do formato ou `retention_pct` fora de 20–80; `404 EB001002` conta inexistente; `409 EB002002` a conta já tem caixinha; `409 EB001006` conta não está `ATIVA` |
| `GET` | `/accounts/{account_id}/smoothing-box` | Devolve saldo, percentual, status, a média atual, o piso, o teto e o último dia fechado | `account_id` no caminho | `200`; `404 EB001002` conta inexistente; `404 EB002001` conta sem caixinha |
| `PATCH` | `/accounts/{account_id}/smoothing-box` | Muda o percentual e/ou pausa e retoma (`ACTIVE` ↔ `PAUSED`). Vale a partir do próximo fechamento | `retention_pct`, `status` | `200`; `400 EB000001`; `404 EB001002`; `404 EB002001`; `409 EB002006` pedido para o status em que ela já está |
| `POST` | `/accounts/{account_id}/smoothing-box/closings` | Fecha um dia: calcula a faixa e retém ou libera. **Idempotente** por `UNIQUE(box_id, reference_date)`: repetir devolve o mesmo fechamento, sem mover dinheiro | `reference_date` (`AAAA-MM-DD`) | `201` fechamento novo; `200` o dia já estava fechado (mesmo corpo da primeira vez); `400 EB000001`; `404 EB001002`; `404 EB002001`; `409 EB001006` conta não está `ATIVA`; `409 EB002003` o dia anterior não foi fechado, com `next_reference_date` no corpo; `422 EB002004` `reference_date` é hoje, futuro ou anterior a `activated_on` |
| `GET` | `/accounts/{account_id}/smoothing-box/closings` | Histórico de fechamentos: renda, média, faixa, valor calculado e valor movido de cada dia | `start_date`, `end_date` (opcionais), `limit`, `page` | `200` com a página; `400 EB000001` data fora do formato; `400 EB000010` `start_date` > `end_date`; `404 EB001002`; `404 EB002001` |
| `POST` | `/accounts/{account_id}/smoothing-box/withdrawals` | Resgata da caixinha para a conta. **Idempotente** pela `idempotency_key`, no mesmo mecanismo das transferências | `value` (texto, > 0, até duas casas: `"50.00"`), `idempotency_key` | `201` com `transaction_id` e saldos (reenvio com a mesma chave e o mesmo corpo devolve o `201` original); `400 EB000001` valor ≤ 0, fora do formato ou com mais de duas casas; `404 EB001002`; `404 EB002001`; `409 EB001006` conta não está `ATIVA`; `409 EB001007` mesma chave com corpo diferente; `422 EB002005` saldo da caixinha insuficiente, com o saldo atual no corpo |

**Idempotência**: as operações financeiras iniciadas pelo cliente (deposits, transfers, payments e o resgate da caixinha em `withdrawals`) exigem o campo `idempotency_key` no corpo. A chave vale por conta (a conta dona da operação, `account_out_id`) e para uma operação só. Requisições repetidas com a mesma chave devem retornar o mesmo resultado da primeira execução, sem gerar uma nova transação. O uso da mesma chave com payload diferente, inclusive em outra operação, resulta em `409 EB001007`; a comparação usa o `request_hash` do pedido já normalizado (`"50"` e `"50.00"` são o mesmo pedido). A tarifa e o fechamento do dia não recebem chave do cliente: a tarifa usa a chave determinística `fee:{transaction_id}` e `UNIQUE(related_transaction_id)`; o fechamento, `UNIQUE(box_id, reference_date)` e a chave `closing:{box_id}:{reference_date}`.

Todas as rotas, menos `/` e `/health_check`, exigem o cabeçalho do token interno; sem ele ou com valor errado, a resposta é `403 EB000002`. Valores monetários em `numeric(15,2)`, nunca `float`. Datas no fuso `America/Sao_Paulo`.

### Códigos de erro

Todo erro responde no formato padrão do projeto (`title`, `description`, `translation`, `code`). Os códigos seguem o padrão `EB` + grupo de 3 dígitos + sequencial de 3 dígitos; cada código tem um único significado e é reutilizado em todas as rotas onde o mesmo erro acontece.

| Código | HTTP | Quando |
|---|---|---|
| `EB000001` | `400` | corpo ou parâmetros fora do formato (schema) |
| `EB000002` | `403` | token interno ausente ou errado |
| `EB000010` | `400` | parâmetros que se contradizem (`start_date` posterior a `end_date`) |
| `EB000404` | `404` | rota inexistente |
| `EB000405` | `405` | a rota existe, mas não aceita o método |
| `EB000500` | `500` | erro inesperado |
| `EB001001` | `404` | cliente inexistente |
| `EB001002` | `404` | conta inexistente (ou conta de origem inexistente) |
| `EB001003` | `422` | CPF com dígitos verificadores que não batem |
| `EB001004` | `409` | CPF já cadastrado |
| `EB001005` | `404` | conta de destino inexistente |
| `EB001006` | `409` | conta não está `ATIVA` |
| `EB001007` | `409` | `idempotency_key` reutilizada com outro payload |
| `EB001008` | `422` | saldo da conta insuficiente (na transferência, para valor + tarifa) |
| `EB001009` | `422` | transferência para a própria conta |
| `EB001010` | `409` | transição de status da conta não permitida |
| `EB001011` | `422` | encerrar conta com saldo na conta ou na caixinha |
| `EB002001` | `404` | conta sem caixinha |
| `EB002002` | `409` | a conta já tem caixinha |
| `EB002003` | `409` | o dia anterior não foi fechado (`next_reference_date` no corpo) |
| `EB002004` | `422` | `reference_date` é hoje, futuro ou anterior a `activated_on` |
| `EB002005` | `422` | saldo da caixinha insuficiente |
| `EB002006` | `409` | `PATCH` pede o status em que a caixinha já está |

Grupos: `EB000…` são os erros genéricos de toda API, `EB001…` os do banco (cliente, conta, transferência, pagamento, extrato) e `EB002…` os da caixinha.


### Banco de Dados (Somente diagrama)

```mermaid
erDiagram
    CUSTOMER ||--|| ACCOUNT : "possui"
    ACCOUNT ||--o| SMOOTHING_BOX : "possui no maximo uma"
    ACCOUNT ||--o{ TRANSACTION : "origina"
    ACCOUNT |o--o{ TRANSACTION : "recebe"
    TRANSACTION |o--o| TRANSACTION : "tarifa de"
    TRANSACTION ||--|{ LEDGER_ENTRY : "gera"
    ACCOUNT ||--o{ LEDGER_ENTRY : "movimenta"

    SMOOTHING_BOX ||--o{ BOX_ENTRY : "possui"
    TRANSACTION ||--o| BOX_ENTRY : "origina"

    SMOOTHING_BOX ||--o{ DAILY_CLOSING : "fecha um por dia"
    TRANSACTION |o--o| DAILY_CLOSING : "origina, se moveu dinheiro"

    CUSTOMER {
        uuid id PK "customer_id que sai na resposta"
        varchar document_number UK "CPF, garante cadastro único"
        varchar name
        varchar nationality
        varchar email
        date birth_date
        timestamptz created_at
    }
    ACCOUNT {
        uuid id PK "account_id que sai na resposta"
        uuid customer_id FK,UK "uma conta por cliente"
        numeric balance "numeric 15,2, CHECK balance >= 0"
        varchar status "ATIVA, SUSPENSA ou ENCERRADA"
        timestamptz created_at
        timestamptz updated_at
    }
    TRANSACTION {
        uuid id PK "transaction_id que sai na resposta"
        varchar type "DEPOSIT, TRANSFER, FEE, PAYMENT, BOX_RETENTION, BOX_RELEASE ou BOX_WITHDRAWAL"
        uuid account_out_id FK "conta dona da operacao: origem na TRANSFER e no PAYMENT, quem recebe no DEPOSIT, quem paga na FEE, dona da caixinha nas BOX_*"
        uuid account_in_id FK "conta de destino, so na TRANSFER"
        numeric value "CHECK value > 0"
        varchar idempotency_key UK "UNIQUE(account_out_id, idempotency_key)"
        varchar request_hash "detecta reuso da chave com outro payload"
        uuid related_transaction_id FK,UK "na FEE, a transferencia que a gerou"
        timestamptz created_at "quando a operação aconteceu"
    }
    LEDGER_ENTRY {
        uuid id PK
        uuid transaction_id FK
        uuid account_id FK "conta movimentada"
        varchar direction "DEBITO ou CREDITO"
        numeric value "CHECK value > 0"
        numeric balance_after "saldo da conta após o lançamento"
        timestamptz created_at "clock_timestamp(), base do extrato por período e da ordem"
    }
    SMOOTHING_BOX {
        uuid id PK
        uuid box_key UK "sai na resposta"
        uuid account_id FK,UK "uma caixinha por conta"
        numeric balance "numeric 15,2, CHECK balance >= 0"
        smallint retention_pct "CHECK entre 20 e 80"
        varchar status "ACTIVE ou PAUSED"
        date activated_on "primeiro dia fechavel"
        timestamptz created_at
        timestamptz updated_at
    }

    BOX_ENTRY {
        uuid id PK
        uuid box_id FK
        uuid transaction_id FK,UK "um lancamento de caixinha por transacao"
        varchar direction "DEBITO ou CREDITO"
        varchar origin "RETENTION, RELEASE ou WITHDRAWAL"
        numeric value "CHECK value > 0"
        numeric balance_after "saldo da caixinha apos o lancamento"
        timestamptz created_at
    }

    DAILY_CLOSING {
        uuid id PK
        uuid closing_key UK "sai na resposta"
        uuid box_id FK,UK "UNIQUE(box_id, reference_date)"
        date reference_date UK "UNIQUE(box_id, reference_date)"
        numeric income "renda do dia"
        numeric baseline "media usada, congelada"
        smallint window_days "quantos dias entraram na media"
        numeric lower_bound "piso = 0,90 x media"
        numeric upper_bound "teto = 1,10 x media"
        varchar band "WARMUP, ABOVE, NEUTRAL, BELOW ou PAUSED"
        numeric amount_calculated "o que a regra pediu"
        numeric amount_moved "o que de fato moveu"
        uuid transaction_id FK "nulo quando nada moveu"
        timestamptz created_at "quando o fechamento aconteceu"
    }
```

### Fluxos

**Cadastro de cliente e conta — caminho feliz e falhas (400, 409, 422)**

```mermaid
sequenceDiagram
    autonumber
    participant S as Sistema chamador
    participant API as API (controller)
    participant DB as PostgreSQL

    S->>API: POST /customers (name, document_number, email, birth_date, ...)
    API->>API: valida schema e máscara do CPF, senão 400 EB000001
    API->>API: valida dígitos verificadores do CPF, senão 422 EB001003
    API->>DB: BEGIN
    API->>DB: INSERT customer (document_number, ...)
    alt violação de UNIQUE(document_number)
        API->>DB: ROLLBACK
        API-->>S: 409 EB001004 CPF já cadastrado
    else CPF novo
        API->>DB: INSERT account (customer_id, status = ATIVA, balance = 0)
        API->>DB: COMMIT
        API-->>S: 201 customer_id e account_id
    end
```

**Cadastro — falha: duas requisições concorrentes com o mesmo CPF**

```mermaid
sequenceDiagram
    participant R1 as Req 1 (CPF X)
    participant DB as PostgreSQL
    participant R2 as Req 2 (CPF X)

    R1->>DB: INSERT customer (CPF X)
    R2->>DB: INSERT customer (CPF X)
    Note over R2,DB: R2 espera o desfecho da R1 no índice único
    R1->>DB: INSERT account e COMMIT
    DB-->>R2: unique_violation em document_number
    R2->>DB: ROLLBACK
    Note over R2: responde 409 EB001004 CPF já cadastrado
```

**Consulta de cliente — caminho feliz e falha (404)**

```mermaid
sequenceDiagram
    autonumber
    participant S as Sistema chamador
    participant API as API (controller)
    participant DB as PostgreSQL

    S->>API: GET /customers/{customer_id}
    API->>DB: SELECT customer JOIN account WHERE customer.id = customer_id
    alt cliente inexistente
        API-->>S: 404 EB001001 cliente inexistente
    else encontrado
        API-->>S: 200 dados do cliente, document_number e account_id
    end
```

**Consulta de saldo — caminho feliz e falha (404)**

```mermaid
sequenceDiagram
    autonumber
    participant S as Sistema chamador
    participant API as API (controller)
    participant DB as PostgreSQL

    S->>API: GET /accounts/{account_id}
    API->>DB: SELECT balance, status FROM account WHERE id = account_id
    Note over DB: leitura sem trava, vê o último saldo commitado
    alt conta inexistente
        API-->>S: 404 EB001002 conta inexistente
    else encontrada
        API-->>S: 200 account_id, balance e status
    end
```

**Ciclo de vida da conta — `PATCH /accounts/{account_id}`**

A conta nasce `ATIVA` no `POST /customers`. Só uma conta `ATIVA` deposita, transfere, recebe, paga, consulta o extrato e usa a caixinha (`409 EB001006` nas outras). A mudança trava a conta e, ao encerrar, a caixinha, na mesma ordem das outras operações.

```mermaid
stateDiagram-v2
    [*] --> ATIVA: POST /customers
    ATIVA --> SUSPENSA: PATCH
    SUSPENSA --> ATIVA: PATCH
    ATIVA --> ENCERRADA: PATCH, com conta e caixinha zeradas
    SUSPENSA --> ENCERRADA: PATCH, com conta e caixinha zeradas
    ENCERRADA --> [*]
```

Qualquer outro caminho, inclusive pedir o status em que a conta já está, responde `409 EB001010`. Encerrar com saldo na conta ou na caixinha responde `422 EB001011`: o dinheiro ficaria preso numa conta que não movimenta mais.

**Transferência — caminho feliz e falhas (404, 409, 422, reenvio idempotente)**

O pagamento (`POST /accounts/{account_id_out}/payments`) segue o mesmo fluxo, mas trava só a conta de origem, grava só o lançamento de débito, já que o destino é externo ao banco, e não cobra tarifa. O depósito (`POST /accounts/{account_id}/deposits`) é o espelho do pagamento: trava só a conta e grava só o crédito.

```mermaid
sequenceDiagram
    autonumber
    participant S as Sistema chamador
    participant API as API (controller)
    participant DB as PostgreSQL

    S->>API: POST /accounts/{out}/transfers (account_id_in, value, idempotency_key)
    API->>API: valida schema (value > 0), senão 400 EB000001
    API->>API: origem = destino? 422 EB001009
    API->>DB: BEGIN
    API->>DB: SELECT account WHERE id IN (out, in) ORDER BY id FOR UPDATE
    Note over DB: trava as duas linhas em ordem de id (evita deadlock)
    API->>DB: SELECT transaction WHERE account_out_id = out AND idempotency_key = k
    alt chave já usada
        alt mesmo payload (request_hash igual)
            API->>DB: ROLLBACK
            API-->>S: 201 com a transação original
        else payload diferente
            API->>DB: ROLLBACK
            API-->>S: 409 EB001007 chave reutilizada com outro payload
        end
    else chave nova
        alt origem ou destino inexistente
            API->>DB: ROLLBACK
            API-->>S: 404 EB001002 (origem) ou EB001005 (destino)
        else alguma conta não está ATIVA
            API->>DB: ROLLBACK
            API-->>S: 409 EB001006 conta inativa
        else saldo da origem < value + tarifa
            Note over API: tarifa = 0 se a origem fez menos de 5 TRANSFER no mês, senão max(1% × value, R$ 1,00)
            API->>DB: ROLLBACK
            API-->>S: 422 EB001008 saldo insuficiente
        else tudo ok
            API->>DB: INSERT transaction TRANSFER (idempotency_key, request_hash, value)
            API->>DB: INSERT ledger_entry DEBITO (out) e CREDITO (in)
            API->>DB: UPDATE account SET balance = balance - value (out)
            API->>DB: UPDATE account SET balance = balance + value (in)
            opt tarifa > 0
                API->>DB: INSERT transaction FEE (related_transaction_id, chave fee:{id})
                API->>DB: INSERT ledger_entry DEBITO da tarifa (out)
                API->>DB: UPDATE account SET balance = balance - tarifa (out)
            end
            API->>DB: COMMIT (libera as travas)
            API-->>S: 201 transaction_id, fee e balance_after
        end
    end
```

**Transferência — falha: duas requisições concorrentes na mesma conta**

```mermaid
sequenceDiagram
    participant R1 as Req 1 (débito R$80)
    participant DB as PostgreSQL
    participant R2 as Req 2 (débito R$80)

    Note over DB: conta X com saldo 100
    R1->>DB: SELECT conta X FOR UPDATE
    DB-->>R1: saldo 100 (trava obtida)
    R2->>DB: SELECT conta X FOR UPDATE
    Note over R2,DB: R2 fica bloqueada esperando a trava
    R1->>DB: INSERT transfer e ledger, UPDATE saldo = 20 (isenta, 1ª do mês)
    R1->>DB: COMMIT
    Note over DB: trava liberada
    DB-->>R2: saldo 20 (lê o valor já atualizado, precisa de 80)
    R2->>DB: ROLLBACK
    Note over R2: responde 422 EB001008 saldo insuficiente
```

**Regra da tarifa** (constantes em `src/constants.py`, cálculo em `src/controllers/transfer_fee_rule.py`)

| Parâmetro | Valor | Por quê |
|---|---|---|
| Franquia | **5** transferências enviadas por mês, por conta | cobre o uso do dia a dia sem custo |
| Mês | do dia 1º às 00:00 ao último dia às 24:00, no fuso de São Paulo | o mesmo relógio do cliente e da caixinha |
| O que conta | só `TRANSFER` gravadas em que a conta é a origem | transferência recusada ou recebida não gasta franquia |
| Percentual | **1%** do valor, arredondado ao centavo (meio centavo sobe) | cobra mais de quem movimenta mais |
| Mínimo | **R$ 1,00** | abaixo disso a tarifa não paga o processamento |

Exemplos fora da franquia: R$ 10,00 paga R$ 1,00 (o mínimo); R$ 500,00 paga R$ 5,00; R$ 123,45 paga R$ 1,23. A contagem do mês acontece depois de a conta de origem estar travada, então dois pedidos simultâneos fazem fila e o segundo já enxerga o primeiro: a última isenção do mês vai para um pedido só.

**Extrato de transações — caminho feliz e falhas (400, 404, 409)**

```mermaid
sequenceDiagram
    autonumber
    participant S as Sistema chamador
    participant API as API (controller)
    participant DB as PostgreSQL

    S->>API: GET /accounts/{account_id}/transactions (start_date, end_date, limit, page opcionais)
    API->>API: valida formato das datas (senão 400 EB000001) e start_date <= end_date (senão 400 EB000010)
    API->>DB: SELECT status FROM account WHERE id = account_id
    alt conta inexistente
        API-->>S: 404 EB001002 conta inexistente
    else conta não está ATIVA
        API-->>S: 409 EB001006 conta inativa
    else conta ATIVA
        API->>DB: SELECT ledger_entry JOIN transaction WHERE account_id = account_id AND created_at no período ORDER BY created_at DESC, id DESC LIMIT limit + 1 OFFSET page × limit
        Note over API: veio uma linha a mais que o limite? então há próxima página
        API-->>S: 200 data (tipo, direção, valor, saldo após, contraparte, data), limit, page, is_last_page
    end
```

**Parâmetros da regra** (constantes do módulo; só `retention_pct` é por caixinha)

| Parâmetro | Valor | Por quê |
|---|---|---|
| Janela da média | últimos **28** fechamentos anteriores ao dia | 4 semanas: cada dia da semana pesa igual |
| Aquecimento | primeiros **14** fechamentos: faixa `WARMUP`, nada se move | média com menos de 2 semanas é ruído |
| Renda do dia | soma dos `ledger_entry` `CREDITO` da conta no dia, **exceto** `BOX_RELEASE` e `BOX_WITHDRAWAL` | a própria liberação não pode inflar a média |
| Dia sem renda | entra como **0** na média | folga é renda zero de verdade; a caixinha existe para ela |
| Teto (ACIMA) | renda > média × **1,10** | tolerância de 10% evita mexer em dia normal |
| Piso (ABAIXO) | renda < média × **0,90** | o que a liberação garante |
| Retenção | (renda − teto) × `retention_pct` | só o excedente acima do teto, nunca a renda base |
| Limite da caixinha | saldo até **10 × média** | ≈ 2 semanas de renda; acima disso para de reter |
| Arredondamento | para baixo, na segunda casa decimal (centavo) | nunca move um centavo a mais que a regra |

**Classificação do dia** (`M` = média, `R` = renda do dia, `S` = saldo da caixinha, `C` = saldo da conta)

```mermaid
flowchart TD
    A[Fechar dia D] --> B{Menos de 14 fechamentos?}
    B -- sim --> W[WARMUP: grava renda, move 0]
    B -- nao --> P{Caixinha PAUSED?}
    P -- sim --> PZ[PAUSED: grava renda e media, move 0]
    P -- nao --> M0{M = 0?}
    M0 -- sim --> N[NEUTRAL: move 0]
    M0 -- nao --> X{R comparado a M}
    X -- "R > 1,10 M" --> UP["ABOVE: reter = min((R - 1,10 M) x pct, 10 M - S, C)"]
    X -- "0,90 M <= R <= 1,10 M" --> N
    X -- "R < 0,90 M" --> DN["BELOW: liberar = min(0,90 M - R, S)"]
    UP --> T[transaction BOX_RETENTION: debita conta, credita caixinha]
    DN --> T2[transaction BOX_RELEASE: debita caixinha, credita conta]
```

Exemplo com média R$ 200 (teto R$ 220, piso R$ 180) e retenção de 50%: num dia de R$ 320 a caixinha
guarda (320 − 220) × 50% = **R$ 50** e o cliente fica com R$ 270; num dia de R$ 120 a caixinha devolve
180 − 120 = **R$ 60**; numa folga (R$ 0) devolve até **R$ 180**, se houver saldo. Um fechamento `PAUSED`
ou `WARMUP` não move dinheiro, mas grava a renda do dia: a sequência de fechamentos não tem buraco e a
média continua contando dias de 0.

**Fechar o dia — caminho feliz**

```mermaid
sequenceDiagram
    participant Ag as Agendador
    participant API
    participant DB as Banco
    Ag->>API: POST /accounts/{id}/smoothing-box/closings {reference_date: D}
    API->>API: valida corpo, D < hoje
    Note over API,DB: BEGIN implicito na 1a consulta
    API->>DB: SELECT account ... FOR UPDATE
    Note over DB: linha da conta travada
    API->>DB: SELECT smoothing_box ... FOR UPDATE
    Note over DB: linha da caixinha travada
    API->>DB: SELECT daily_closing (box, D)
    DB-->>API: nenhum
    API->>DB: SELECT daily_closing (box, D-1)
    DB-->>API: existe
    API->>DB: SELECT income dos ultimos 28 fechamentos
    API->>DB: SUM ledger_entry CREDITO de D, sem BOX_RELEASE/BOX_WITHDRAWAL
    API->>API: media, piso, teto, faixa, valor
    alt ABOVE ou BELOW, valor > 0
        API->>DB: INSERT transaction (idempotency_key closing:box:D)
        API->>DB: INSERT ledger_entry + UPDATE account.balance
        API->>DB: INSERT box_entry + UPDATE smoothing_box.balance
    end
    API->>DB: INSERT daily_closing
    API->>DB: COMMIT
    Note over DB: travas liberadas
    API-->>Ag: 201 {closing_key, band, income, baseline, lower_bound, upper_bound, amount_calculated, amount_moved}
```

1. Valida o corpo; `reference_date` precisa ser um dia já encerrado (`422 EB002005` antes de qualquer
   trava) e, depois de ler a caixinha, não anterior a `activated_on` (o mesmo `422`).
2. Trava a conta e depois a caixinha, **sempre nessa ordem** — a mesma do resgate. A transferência do
   time trava só a conta, então espera o fechamento terminar (milissegundos) e nunca forma ciclo.
3. Procura o fechamento de D. Não há. Procura o de D−1 (ou D é `activated_on`). Há.
4. Lê a renda dos últimos 28 fechamentos já gravados — números congelados, não o ledger — e soma os
   créditos de renda de D no ledger, fora os movimentos da própria caixinha.
5. Calcula média, piso, teto e faixa pela regra acima, já limitando pelo saldo da conta (retenção) ou da
   caixinha (liberação), que estão travados e não mudam até o `COMMIT`.
6. Se há valor a mover, grava uma `transaction` com `idempotency_key = closing:{box_id}:{D}`, o
   lançamento na conta, o lançamento na caixinha e atualiza os dois saldos. Grava o `daily_closing` com
   tudo que foi usado no cálculo. Confirma: as travas saem juntas. Responde `201`.

**Fechar o dia — falha: o agendador manda o mesmo dia duas vezes ao mesmo tempo**

1. A e B pedem o fechamento de D. A trava a conta; B pede a mesma trava e fica parada no banco.
2. A calcula, move R$ 50, grava o `daily_closing` e confirma. A trava é liberada.
3. B recebe a trava, procura o fechamento de D e o encontra. Responde `200` com o corpo do fechamento de
   A. Nenhuma `transaction`, nenhum lançamento, saldo intacto.
4. Se algum caminho escapar da trava, o `INSERT` de B esbarra em `UNIQUE(box_id, reference_date)` (e na
   `idempotency_key` da `transaction`): a sessão é desfeita inteira, inclusive o movimento, e a API
   relê e devolve o fechamento existente com `200`.

**Fechar o dia — falha: o dia anterior não foi fechado**

1. O agendador ficou fora do ar em D−1 e pede D. A API trava conta e caixinha, não encontra o fechamento
   de D−1 e encerra a sessão sem `COMMIT`.
2. Responde `409 EB002003` com `next_reference_date` = o primeiro dia aberto. O agendador fecha os dias
   em ordem até chegar a D. Fechar fora de ordem deixaria a média de D sem o dia D−1.

**Fechar o dia — falha: o cliente gastou o excedente antes do fechamento**

1. A regra pede reter R$ 50, mas a conta travada tem R$ 30.
2. A retenção move R$ 30: `amount_calculated` = 50,00, `amount_moved` = 30,00. A conta fica em zero, não
   negativa. Com saldo zero, nada se move e `transaction_id` fica `null`. Responde `201` normalmente.

**Resgatar — caminho feliz**

1. Valida `value` > 0 e procura a `transaction` pela `idempotency_key`. Não há.
2. Trava a conta e depois a caixinha (mesma ordem do fechamento).
3. O saldo da caixinha cobre o valor. Grava `transaction` `BOX_WITHDRAWAL`, o débito na caixinha, o
   crédito na conta e atualiza os dois saldos. Confirma e responde `201`.

**Resgatar — falha: saldo da caixinha insuficiente, com fechamento concorrente**

1. A caixinha tem R$ 100. O cliente pede R$ 100 enquanto o fechamento de um dia `BELOW` está liberando
   R$ 60. O fechamento pegou as travas primeiro; o resgate espera na trava da conta.
2. O fechamento confirma: caixinha com R$ 40. O resgate recebe as travas, lê R$ 40 e responde
   `422 EB002005` com o saldo atual. Nada é gravado. A mesma chave com o mesmo corpo repetida depois
   volta a ser avaliada; com outro corpo, `409 EB001007`.


> ## Principal desafio
>
> - **Qual é:** fechar o dia move dinheiro com base num cálculo sobre o histórico, e esse movimento
>   precisa acontecer exatamente uma vez por dia, com um resultado que se possa refazer depois.
> - **Por que é difícil:** o agendador reenvia pedidos e pode rodar duas instâncias; a conta continua
>   recebendo transferências durante o cálculo; e a solução óbvia — calcular a média relendo o ledger —
>   devolve outro número se um crédito antigo for estornado, ou se a própria liberação da caixinha for
>   contada como renda e inflar a média seguinte.
> - **Como o desenho resolve:** a conta e a caixinha são travadas com `SELECT … FOR UPDATE`, sempre
>   nessa ordem, antes de procurar o fechamento do dia; quem chega depois espera, acha o fechamento e
>   recebe `200` sem mover nada, e `UNIQUE(box_id, reference_date)` mais a `idempotency_key`
>   determinística da `transaction` seguram o caso que escapar. A média lê a renda já gravada nos 28
>   `daily_closing` anteriores, não o ledger, e cada fechamento guarda a média, o piso, o teto e os
>   valores calculado e movido; a renda do dia exclui `BOX_RELEASE` e `BOX_WITHDRAWAL`. Os fechamentos
>   são sequenciais (`409 EB002003` se faltar o dia anterior), então todo dia, inclusive a folga, entra na média.
