from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from tests.utils.payload_generator import PayloadGenerator
from tests.utils.request_generator import RequestGenerator

BANK_TIMEZONE = "America/Sao_Paulo"


class BankApi:
    """Prepara o cenário dos testes PELA API — a porta da frente.

    É o combinado do projeto (D3T p.15): o teste cria o mundo de que
    precisa com as mesmas rotas que um cliente usaria. Se uma dessas
    rotas quebrar, o teste quebra junto, e isso é o que se quer: o
    cenário nunca existe num estado que a API não saberia produzir.

    Cada passo confere o próprio status e para na hora se não deu certo,
    com a resposta na mensagem. Assim um teste vermelho aponta para a
    preparação quebrada, e não para uma asserção lá na frente que só
    falhou por consequência.
    """

    @staticmethod
    def create_customer() -> dict:
        status, customer = RequestGenerator.POST_customer(PayloadGenerator.create_customer_payload())
        assert status == 201, f"POST /customers respondeu {status}: {customer}"
        return customer

    @staticmethod
    def create_account(balance: Decimal = Decimal("0.00"), status: str = "ATIVA") -> str:
        """Um cliente novo, a conta dele, um depósito do saldo pedido e o status pedido."""
        account_id = BankApi.create_customer()["account_id"]

        if Decimal(balance) > 0:
            BankApi.deposit(account_id, f"{Decimal(balance):.2f}")

        if status != "ATIVA":
            BankApi.set_status(account_id, status)

        return account_id

    @staticmethod
    def deposit(account_id: str, value: str) -> dict:
        status, deposit = RequestGenerator.POST_deposit(account_id, PayloadGenerator.create_operation_payload(value))
        assert status == 201, f"POST deposits respondeu {status}: {deposit}"
        return deposit

    @staticmethod
    def set_status(account_id: str, status: str) -> None:
        response_status, account = RequestGenerator.PATCH_account(account_id, {"status": status})
        assert response_status == 200, f"PATCH /accounts respondeu {response_status}: {account}"

    @staticmethod
    def balance(account_id: str) -> str:
        status, account = RequestGenerator.GET_account(account_id)
        assert status == 200, f"GET /accounts respondeu {status}: {account}"
        return account["balance"]

    @staticmethod
    def statement(account_id: str) -> list:
        """O extrato inteiro de uma conta de teste (cabe numa página de 100)."""
        status, page = RequestGenerator.GET_account_transactions(account_id, {"limit": "100"})
        assert status == 200, f"GET transactions respondeu {status}: {page}"
        assert page["is_last_page"], "o extrato desta conta passou de 100 linhas"
        return page["data"]

    @staticmethod
    def count_in_statement(account_id: str, transaction_type: str) -> int:
        count = 0
        for entry in BankApi.statement(account_id):
            if entry["type"] == transaction_type:
                count = count + 1
        return count

    @staticmethod
    def today() -> date:
        """O "hoje" do banco, calculado aqui mesmo no fuso de São Paulo.

        Não pergunta ao banco de dados: o teste black box não lê o banco.
        A API usa o mesmo fuso (constants.BANK_TIMEZONE), então os dois
        concordam — fora a corrida de rodar o teste exatamente à meia-noite.
        """
        return datetime.now(ZoneInfo(BANK_TIMEZONE)).date()
