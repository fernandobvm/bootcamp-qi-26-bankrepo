from datetime import timedelta
from uuid import uuid4

from tests.utils import BankApi, PayloadGenerator, RequestGenerator


def account_with_movements(number_of_payments: int) -> str:
    """Um depósito de 100 e `number_of_payments` pagamentos de 1,00: N + 1 linhas no extrato."""
    account_id = BankApi.create_account(balance="100.00")

    for _ in range(number_of_payments):
        status, payment = RequestGenerator.POST_payment(account_id, PayloadGenerator.create_operation_payload("1.00"))
        assert status == 201, payment

    return account_id


class TestStatement:
    def test_pages_carry_data_limit_page_and_is_last_page(self):
        """Extrato paginado: cinco linhas, de duas em duas, sem repetir nem pular nenhuma."""
        account_id = account_with_movements(4)

        seen_ids = []
        for page, expected_size, expected_last in [(0, 2, False), (1, 2, False), (2, 1, True)]:
            status, response = RequestGenerator.GET_account_transactions(
                account_id, {"limit": "2", "page": str(page)}
            )

            assert status == 200
            assert set(response.keys()) == {"data", "limit", "page", "is_last_page"}
            assert response["limit"] == 2
            assert response["page"] == page
            assert response["is_last_page"] is expected_last
            assert len(response["data"]) == expected_size

            seen_ids.extend(line["transaction_id"] for line in response["data"])

        assert len(set(seen_ids)) == 5

    def test_newest_first_with_running_balance(self):
        account_id = account_with_movements(2)

        lines = BankApi.statement(account_id)

        assert [line["type"] for line in lines] == ["PAYMENT", "PAYMENT", "DEPOSIT"]
        assert [line["balance_after"] for line in lines] == ["98.00", "99.00", "100.00"]
        assert [line["direction"] for line in lines] == ["DEBITO", "DEBITO", "CREDITO"]

    def test_default_page_has_ten_lines(self):
        account_id = account_with_movements(11)

        status, response = RequestGenerator.GET_account_transactions(account_id)

        assert status == 200
        assert response["limit"] == 10
        assert response["page"] == 0
        assert len(response["data"]) == 10
        assert response["is_last_page"] is False

    def test_filters_by_period_in_bank_days(self):
        account_id = account_with_movements(1)
        today = BankApi.today()
        tomorrow = (today + timedelta(days=1)).isoformat()
        yesterday = (today - timedelta(days=1)).isoformat()

        status, response = RequestGenerator.GET_account_transactions(
            account_id, {"start_date": today.isoformat(), "end_date": today.isoformat()}
        )
        assert status == 200
        assert len(response["data"]) == 2

        status, response = RequestGenerator.GET_account_transactions(account_id, {"start_date": tomorrow})
        assert status == 200
        assert response["data"] == []
        assert response["is_last_page"] is True

        status, response = RequestGenerator.GET_account_transactions(account_id, {"end_date": yesterday})
        assert status == 200
        assert response["data"] == []

    def test_start_after_end_is_bad_request(self):
        account_id = BankApi.create_account()

        status, response = RequestGenerator.GET_account_transactions(
            account_id, {"start_date": "2026-05-10", "end_date": "2026-05-01"}
        )

        assert status == 400
        assert response["code"] == "EB000010"

    def test_refuses_malformed_parameters(self):
        account_id = BankApi.create_account()

        for params in [{"start_date": "10/05/2026"}, {"limit": "101"}, {"page": "-1"}, {"inicio": "2026-05-01"}]:
            status, response = RequestGenerator.GET_account_transactions(account_id, params)
            assert status == 400, params
            assert response["code"] == "EB000001"

    def test_unknown_account_is_not_found(self):
        status, response = RequestGenerator.GET_account_transactions(str(uuid4()))

        assert status == 404
        assert response["code"] == "EB001002"

    def test_inactive_account_is_conflict(self):
        account_id = BankApi.create_account(status="SUSPENSA")

        status, response = RequestGenerator.GET_account_transactions(account_id)

        assert status == 409
        assert response["code"] == "EB001006"
