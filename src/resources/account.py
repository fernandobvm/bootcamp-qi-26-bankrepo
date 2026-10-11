from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import AccountController
from utils.schema_handler import SchemaHandler

DEFAULT_LIMIT = 10
DEFAULT_PAGE = 0


class AccountResource:
    def on_get(self, account_id: str) -> JSONResponse:
        controller = AccountController()
        account = controller.get(account_id)

        return JSONResponse(content=jsonable_encoder(account), status_code=http_status.HTTP_200_OK)

    @SchemaHandler.validate("patch_account.json")
    def on_patch(self, account_id: str, payload: dict) -> JSONResponse:
        controller = AccountController()
        account = controller.update_status(account_id, payload)

        return JSONResponse(content=jsonable_encoder(account), status_code=http_status.HTTP_200_OK)

    @SchemaHandler.validate_query_params("get_account_transactions.json")
    def on_get_transactions(self, account_id: str, request: Request) -> JSONResponse:
        controller = AccountController()

        query_params = request.query_params

        limit = int(query_params.get("limit", DEFAULT_LIMIT))
        page = int(query_params.get("page", DEFAULT_PAGE))

        filters = {
            "start_date": query_params.get("start_date"),
            "end_date": query_params.get("end_date"),
        }

        statement_page = controller.list_statement(account_id, limit, page * limit, filters)

        page_envelope = {
            "data": statement_page["statement_list_dto"],
            "limit": limit,
            "page": page,
            "is_last_page": statement_page["is_last_page"],
        }

        return JSONResponse(content=jsonable_encoder(page_envelope), status_code=http_status.HTTP_200_OK)
