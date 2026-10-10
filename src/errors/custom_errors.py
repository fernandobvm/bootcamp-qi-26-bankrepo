from errors import QIException


class NotFoundSampleEntity(QIException):
    code = "QIT001001"

    def __init__(self, sample_entity_key) -> None:
        title = "Entity not Found"
        http_status = 404
        description = f"Entity with key {sample_entity_key} was not found."
        translation = f"A entidade com chave {sample_entity_key} não foi encontrada."
        super().__init__(title, self.code, http_status, description, translation)


class SampleEntityFinalStatus(QIException):
    code = "QIT001002"

    def __init__(self, old_status, new_status) -> None:
        title = "Entity cannot change status"
        http_status = 409
        description = f"Entity with status {old_status} cannot update to {new_status}."
        translation = "Essa entidade não pode ser atualizada."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidDocumentNumber(QIException):
    """O CPF tem o formato certo e não existe.

    422, e não 400, de propósito: 400 quer dizer "não consegui ler o seu
    pedido". Aqui a API leu, entendeu, e o valor é que não pode existir —
    os dois últimos dígitos não batem com a conta. A diferença está
    explicada em src/utils/document_number.py.
    """

    code = "QIT001003"

    def __init__(self, document_number) -> None:
        title = "Invalid Document Number"
        http_status = 422
        description = f"The document number {document_number} is not a valid CPF."
        translation = "O CPF informado não é válido."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedDocumentNumber(QIException):
    """Já existe um cadastro com este CPF.

    409 Conflict: o pedido está correto em si, e o que impede é o que já
    está no banco. É a mesma família do SampleEntityFinalStatus aqui em
    cima — conflito com o que já existe, não erro de quem pediu.
    """

    code = "QIT001004"

    def __init__(self, document_number) -> None:
        title = "Document Number already registered"
        http_status = 409
        description = f"There is already an entity with the document number {document_number}."
        translation = "Já existe um cadastro com este CPF."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedEmail(QIException):
    code = "QIT001005"

    def __init__(self, email) -> None:
        title = "Email already registered"
        http_status = 409
        description = f"There is already an entity with the email {email}."
        translation = "Já existe um cadastro com este e-mail."
        super().__init__(title, self.code, http_status, description, translation)


class UnderageSampleEntity(QIException):
    code = "QIT001006"

    def __init__(self, age, minimum_age) -> None:
        title = "Entity is underage"
        http_status = 422
        description = f"The entity is {age} years old, and the minimum is {minimum_age}."
        translation = f"É preciso ter pelo menos {minimum_age} anos."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidBirthdate(QIException):
    """A data tem o formato certo e não existe no calendário.

    Existe porque o `pattern` do schema sabe contar dígitos, não dias:
    "2025-02-30" e "9999-99-99" passam pelo regex e morrem no
    `date.fromisoformat`. Sem esta classe, esse ValueError virava 500 —
    a API culpando a si mesma por um erro de quem chamou.
    """

    code = "QIT001007"

    def __init__(self, birthdate) -> None:
        title = "Invalid Birthdate"
        http_status = 422
        description = f"The birthdate {birthdate} is not a real date."
        translation = "A data de nascimento informada não existe."
        super().__init__(title, self.code, http_status, description, translation)


# ────────────────────────────────────────────────────────────────────
# Núcleo do banco — EB001xxx, a tabela "Códigos de erro" do RFC
# ────────────────────────────────────────────────────────────────────


class NotFoundCustomer(QIException):
    code = "EB001001"

    def __init__(self, customer_id) -> None:
        title = "Customer not Found"
        http_status = 404
        description = f"Customer {customer_id} was not found."
        translation = "O cliente informado não existe."
        super().__init__(title, self.code, http_status, description, translation)


class NotFoundAccount(QIException):
    """Conta inexistente — ou, numa transferência, a conta de ORIGEM.

    A de destino tem código próprio (EB001005): quem chamou precisa saber
    qual das duas pontas está errada sem ler a descrição.
    """

    code = "EB001002"

    def __init__(self, account_id) -> None:
        title = "Account not Found"
        http_status = 404
        description = f"Account {account_id} was not found."
        translation = "A conta informada não existe."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidCustomerDocument(QIException):
    """O CPF tem a máscara certa e os dígitos verificadores não batem.

    O mesmo 422 do InvalidDocumentNumber da sample entity, e pelo mesmo
    motivo (src/utils/document_number.py): a API leu o pedido, e o valor
    é que não pode existir. Código separado porque este é do banco.
    """

    code = "EB001003"

    def __init__(self, document_number) -> None:
        title = "Invalid Document Number"
        http_status = 422
        description = f"The document number {document_number} is not a valid CPF."
        translation = "O CPF informado não é válido."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedCustomer(QIException):
    code = "EB001004"

    def __init__(self, document_number) -> None:
        title = "Customer already registered"
        http_status = 409
        description = f"There is already a customer with the document number {document_number}."
        translation = "Já existe um cliente com este CPF."
        super().__init__(title, self.code, http_status, description, translation)


class NotFoundDestinationAccount(QIException):
    code = "EB001005"

    def __init__(self, account_id) -> None:
        title = "Destination account not Found"
        http_status = 404
        description = f"Destination account {account_id} was not found."
        translation = "A conta de destino não existe."
        super().__init__(title, self.code, http_status, description, translation)


