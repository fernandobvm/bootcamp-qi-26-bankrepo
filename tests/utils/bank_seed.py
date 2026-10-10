from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine, text

from tests.utils.bank_api import BankApi
from tests.utils.db_utils import DbUtils
from tests.utils.request_generator import RequestGenerator


class BankSeed:
    """Monta, direto no banco, o PASSADO que a caixinha precisa encontrar.

    ────────────────────────────────────────────────────────────────
    POR QUE ESTES TESTES NÃO ENTRAM SÓ "PELA PORTA DA FRENTE"
    ────────────────────────────────────────────────────────────────
    O combinado do projeto é preparar o teste pelas rotas da API, e o
    que dá para fazer assim já é feito assim: cliente, conta, saldo e
    status nascem pelo `BankApi` (POST /customers, depósito, PATCH).

    O que sobra aqui é o que nenhuma rota cria — e não deveria criar: a
    caixinha trabalha com o PASSADO. Renda de 15 dias atrás, uma
    caixinha ativada há duas semanas, um saldo de caixinha que só um mês
    de fechamentos produziria. Esses INSERTs são a exceção, e só na
    PREPARAÇÃO: a ação e a conferência continuam sendo requisições HTTP.
    """

    _platform_account_id = None

    @staticmethod
    def _engine():
        return create_engine(DbUtils.database_url())

    @staticmethod
    def today() -> date:
        """O "hoje" do banco, no fuso de São Paulo — o mesmo que a API usa."""
        engine = BankSeed._engine()
        try:
            with engine.connect() as connection:
                return connection.execute(text("SELECT (NOW() AT TIME ZONE 'America/Sao_Paulo')::date")).scalar_one()
        finally:
            engine.dispose()

    @staticmethod
    def create_account(balance: Decimal = Decimal("0.00"), status: str = "ATIVA") -> str:
        """A conta nasce pela API; o nome continua aqui para os testes da caixinha."""
        return BankApi.create_account(balance=balance, status=status)

    @staticmethod
    def set_account(account_id: str, balance: Decimal = None, status: str = None) -> None:
        engine = BankSeed._engine()
        try:
            with engine.begin() as connection:
                if balance is not None:
                    connection.execute(text("UPDATE account SET balance = :b WHERE id = :id"), {"b": balance, "id": account_id})
                if status is not None:
                    connection.execute(text("UPDATE account SET status = :s WHERE id = :id"), {"s": status, "id": account_id})
        finally:
            engine.dispose()

    @staticmethod
    def add_income(account_id: str, day: date, value: Decimal, hour: int = 12) -> None:
        """Um crédito de renda na conta, às `hour` horas de São Paulo do dia `day`.

        Vem de uma conta "plataforma" (o app de entrega pagando o
        entregador), como uma transferência comum. O saldo da conta não é
        mexido aqui: quem precisa de um saldo específico usa
        `set_account`, e o teste fica dizendo em voz alta de quanto é.
        """
        BankSeed.add_credit(account_id, day, value, "TRANSFER", hour)

    @staticmethod
    def add_credit(account_id: str, day: date, value: Decimal, transaction_type: str, hour: int = 12) -> None:
        """Um crédito de qualquer tipo. Nos tipos da caixinha, a origem é a própria conta."""
        if transaction_type.startswith("BOX_"):
            out_id, in_id = account_id, None
        else:
            out_id, in_id = BankSeed._platform_account(), account_id

        engine = BankSeed._engine()
        try:
            with engine.begin() as connection:
                transaction_id = connection.execute(
                    text(
                        "INSERT INTO transaction (type, account_out_id, account_in_id, value, idempotency_key, request_hash, created_at) "
                        "VALUES (:type, :out_id, :in_id, :value, :key, :hash, "
                        "(CAST(:day AS date) + make_interval(hours => :hour)) AT TIME ZONE 'America/Sao_Paulo') RETURNING id"
                    ),
                    {
                        "type": transaction_type,
                        "out_id": out_id,
                        "in_id": in_id,
                        "value": value,
                        "key": str(uuid4()),
                        "hash": "0" * 64,
                        "day": day,
                        "hour": hour,
                    },
                ).scalar_one()

                connection.execute(
                    text(
                        "INSERT INTO ledger_entry (transaction_id, account_id, direction, value, balance_after, created_at) "
                        "VALUES (:transaction_id, :account_id, 'CREDITO', :value, 0, "
                        "(CAST(:day AS date) + make_interval(hours => :hour)) AT TIME ZONE 'America/Sao_Paulo')"
                    ),
                    {"transaction_id": transaction_id, "account_id": account_id, "value": value, "day": day, "hour": hour},
                )
        finally:
            engine.dispose()

    @staticmethod
    def create_box(
        account_id: str,
        activated_on: date,
        retention_pct: int = 50,
        balance: Decimal = Decimal("0.00"),
        status: str = "ACTIVE",
    ) -> None:
        """Uma caixinha já ativada no passado — o POST só ativaria com data de hoje."""
        engine = BankSeed._engine()
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO smoothing_box (account_id, balance, retention_pct, status, activated_on) "
                        "VALUES (:account_id, :balance, :pct, :status, :activated_on)"
                    ),
                    {
                        "account_id": account_id,
                        "balance": balance,
                        "pct": retention_pct,
                        "status": status,
                        "activated_on": activated_on,
                    },
                )
        finally:
            engine.dispose()

    @staticmethod
    def build_history(
        incomes: list,
        account_balance: Decimal = Decimal("10000.00"),
        box_balance: Decimal = Decimal("0.00"),
        retention_pct: int = 50,
    ) -> tuple:
        """Conta + caixinha ativada há `len(incomes)` dias, com uma renda por dia.

        O último item de `incomes` é a renda de ONTEM — o dia mais recente
        que já pode ser fechado. Devolve a conta e a lista de dias, na
        mesma ordem das rendas.
        """
        today = BankSeed.today()
        days = [today - timedelta(days=len(incomes) - i) for i in range(len(incomes))]

        account_id = BankSeed.create_account(balance=account_balance)
        BankSeed.create_box(account_id, days[0], retention_pct=retention_pct, balance=box_balance)

        for day, income in zip(days, incomes):
            if Decimal(income) > 0:
                BankSeed.add_income(account_id, day, Decimal(income))

        return account_id, days

    @staticmethod
    def _platform_account() -> str:
        # Uma conta "plataforma" por processo de teste. Se o banco foi
        # recriado no meio (DbUtils.rollback), ela some — então confere.
        if BankSeed._platform_account_id is not None:
            status, _ = RequestGenerator.GET_account(BankSeed._platform_account_id)
            if status == 200:
                return BankSeed._platform_account_id

        BankSeed._platform_account_id = BankSeed.create_account()
        return BankSeed._platform_account_id
