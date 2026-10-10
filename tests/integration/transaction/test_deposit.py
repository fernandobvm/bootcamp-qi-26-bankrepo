from uuid import uuid4

from tests.utils import BankApi, PayloadGenerator, RequestGenerator


class TestDeposit:
    def test_credits_the_account(self):
        account_id = BankApi.create_account()

        status, deposit = RequestGenerator.POST_deposit(account_id, PayloadGenerator.create_operation_payload("75.50"))

        assert status == 201
        assert deposit["type"] == "DEPOSIT"
        assert deposit["value"] == "75.50"
        assert deposit["balance_after"] == "75.50"
        assert BankApi.balance(account_id) == "75.50"

    def test_decimal_values_stay_exact(self):
        """0,10 + 0,20 tem que dar 0,30 — o teste que um float reprovaria."""
        account_id = BankApi.create_account()

        BankApi.deposit(account_id, "0.1")
        BankApi.deposit(account_id, "0.2")

        assert BankApi.balance(account_id) == "0.30"

    def test_same_key_same_body_credits_once(self):
        account_id = BankApi.create_account()
        payload = PayloadGenerator.create_operation_payload("50.00")

        first_status, first = RequestGenerator.POST_deposit(account_id, payload)
        second_status, second = RequestGenerator.POST_deposit(account_id, payload)

        assert first_status == second_status == 201
        assert second == first
        assert BankApi.balance(account_id) == "50.00"

    def test_same_key_other_body_is_conflict(self):
        account_id = BankApi.create_account()
        key = str(uuid4())
        RequestGenerator.POST_deposit(account_id, PayloadGenerator.create_operation_payload("50.00", key))

        status, response = RequestGenerator.POST_deposit(account_id, PayloadGenerator.create_operation_payload("60.00", key))

        assert status == 409
        assert response["code"] == "EB001007"
        assert BankApi.balance(account_id) == "50.00"

    def test_inactive_account_cannot_receive(self):
        account_id = BankApi.create_account(status="SUSPENSA")

        status, response = RequestGenerator.POST_deposit(account_id, PayloadGenerator.create_operation_payload("10.00"))

        assert status == 409
        assert response["code"] == "EB001006"

    def test_refuses_invalid_values(self):
        account_id = BankApi.create_account()

        for value in ["0", "0.00", "-1.00", "1.001", "abc", 50]:
            status, response = RequestGenerator.POST_deposit(account_id, PayloadGenerator.create_operation_payload(value))
            assert status == 400, f"value={value!r} deveria ser recusado"
            assert response["code"] == "EB000001"
