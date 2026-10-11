from fastapi import FastAPI

from constants import check_variables
from errors import register_error_handlers
from errors.base_error import error_verification
from middlewares import (
    register_internal_token_middleware,
    register_request_context_middleware,
    register_request_logger_middleware,
    register_session_manager_middleware,
)
from resources import (
    AccountResource,
    CustomerResource,
    HealthCheckResource,
    SmoothingBoxResource,
    TransactionResource,
)
from utils.logger import setup_logging


def create_app() -> FastAPI:
    application = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    register_session_manager_middleware(application)
    register_internal_token_middleware(application)
    register_request_logger_middleware(application)
    register_request_context_middleware(application)

    health_check_resource = HealthCheckResource()

    application.add_api_route("/", health_check_resource.on_get_home, methods=["GET"])
    application.add_api_route(
        "/health_check",
        health_check_resource.on_get_health_check,
        methods=["GET"]
    )


    customer_resource = CustomerResource()
    account_resource = AccountResource()
    transaction_resource = TransactionResource()

    application.add_api_route(
        "/customers",
        customer_resource.on_post,
        methods=["POST"],
    )
    application.add_api_route(
        "/customers/{customer_id}",
        customer_resource.on_get,
        methods=["GET"],
    )
    application.add_api_route(
        "/accounts/{account_id}",
        account_resource.on_get,
        methods=["GET"],
    )
    application.add_api_route(
        "/accounts/{account_id}",
        account_resource.on_patch,
        methods=["PATCH"],
    )
    application.add_api_route(
        "/accounts/{account_id}/deposits",
        transaction_resource.on_post_deposit,
        methods=["POST"],
    )
    application.add_api_route(
        "/accounts/{account_id}/transfers",
        transaction_resource.on_post_transfer,
        methods=["POST"],
    )
    application.add_api_route(
        "/accounts/{account_id}/payments",
        transaction_resource.on_post_payment,
        methods=["POST"],
    )
    application.add_api_route(
        "/accounts/{account_id}/transactions",
        account_resource.on_get_transactions,
        methods=["GET"],
    )

    smoothing_box_resource = SmoothingBoxResource()

    application.add_api_route(
        "/accounts/{account_id}/smoothing-box",
        smoothing_box_resource.on_post,
        methods=["POST"],
    )
    application.add_api_route(
        "/accounts/{account_id}/smoothing-box",
        smoothing_box_resource.on_get,
        methods=["GET"],
    )
    application.add_api_route(
        "/accounts/{account_id}/smoothing-box",
        smoothing_box_resource.on_patch,
        methods=["PATCH"],
    )
    application.add_api_route(
        "/accounts/{account_id}/smoothing-box/closings",
        smoothing_box_resource.on_post_closing,
        methods=["POST"],
    )
    application.add_api_route(
        "/accounts/{account_id}/smoothing-box/closings",
        smoothing_box_resource.on_get_closings,
        methods=["GET"],
    )
    application.add_api_route(
        "/accounts/{account_id}/smoothing-box/withdrawals",
        smoothing_box_resource.on_post_withdrawal,
        methods=["POST"],
    )

    register_error_handlers(application)

    return application


def main() -> FastAPI:
    check_variables()
    error_verification()
    setup_logging()

    return create_app()


app = main()
