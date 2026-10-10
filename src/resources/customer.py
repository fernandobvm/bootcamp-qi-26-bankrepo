from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import CustomerController
from utils.schema_handler import SchemaHandler


class CustomerResource:
    """A porta de entrada HTTP do cadastro: confere o corpo, chama o controller."""

    @SchemaHandler.validate("post_customer.json")
    def on_post(self, payload: dict) -> JSONResponse:
        controller = CustomerController()
        customer = controller.create(payload)

        return JSONResponse(content=jsonable_encoder(customer), status_code=http_status.HTTP_201_CREATED)

    def on_get(self, customer_id: str) -> JSONResponse:
        controller = CustomerController()
        customer = controller.get(customer_id)

        return JSONResponse(content=jsonable_encoder(customer), status_code=http_status.HTTP_200_OK)
