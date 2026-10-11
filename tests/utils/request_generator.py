from os import environ

from tests.utils.requisition import ClientRequisition, BaseConnectorResponse


INTERNAL_TOKEN = environ.get("INTERNAL_TOKEN", "default_token")


class RequestGenerator:
    # ── Banco: cliente, conta e transações ──────────────────────────

    @staticmethod
    def POST_customer(payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send("POST", "/customers", payload=payload, headers={"INTERNAL-TOKEN": INTERNAL_TOKEN})
        return response.response_status, response.response_json

    @staticmethod
    def GET_customer(customer_id: str) -> BaseConnectorResponse:
        response = ClientRequisition.send("GET", f"/customers/{customer_id}", headers={"INTERNAL-TOKEN": INTERNAL_TOKEN})
        return response.response_status, response.response_json

    @staticmethod
    def GET_account(account_id: str) -> BaseConnectorResponse:
        response = ClientRequisition.send("GET", f"/accounts/{account_id}", headers={"INTERNAL-TOKEN": INTERNAL_TOKEN})
        return response.response_status, response.response_json

    @staticmethod
    def PATCH_account(account_id: str, payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "PATCH", f"/accounts/{account_id}", payload=payload, headers={"INTERNAL-TOKEN": INTERNAL_TOKEN}
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_deposit(account_id: str, payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST", f"/accounts/{account_id}/deposits", payload=payload, headers={"INTERNAL-TOKEN": INTERNAL_TOKEN}
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_transfer(account_id: str, payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST", f"/accounts/{account_id}/transfers", payload=payload, headers={"INTERNAL-TOKEN": INTERNAL_TOKEN}
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_payment(account_id: str, payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST", f"/accounts/{account_id}/payments", payload=payload, headers={"INTERNAL-TOKEN": INTERNAL_TOKEN}
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_account_transactions(account_id: str, params: dict = None) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET",
            f"/accounts/{account_id}/transactions",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
            query_params=params,
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
