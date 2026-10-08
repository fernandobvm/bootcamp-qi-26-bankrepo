from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

from tests.utils import BankSeed, RequestGenerator


def account_with_box(box_balance: str, account_balance: str = "100.00") -> str:
    account_id = BankSeed.create_account(balance=Decimal(account_balance))
    BankSeed.create_box(account_id, BankSeed.today(), balance=Decimal(box_balance))
    return account_id


class TestWithdrawal:
    def test_moves_money_from_box_to_account(self):
        account_id = account_with_box("150.00", account_balance="100.00")

        status, response = RequestGenerator.POST_smoothing_box_withdrawal(
            account_id, {"value": "50.00", "idempotency_key": str(uuid4())}
        )

        assert status == 201
        assert response["value"] == "50.00"
        assert response["box_balance"] == "100.00"
        assert response["account_balance"] == "150.00"

    def test_decimal_values_stay_exact(self):
        """0,10 + 0,20 tem que dar 0,30 — o teste que um float reprovaria."""
        account_id = account_with_box("1.00", account_balance="0.00")

        RequestGenerator.POST_smoothing_box_withdrawal(account_id, {"value": "0.1", "idempotency_key": str(uuid4())})
        status, response = RequestGenerator.POST_smoothing_box_withdrawal(
            account_id, {"value": "0.2", "idempotency_key": str(uuid4())}
        )

        assert status == 201
        assert response["account_balance"] == "0.30"
        assert response["box_balance"] == "0.70"

    def test_same_key_same_body_returns_the_original(self):
        account_id = account_with_box("150.00")
        payload = {"value": "50.00", "idempotency_key": str(uuid4())}

        first_status, first = RequestGenerator.POST_smoothing_box_withdrawal(account_id, payload)
        second_status, second = RequestGenerator.POST_smoothing_box_withdrawal(account_id, payload)

        assert first_status == second_status == 201
        assert second == first
        assert BankSeed.count_transactions(account_id, "BOX_WITHDRAWAL") == 1

    def test_same_amount_written_differently_is_the_same_request(self):
        account_id = account_with_box("150.00")
        key = str(uuid4())

        RequestGenerator.POST_smoothing_box_withdrawal(account_id, {"value": "50", "idempotency_key": key})
        status, _ = RequestGenerator.POST_smoothing_box_withdrawal(account_id, {"value": "50.00", "idempotency_key": key})

        assert status == 201
        assert BankSeed.count_transactions(account_id, "BOX_WITHDRAWAL") == 1

    def test_same_key_other_body_is_conflict(self):
        account_id = account_with_box("150.00")
        key = str(uuid4())
        RequestGenerator.POST_smoothing_box_withdrawal(account_id, {"value": "50.00", "idempotency_key": key})

        status, response = RequestGenerator.POST_smoothing_box_withdrawal(
            account_id, {"value": "60.00", "idempotency_key": key}
        )

        assert status == 409
        assert response["code"] == "EB002007"

    def test_insufficient_box_balance(self):
        account_id = account_with_box("40.00")

        status, response = RequestGenerator.POST_smoothing_box_withdrawal(
            account_id, {"value": "100.00", "idempotency_key": str(uuid4())}
        )

        assert status == 422
        assert response["code"] == "EB002006"
        assert response["box_balance"] == "40.00"

    def test_concurrent_withdrawals_never_go_negative(self):
        """Cinco pedidos de 30 numa caixinha de 100: só três cabem."""
        account_id = account_with_box("100.00")

        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(
                pool.map(
                    lambda _: RequestGenerator.POST_smoothing_box_withdrawal(
                        account_id, {"value": "30.00", "idempotency_key": str(uuid4())}
                    ),
                    range(5),
                )
            )

        statuses = sorted(status for status, _ in results)
        assert statuses == [201, 201, 201, 422, 422]

        status, box = RequestGenerator.GET_smoothing_box(account_id)
        assert box["balance"] == "10.00"

    def test_refuses_invalid_values(self):
        account_id = account_with_box("100.00")

        for value in ["0", "0.00", "-1.00", "1.001", "abc", 50]:
            status, response = RequestGenerator.POST_smoothing_box_withdrawal(
                account_id, {"value": value, "idempotency_key": str(uuid4())}
            )
            assert status == 400, f"value={value!r} deveria ser recusado"
            assert response["code"] == "QIT000001"

    def test_requires_idempotency_key(self):
        account_id = account_with_box("100.00")

        status, response = RequestGenerator.POST_smoothing_box_withdrawal(account_id, {"value": "10.00"})

        assert status == 400

    def test_inactive_account_cannot_withdraw(self):
        account_id = account_with_box("100.00")
        BankSeed.set_account(account_id, status="SUSPENSA")

        status, response = RequestGenerator.POST_smoothing_box_withdrawal(
            account_id, {"value": "10.00", "idempotency_key": str(uuid4())}
        )

        assert status == 409
        assert response["code"] == "EB002003"
