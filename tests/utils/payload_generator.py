from uuid import uuid4

from tests.utils.random_generator import RandomGenerator


class PayloadGenerator:
    @staticmethod
    def create_customer_payload(
        name: str = None,
        nationality: str = None,
        document_number: str = None,
        email: str = None,
        birth_date: str = None,
    ) -> dict:
        """Um cadastro de cliente válido, com CPF e e-mail aleatórios."""
        if name is None:
            name = "João Entregador"

        if nationality is None:
            nationality = "brasileira"

        if document_number is None:
            document_number = RandomGenerator.generate_cpf()

        if email is None:
            email = f"joao.entregador.{uuid4()}@exemplo.com.br"

        if birth_date is None:
            birth_date = "1995-03-10"

        return {
            "name": name,
            "nationality": nationality,
            "document_number": document_number,
            "email": email,
            "birth_date": birth_date,
        }

    @staticmethod
    def create_operation_payload(value: str, idempotency_key: str = None) -> dict:
        """Depósito e pagamento: valor em texto e uma chave nova a cada chamada."""
        if idempotency_key is None:
            idempotency_key = str(uuid4())

        return {"value": value, "idempotency_key": idempotency_key}

    @staticmethod
    def create_transfer_payload(account_id_in: str, value: str, idempotency_key: str = None) -> dict:
        if idempotency_key is None:
            idempotency_key = str(uuid4())

        return {"account_id_in": account_id_in, "value": value, "idempotency_key": idempotency_key}
