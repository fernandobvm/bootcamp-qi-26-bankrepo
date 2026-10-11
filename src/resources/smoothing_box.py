from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import SmoothingBoxController
from utils.schema_handler import SchemaHandler

DEFAULT_LIMIT = 10
DEFAULT_PAGE = 0


class SmoothingBoxResource:
    @SchemaHandler.validate("post_smoothing_box.json")
    def on_post(self, account_id: str, payload: dict) -> JSONResponse:
        controller = SmoothingBoxController()
        box = controller.create(account_id, payload)

        return JSONResponse(content=jsonable_encoder(box), status_code=http_status.HTTP_201_CREATED)

    def on_get(self, account_id: str) -> JSONResponse:
        controller = SmoothingBoxController()
        box = controller.get(account_id)

        return JSONResponse(content=jsonable_encoder(box), status_code=http_status.HTTP_200_OK)

    @SchemaHandler.validate("patch_smoothing_box.json")
    def on_patch(self, account_id: str, payload: dict) -> JSONResponse:
        controller = SmoothingBoxController()
        box = controller.update(account_id, payload)

        return JSONResponse(content=jsonable_encoder(box), status_code=http_status.HTTP_200_OK)

    @SchemaHandler.validate("post_smoothing_box_closing.json")
    def on_post_closing(self, account_id: str, payload: dict) -> JSONResponse:
        controller = SmoothingBoxController()
        closing, created = controller.close_day(account_id, payload["reference_date"])

        if created:
            status_code = http_status.HTTP_201_CREATED
        else:
            status_code = http_status.HTTP_200_OK

        return JSONResponse(content=jsonable_encoder(closing), status_code=status_code)

    @SchemaHandler.validate_query_params("get_smoothing_box_closings.json")
    def on_get_closings(self, account_id: str, request: Request) -> JSONResponse:
        controller = SmoothingBoxController()

        query_params = request.query_params

        limit = int(query_params.get("limit", DEFAULT_LIMIT))
        page = int(query_params.get("page", DEFAULT_PAGE))

        filters = {
            "start_date": query_params.get("start_date"),
            "end_date": query_params.get("end_date"),
        }

        closings_page = controller.list_closings(account_id, limit, page * limit, filters)

        page_envelope = {
            "data": closings_page["closings_list_dto"],
            "limit": limit,
            "page": page,
            "is_last_page": closings_page["is_last_page"],
        }

        return JSONResponse(content=jsonable_encoder(page_envelope), status_code=http_status.HTTP_200_OK)

    @SchemaHandler.validate("post_smoothing_box_withdrawal.json")
    def on_post_withdrawal(self, account_id: str, payload: dict) -> JSONResponse:
        controller = SmoothingBoxController()
        withdrawal = controller.withdraw(account_id, payload)

        return JSONResponse(content=jsonable_encoder(withdrawal), status_code=http_status.HTTP_201_CREATED)
