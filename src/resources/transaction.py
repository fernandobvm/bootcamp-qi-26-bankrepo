from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import TransactionController
from utils.schema_handler import SchemaHandler


class TransactionResource:
    """Depósito, transferência e pagamento.

    As três respondem 201 também no reenvio com a mesma chave, com o
    corpo da primeira vez: para quem chamou, o pedido deu certo uma vez
    só, não importa quantas vezes ele foi mandado.
    """

    @SchemaHandler.validate("post_deposit.json")
    def on_post_deposit(self, account_id: str, payload: dict) -> JSONResponse:
        controller = TransactionController()
        deposit = controller.deposit(account_id, payload)

        return JSONResponse(content=jsonable_encoder(deposit), status_code=http_status.HTTP_201_CREATED)

    @SchemaHandler.validate("post_transfer.json")
    def on_post_transfer(self, account_id: str, payload: dict) -> JSONResponse:
        controller = TransactionController()
        transfer = controller.transfer(account_id, payload)

        return JSONResponse(content=jsonable_encoder(transfer), status_code=http_status.HTTP_201_CREATED)

    @SchemaHandler.validate("post_payment.json")
    def on_post_payment(self, account_id: str, payload: dict) -> JSONResponse:
        controller = TransactionController()
        payment = controller.payment(account_id, payload)

        return JSONResponse(content=jsonable_encoder(payment), status_code=http_status.HTTP_201_CREATED)
