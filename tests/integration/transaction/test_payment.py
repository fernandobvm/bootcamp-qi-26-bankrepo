from uuid import uuid4

from tests.utils import BankApi, PayloadGenerator, RequestGenerator


class TestPayment:
    def test_debits_without_fee(self):
        account_id = BankApi.create_account(balance="100.00")

        status, payment = RequestGenerator.POST_payment(account_id, PayloadGenerator.create_operation_payload("30.00"))

        assert status == 201
        assert payment["type"] == "PAYMENT"
        assert payment["value"] == "30.00"
        assert payment["balance_after"] == "70.00"
        assert BankApi.balance(account_id) == "70.00"
        assert BankApi.count_in_statement(account_id, "FEE") == 0

    def test_can_spend_the_whole_balance(self):
        account_id = BankApi.create_account(balance="100.00")

        status, payment = RequestGenerator.POST_payment(account_id, PayloadGenerator.create_operation_payload("100.00"))

        assert status == 201
        assert payment["balance_after"] == "0.00"

    def test_insufficient_balance_changes_nothing(self):
        account_id = BankApi.create_account(balance="100.00")

        status, response = RequestGenerator.POST_payment(account_id, PayloadGenerator.create_operation_payload("100.01"))

        assert status == 422
        assert response["code"] == "EB001008"
        assert response["balance"] == "100.00"
        assert BankApi.balance(account_id) == "100.00"

    def test_same_key_same_body_debits_once(self):
        account_id = BankApi.create_account(balance="100.00")
        payload = PayloadGenerator.create_operation_payload("30.00")

        first_status, first = RequestGenerator.POST_payment(account_id, payload)
        second_status, second = RequestGenerator.POST_payment(account_id, payload)

        assert first_status == second_status == 201
        assert second == first
        assert BankApi.balance(account_id) == "70.00"

    def test_one_key_is_one_operation(self):
        account_id = BankApi.create_account()
        key = str(uuid4())
        RequestGenerator.POST_deposit(account_id, PayloadGenerator.create_operation_payload("50.00", key))

        status, response = RequestGenerator.POST_payment(account_id, PayloadGenerator.create_operation_payload("50.00", key))

        assert status == 409
        assert response["code"] == "EB001007"
        assert BankApi.balance(account_id) == "50.00"

    def test_inactive_account_cannot_pay(self):
        account_id = BankApi.create_account(balance="100.00", status="SUSPENSA")

        status, response = RequestGenerator.POST_payment(account_id, PayloadGenerator.create_operation_payload("10.00"))

        assert status == 409
        assert response["code"] == "EB001006"

    def test_unknown_account_is_not_found(self):
        status, response = RequestGenerator.POST_payment(str(uuid4()), PayloadGenerator.create_operation_payload("10.00"))

        assert status == 404
        assert response["code"] == "EB001002"
