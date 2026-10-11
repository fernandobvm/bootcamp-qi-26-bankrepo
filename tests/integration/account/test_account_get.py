from uuid import uuid4

from tests.utils import BankApi, PayloadGenerator, RequestGenerator


class TestAccountGet:
    def test_returns_balance_and_status(self):
        account_id = BankApi.create_account(balance="150.75")

        status, account = RequestGenerator.GET_account(account_id)

        assert status == 200
        assert account["account_id"] == account_id
        assert account["balance"] == "150.75"
        assert account["status"] == "ATIVA"

    def test_unknown_account_is_not_found(self):
        for account_id in [str(uuid4()), "nao-e-um-uuid"]:
            status, response = RequestGenerator.GET_account(account_id)

            assert status == 404, account_id
            assert response["code"] == "EB001002"

    def test_account_only_exists_with_a_customer(self):
        invented_account_id = str(uuid4())

        status, response = RequestGenerator.POST_deposit(
            invented_account_id, PayloadGenerator.create_operation_payload("10.00")
        )
        assert status == 404
        assert response["code"] == "EB001002"

        status, _ = RequestGenerator.GET_account(invented_account_id)
        assert status == 404
