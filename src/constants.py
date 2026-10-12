import os
from decimal import Decimal


SERVICE_ROOT = os.path.abspath(os.path.dirname(__file__))
SCHEMA_PATH = os.path.join(SERVICE_ROOT, "schemas")
APP_ENV = os.environ.get("APP_ENV", "local")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "bootcamp-api")
DATABASE_URL = os.environ.get("DATABASE_URL")
INTERNAL_TOKEN = os.environ.get("INTERNAL_TOKEN")

BANK_TIMEZONE = "America/Sao_Paulo"

FREE_TRANSFERS_PER_MONTH = 5
TRANSFER_FEE_RATE = Decimal("0.01")
TRANSFER_FEE_MINIMUM = Decimal("1.00")

BYPASS_ENDPOINTS = [
    "/",
    "/health_check",
]

REQUIRED_VARIABLES = ["DATABASE_URL", "INTERNAL_TOKEN"]


def check_variables():
    missing = []
    for name in REQUIRED_VARIABLES:
        if not globals().get(name):
            missing.append(name)

    if missing:
        raise EnvironmentError(
            f"Faltam variáveis de ambiente: {', '.join(missing)}. "
            "Rodando com 'docker compose up' elas já vêm preenchidas. "
            "Fora do Docker, defina DATABASE_URL e INTERNAL_TOKEN no ambiente."
        )
