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
# Núcleo do banco — o mínimo que a caixinha precisa
# ────────────────────────────────────────────────────────────────────
# O RFC ainda deixa o código de "conta inexistente" como EB00XXXX. Este
# é provisório: quando o time fixar o dele, troca-se aqui e só aqui.


class NotFoundAccount(QIException):
    code = "EB001030"

    def __init__(self, account_id) -> None:
        title = "Account not Found"
        http_status = 404
        description = f"Account {account_id} was not found."
        translation = "A conta informada não existe."
        super().__init__(title, self.code, http_status, description, translation)


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


class AccountNotActive(QIException):
    code = "EB002003"

    def __init__(self, account_id, account_status) -> None:
        title = "Account is not active"
        http_status = 409
        description = f"Account {account_id} is {account_status}, and only ATIVA accounts use the smoothing box."
        translation = "A conta não está ATIVA."
        super().__init__(title, self.code, http_status, description, translation)


class PreviousDayNotClosed(QIException):
    """Pediram o dia D e o dia anterior ainda está aberto.

    Os fechamentos são em sequência porque a média de D precisa de D−1
    dentro dela. O corpo diz qual é o primeiro dia em aberto, e quem
    chamou fecha a partir dali.
    """

    code = "EB002004"

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
    code = "EB002005"

    def __init__(self, reference_date, reason) -> None:
        title = "Invalid reference date"
        http_status = 422
        description = f"Cannot close {reference_date.isoformat()}: {reason}."
        translation = "Este dia não pode ser fechado."
        super().__init__(title, self.code, http_status, description, translation)


class InsufficientBoxBalance(QIException):
    code = "EB002006"

    def __init__(self, requested, box_balance) -> None:
        title = "Insufficient smoothing box balance"
        http_status = 422
        description = f"Requested {requested}, but the smoothing box holds {box_balance}."
        translation = "O saldo da caixinha não cobre o resgate."
        super().__init__(title, self.code, http_status, description, translation)
        self.extra = {"box_balance": f"{box_balance:.2f}"}


class IdempotencyKeyReused(QIException):
    code = "EB002007"

    def __init__(self, idempotency_key) -> None:
        title = "Idempotency key reused"
        http_status = 409
        description = f"The idempotency_key {idempotency_key} was already used with a different request."
        translation = "Esta chave de idempotência já foi usada com outro pedido."
        super().__init__(title, self.code, http_status, description, translation)


class SmoothingBoxSameStatus(QIException):
    code = "EB002008"

    def __init__(self, box_status) -> None:
        title = "Smoothing box already in this status"
        http_status = 409
        description = f"The smoothing box is already {box_status}."
        translation = "A caixinha já está neste status."
        super().__init__(title, self.code, http_status, description, translation)