class AccountNotActive(QIException):
    code = "EB001006"

    def __init__(self, account_id, account_status) -> None:
        title = "Account is not active"
        http_status = 409
        description = f"Account {account_id} is {account_status}, and only ATIVA accounts can do this."
        translation = "A conta não está ATIVA."
        super().__init__(title, self.code, http_status, description, translation)


class IdempotencyKeyReused(QIException):
    code = "EB001007"

    def __init__(self, idempotency_key) -> None:
        title = "Idempotency key reused"
        http_status = 409
        description = f"The idempotency_key {idempotency_key} was already used with a different request."
        translation = "Esta chave de idempotência já foi usada com outro pedido."
        super().__init__(title, self.code, http_status, description, translation)


class InsufficientBalance(QIException):
    """O saldo não cobre o pedido. Na transferência, o pedido é valor + tarifa."""

    code = "EB001008"

    def __init__(self, required, balance) -> None:
        title = "Insufficient balance"
        http_status = 422
        description = f"The operation needs {required:.2f}, but the account holds {balance:.2f}."
        translation = "O saldo da conta não cobre a operação."
        super().__init__(title, self.code, http_status, description, translation)
        self.extra = {"balance": f"{balance:.2f}"}


class SameAccountTransfer(QIException):
    code = "EB001009"

    def __init__(self, account_id) -> None:
        title = "Same account transfer"
        http_status = 422
        description = f"Account {account_id} cannot transfer to itself."
        translation = "A conta de origem e a de destino são a mesma."
        super().__init__(title, self.code, http_status, description, translation)


class AccountStatusTransitionNotAllowed(QIException):
    """O ciclo de vida da conta só anda por estes caminhos:

        ATIVA ⇄ SUSPENSA
        ATIVA ou SUSPENSA → ENCERRADA (e dali não sai mais)

    Pedir o status em que a conta já está também cai aqui: não há
    transição nenhuma a fazer.
    """

    code = "EB001010"

    def __init__(self, old_status, new_status) -> None:
        title = "Account status transition not allowed"
        http_status = 409
        description = f"An account cannot go from {old_status} to {new_status}."
        translation = "A conta não pode mudar para este status."
        super().__init__(title, self.code, http_status, description, translation)


class AccountHasBalance(QIException):
    """Encerrar uma conta com dinheiro dentro deixaria o dinheiro preso nela."""

    code = "EB001011"

    def __init__(self, balance, box_balance) -> None:
        title = "Account still has balance"
        http_status = 422
        description = (
            f"The account holds {balance:.2f} and its smoothing box holds {box_balance:.2f}; "
            "both must be zero to close it."
        )
        translation = "A conta só pode ser encerrada com saldo zero, inclusive na caixinha."
        super().__init__(title, self.code, http_status, description, translation)
        self.extra = {"balance": f"{balance:.2f}", "box_balance": f"{box_balance:.2f}"}


# ────────────────────────────────────────────────────────────────────
# Caixinha de Equilíbrio — EB002xxx, como no RFC
# ────────────────────────────────────────────────────────────────────


class NotFoundSmoothingBox(QIException):
    code = "EB002001"

    def __init__(self, account_id) -> None:
        title = "Smoothing box not Found"
        http_status = 404
        description = f"Account {account_id} has no smoothing box."
        translation = "Esta conta não tem caixinha."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedSmoothingBox(QIException):
    code = "EB002002"

    def __init__(self, account_id) -> None:
        title = "Smoothing box already exists"
        http_status = 409
        description = f"Account {account_id} already has a smoothing box."
        translation = "Esta conta já tem uma caixinha."
        super().__init__(title, self.code, http_status, description, translation)


class PreviousDayNotClosed(QIException):
    """Pediram o dia D e o dia anterior ainda está aberto.

    Os fechamentos são em sequência porque a média de D precisa de D−1
    dentro dela. O corpo diz qual é o primeiro dia em aberto, e quem
    chamou fecha a partir dali.
    """

    code = "EB002003"

    def __init__(self, reference_date, next_reference_date) -> None:
        title = "Previous day not closed"
        http_status = 409
        description = (
            f"Cannot close {reference_date.isoformat()}: the first open day is "
            f"{next_reference_date.isoformat()}."
        )
        translation = "O dia anterior ainda não foi fechado."
        super().__init__(title, self.code, http_status, description, translation)
        self.extra = {"next_reference_date": next_reference_date.isoformat()}


class InvalidReferenceDate(QIException):
    code = "EB002004"

    def __init__(self, reference_date, reason) -> None:
        title = "Invalid reference date"
        http_status = 422
        description = f"Cannot close {reference_date.isoformat()}: {reason}."
        translation = "Este dia não pode ser fechado."
        super().__init__(title, self.code, http_status, description, translation)


class InsufficientBoxBalance(QIException):
    code = "EB002005"

    def __init__(self, requested, box_balance) -> None:
        title = "Insufficient smoothing box balance"
        http_status = 422
        description = f"Requested {requested}, but the smoothing box holds {box_balance}."
        translation = "O saldo da caixinha não cobre o resgate."
        super().__init__(title, self.code, http_status, description, translation)
        self.extra = {"box_balance": f"{box_balance:.2f}"}


class SmoothingBoxSameStatus(QIException):
    code = "EB002006"

    def __init__(self, box_status) -> None:
        title = "Smoothing box already in this status"
        http_status = 409
        description = f"The smoothing box is already {box_status}."
        translation = "A caixinha já está neste status."
        super().__init__(title, self.code, http_status, description, translation)
