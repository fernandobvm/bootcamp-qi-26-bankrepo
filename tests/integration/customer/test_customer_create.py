from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from tests.utils import BankApi, PayloadGenerator, RandomGenerator, RequestGenerator

ERROR_FIELDS = {"title", "description", "translation", "code"}


class TestCustomerCreate:
    def test_creates_customer_with_an_empty_active_account(self):
        payload = PayloadGenerator.create_customer_payload()

        status, customer = RequestGenerator.POST_customer(payload)

        assert status == 201
        assert customer["document_number"] == payload["document_number"]
        assert customer["name"] == payload["name"]

        status, account = RequestGenerator.GET_account(customer["account_id"])
        assert status == 200
        assert account["customer_id"] == customer["customer_id"]
        assert account["balance"] == "0.00"
        assert account["status"] == "ATIVA"

    def test_same_cpf_twice_is_refused(self):
        """Cadastro único: o segundo POST com o mesmo CPF é barrado, no formato de erro do projeto."""
        document_number = RandomGenerator.generate_cpf()
        RequestGenerator.POST_customer(PayloadGenerator.create_customer_payload(document_number=document_number))

        status, response = RequestGenerator.POST_customer(
            PayloadGenerator.create_customer_payload(document_number=document_number)
        )

        assert status == 409
        assert response["code"] == "EB001004"
        assert ERROR_FIELDS <= set(response.keys())

    def test_concurrent_requests_with_the_same_cpf_create_one_customer(self):
        """Cinco cadastros simultâneos do mesmo CPF: o UNIQUE deixa passar um só."""
        document_number = RandomGenerator.generate_cpf()

        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(
                pool.map(
                    lambda _: RequestGenerator.POST_customer(
                        PayloadGenerator.create_customer_payload(document_number=document_number)
                    ),
                    range(5),
                )
            )

        statuses = sorted(status for status, _ in results)
        assert statuses == [201, 409, 409, 409, 409]

        for status, response in results:
            if status == 409:
                assert response["code"] == "EB001004"

    def test_cpf_with_wrong_check_digits_is_unprocessable(self):
        for document_number in ["111.222.333-44", "111.111.111-11"]:
            status, response = RequestGenerator.POST_customer(
                PayloadGenerator.create_customer_payload(document_number=document_number)
            )

            assert status == 422, document_number
            assert response["code"] == "EB001003"

    def test_schema_refuses_malformed_fields(self):
        malformed_fields = [
            ("document_number", "12345678901"),
            ("email", "isto-nao-e-um-email"),
            ("birth_date", "10/03/1995"),
            ("name", ""),
        ]

        for field, value in malformed_fields:
            payload = PayloadGenerator.create_customer_payload()
            payload[field] = value

            status, response = RequestGenerator.POST_customer(payload)

            assert status == 400, f"o campo '{field}' aceitou '{value}'"
            assert response["code"] == "EB000001"

    def test_schema_refuses_missing_and_unknown_fields(self):
        payload = PayloadGenerator.create_customer_payload()
        del payload["document_number"]
        status, response = RequestGenerator.POST_customer(payload)
        assert status == 400
        assert response["code"] == "EB000001"

        payload = PayloadGenerator.create_customer_payload()
        payload["balance"] = "1000.00"
        status, response = RequestGenerator.POST_customer(payload)
        assert status == 400
        assert response["code"] == "EB000001"

    def test_birth_date_must_exist_and_be_in_the_past(self):
        tomorrow = (BankApi.today() + timedelta(days=1)).isoformat()

        for birth_date in ["1995-02-30", tomorrow]:
            status, response = RequestGenerator.POST_customer(
                PayloadGenerator.create_customer_payload(birth_date=birth_date)
            )

            assert status == 400, birth_date
            assert response["code"] == "EB000001"
