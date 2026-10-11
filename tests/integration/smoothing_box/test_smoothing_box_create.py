from uuid import uuid4

from tests.utils import BankSeed, RequestGenerator
from tests.utils.requisition import ClientRequisition


class TestSmoothingBoxCreate:
    def test_activates_with_default_retention(self):
        account_id = BankSeed.create_account()

        status, response = RequestGenerator.POST_smoothing_box(account_id)

        assert status == 201
        assert response["status"] == "ACTIVE"
        assert response["retention_pct"] == 50
        assert response["balance"] == "0.00"
        assert response["activated_on"] == BankSeed.today().isoformat()
        assert response["next_reference_date"] == BankSeed.today().isoformat()
        assert response["window_days"] == 0

    def test_activates_with_chosen_retention(self):
        account_id = BankSeed.create_account()

        status, response = RequestGenerator.POST_smoothing_box(account_id, {"retention_pct": 30})

        assert status == 201
        assert response["retention_pct"] == 30

    def test_refuses_retention_out_of_range(self):
        account_id = BankSeed.create_account()

        for retention_pct in [19, 81, 0, 100]:
            status, response = RequestGenerator.POST_smoothing_box(account_id, {"retention_pct": retention_pct})
            assert status == 400, f"retention_pct={retention_pct} deveria ser recusado"
            assert response["code"] == "EB000001"

    def test_refuses_unknown_field(self):
        account_id = BankSeed.create_account()

        status, response = RequestGenerator.POST_smoothing_box(account_id, {"retencao": 50})

        assert status == 400
        assert response["code"] == "EB000001"

    def test_second_activation_is_refused(self):
        """Repetir não cria outra: UNIQUE(account_id) e a trava na conta."""
        account_id = BankSeed.create_account()
        RequestGenerator.POST_smoothing_box(account_id)

        status, response = RequestGenerator.POST_smoothing_box(account_id)

        assert status == 409
        assert response["code"] == "EB002002"

    def test_unknown_account(self):
        for account_id in [str(uuid4()), "nao-e-um-uuid"]:
            status, response = RequestGenerator.POST_smoothing_box(account_id)
            assert status == 404
            assert response["code"] == "EB001002"

    def test_account_must_be_active(self):
        account_id = BankSeed.create_account(status="SUSPENSA")

        status, response = RequestGenerator.POST_smoothing_box(account_id)

        assert status == 409
        assert response["code"] == "EB001006"

    def test_requires_internal_token(self):
        account_id = BankSeed.create_account()

        response = ClientRequisition.send("POST", f"/accounts/{account_id}/smoothing-box", payload={})

        assert response.response_status == 403


class TestSmoothingBoxGetAndUpdate:
    def test_get_returns_the_box(self):
        account_id = BankSeed.create_account()
        RequestGenerator.POST_smoothing_box(account_id, {"retention_pct": 40})

        status, response = RequestGenerator.GET_smoothing_box(account_id)

        assert status == 200
        assert response["account_id"] == account_id
        assert response["retention_pct"] == 40
        assert response["last_closed_date"] is None

    def test_get_without_box(self):
        account_id = BankSeed.create_account()

        status, response = RequestGenerator.GET_smoothing_box(account_id)

        assert status == 404
        assert response["code"] == "EB002001"

    def test_pause_and_resume(self):
        account_id = BankSeed.create_account()
        RequestGenerator.POST_smoothing_box(account_id)

        status, response = RequestGenerator.PATCH_smoothing_box(account_id, {"status": "PAUSED"})
        assert status == 200
        assert response["status"] == "PAUSED"

        status, response = RequestGenerator.PATCH_smoothing_box(account_id, {"status": "ACTIVE", "retention_pct": 60})
        assert status == 200
        assert response["status"] == "ACTIVE"
        assert response["retention_pct"] == 60

    def test_patch_to_current_status_is_conflict(self):
        account_id = BankSeed.create_account()
        RequestGenerator.POST_smoothing_box(account_id)

        status, response = RequestGenerator.PATCH_smoothing_box(account_id, {"status": "ACTIVE"})

        assert status == 409
        assert response["code"] == "EB002006"

    def test_patch_refuses_empty_body_and_bad_values(self):
        account_id = BankSeed.create_account()
        RequestGenerator.POST_smoothing_box(account_id)

        for payload in [{}, {"status": "CLOSED"}, {"retention_pct": 90}]:
            status, response = RequestGenerator.PATCH_smoothing_box(account_id, payload)
            assert status == 400, f"{payload} deveria ser recusado"
            assert response["code"] == "EB000001"
