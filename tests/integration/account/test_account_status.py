from decimal import Decimal

from tests.utils import BankApi, BankSeed, RequestGenerator


class TestAccountStatus:
    def test_suspends_and_reactivates(self):
        account_id = BankApi.create_account()

        status, account = RequestGenerator.PATCH_account(account_id, {"status": "SUSPENSA"})
        assert status == 200
        assert account["status"] == "SUSPENSA"

        status, account = RequestGenerator.PATCH_account(account_id, {"status": "ATIVA"})
        assert status == 200
        assert account["status"] == "ATIVA"

    def test_same_status_is_conflict(self):
        account_id = BankApi.create_account()

        status, response = RequestGenerator.PATCH_account(account_id, {"status": "ATIVA"})

        assert status == 409
        assert response["code"] == "EB001010"

    def test_closed_account_never_reopens(self):
        account_id = BankApi.create_account()

        status, account = RequestGenerator.PATCH_account(account_id, {"status": "ENCERRADA"})
        assert status == 200
        assert account["status"] == "ENCERRADA"

        for new_status in ["ATIVA", "SUSPENSA"]:
            status, response = RequestGenerator.PATCH_account(account_id, {"status": new_status})
            assert status == 409, new_status
            assert response["code"] == "EB001010"

    def test_cannot_close_with_money_in_the_account(self):
        account_id = BankApi.create_account(balance="10.00")

        status, response = RequestGenerator.PATCH_account(account_id, {"status": "ENCERRADA"})

        assert status == 422
        assert response["code"] == "EB001011"
        assert response["balance"] == "10.00"
        assert BankApi.balance(account_id) == "10.00"

    def test_cannot_close_with_money_in_the_smoothing_box(self):
        account_id = BankApi.create_account()
        BankSeed.create_box(account_id, BankApi.today(), balance=Decimal("25.00"))

        status, response = RequestGenerator.PATCH_account(account_id, {"status": "ENCERRADA"})

        assert status == 422
        assert response["code"] == "EB001011"
        assert response["box_balance"] == "25.00"

    def test_refuses_unknown_status(self):
        account_id = BankApi.create_account()

        for payload in [{"status": "BLOQUEADA"}, {}, {"status": "ATIVA", "balance": "0"}]:
            status, response = RequestGenerator.PATCH_account(account_id, payload)
            assert status == 400, payload
            assert response["code"] == "EB000001"
