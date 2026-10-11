import time

from fastapi import FastAPI, Request

from constants import BYPASS_ENDPOINTS
from utils.logger import get_logger


logger = get_logger(__name__)


def register_request_logger_middleware(application: FastAPI) -> None:
    @application.middleware("http")
    async def log_request(request: Request, call_next):
        if request.url.path in BYPASS_ENDPOINTS:
            return await call_next(request)

        # O que veio depois do "?" no endereço entra no log de entrada:
        # é metade do pedido, e sem ele a linha "GET /accounts/{id}/transactions"
        # não diz qual página alguém pediu.
        #
        # E fica a lição pelo avesso: se a query string vai parar no
        # log, ela NÃO é lugar para segredo. Um token na URL acaba
        # gravado aqui, no histórico do navegador e no log de todo proxy
        # do caminho. Segredo viaja em cabeçalho, como o INTERNAL-TOKEN.
        requested_path = request.url.path
        if request.url.query:
            requested_path = f"{requested_path}?{request.url.query}"

        started_at = time.perf_counter()
        logger.info(f"ENTROU {request.method} {requested_path}")

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.info(f"SAIU {response.status_code} {request.method} {request.url.path} - {elapsed_ms:.1f} ms")

        return response
