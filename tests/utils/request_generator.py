from os import environ

from tests.utils.requisition import ClientRequisition, BaseConnectorResponse


INTERNAL_TOKEN = environ.get("INTERNAL_TOKEN", "default_token")


class RequestGenerator:
    @staticmethod
    def POST_sample_entity(sample_entity_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST",
            "/sample_entity",
            payload=sample_entity_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )

        return response.response_status, response.response_json

    @staticmethod
    def GET_sample_entity(sample_entity_key: str) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET",
            f"/sample_entity/{sample_entity_key}",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def PUT_sample_entity(sample_entity_key: str, update_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "PUT",
            f"/sample_entity/{sample_entity_key}",
            payload=update_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def PUT_webhook_sample_entity(sample_entity_key: str) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "PUT",
            f"/webhook/sample_entity/{sample_entity_key}/increment_counter",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_sample_entities(params: dict = None) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET", "/sample_entities", headers={"INTERNAL-TOKEN": INTERNAL_TOKEN}, query_params=params
        )
        return response.response_status, response.response_json

    # ── Caixinha de Equilíbrio ──────────────────────────────────────

    @staticmethod
    def POST_smoothing_box(account_id: str, payload: dict = None) -> BaseConnectorResponse:
        if payload is None:
            payload = {}
        response = ClientRequisition.send(
            "POST", f"/accounts/{account_id}/smoothing-box", payload=payload, headers={"INTERNAL-TOKEN": INTERNAL_TOKEN}
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_smoothing_box(account_id: str) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET", f"/accounts/{account_id}/smoothing-box", headers={"INTERNAL-TOKEN": INTERNAL_TOKEN}
        )
        return response.response_status, response.response_json

    @staticmethod
    def PATCH_smoothing_box(account_id: str, payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "PATCH", f"/accounts/{account_id}/smoothing-box", payload=payload, headers={"INTERNAL-TOKEN": INTERNAL_TOKEN}
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_smoothing_box_closing(account_id: str, reference_date: str) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST",
            f"/accounts/{account_id}/smoothing-box/closings",
            payload={"reference_date": reference_date},
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_smoothing_box_closings(account_id: str, params: dict = None) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET",
            f"/accounts/{account_id}/smoothing-box/closings",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
            query_params=params,
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_smoothing_box_withdrawal(account_id: str, payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST",
            f"/accounts/{account_id}/smoothing-box/withdrawals",
            payload=payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json
