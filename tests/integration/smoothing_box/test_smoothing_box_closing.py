from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

from tests.utils import BankSeed, RequestGenerator

# Catorze dias de R$ 200: o aquecimento inteiro, com média redonda.
WARMUP = ["200.00"] * 14


def close_all(account_id: str, days: list) -> list:
    """Fecha os dias em ordem, como o agendador faria, e devolve os fechamentos."""
    closings = []

    for day in days:
        status, response = RequestGenerator.POST_smoothing_box_closing(account_id, day.isoformat())
        assert status == 201, response
        closings.append(response)

    return closings


class TestClosingBands:
    def test_warmup_records_income_and_moves_nothing(self):
        account_id, days = BankSeed.build_history(WARMUP)

        closings = close_all(account_id, days)

        for closing in closings:
            assert closing["band"] == "WARMUP"
            assert closing["income"] == "200.00"
            assert closing["amount_moved"] == "0.00"
            assert closing["transaction_id"] is None

        # O 14º dia ainda é aquecimento: a média dele tem só 13 dias atrás.
        assert closings[-1]["window_days"] == 13

    def test_above_retains_half_of_what_passed_the_ceiling(self):
        """O exemplo do RFC: média 200, teto 220, renda 400 → guarda (400 − 220) × 50% = 90."""
        account_id, days = BankSeed.build_history(WARMUP + ["400.00"], account_balance=Decimal("1000.00"))

        closing = close_all(account_id, days)[-1]

        assert closing["band"] == "ABOVE"
        assert closing["window_days"] == 14
        assert closing["baseline"] == "200.00"
        assert closing["upper_bound"] == "220.00"
        assert closing["lower_bound"] == "180.00"
        assert closing["amount_calculated"] == "90.00"
        assert closing["amount_moved"] == "90.00"
        assert closing["transaction_id"] is not None

        status, box = RequestGenerator.GET_smoothing_box(account_id)
        assert box["balance"] == "90.00"

    def test_below_releases_up_to_the_floor_limited_by_the_box(self):
        """Dia fraco depois de um dia forte: a caixinha devolve o que tem.

        Média dos 15 dias = 3200 / 15 = 213,333… → 213,33 (para baixo).
        Piso = 213,33 × 0,90 = 191,997 → 191,99. Faltam 91,99 para o piso,
        mas a caixinha só guardou 90,00: move 90,00.
        """
        account_id, days = BankSeed.build_history(WARMUP + ["400.00", "100.00"], account_balance=Decimal("1000.00"))

        closing = close_all(account_id, days)[-1]

        assert closing["band"] == "BELOW"
        assert closing["baseline"] == "213.33"
        assert closing["lower_bound"] == "191.99"
        assert closing["amount_calculated"] == "91.99"
        assert closing["amount_moved"] == "90.00"

        status, box = RequestGenerator.GET_smoothing_box(account_id)
        assert box["balance"] == "0.00"

    def test_day_off_counts_as_zero_income(self):
        """Folga é renda zero, e a caixinha existe para ela."""
        account_id, days = BankSeed.build_history(
            WARMUP + ["0.00"], account_balance=Decimal("1000.00"), box_balance=Decimal("500.00")
        )

        closing = close_all(account_id, days)[-1]

        assert closing["income"] == "0.00"
        assert closing["band"] == "BELOW"
        assert closing["amount_moved"] == "180.00"

    def test_inside_the_band_is_neutral(self):
        account_id, days = BankSeed.build_history(WARMUP + ["215.00"])

        closing = close_all(account_id, days)[-1]

        assert closing["band"] == "NEUTRAL"
        assert closing["amount_moved"] == "0.00"

    def test_box_movements_are_not_income(self):
        """Dinheiro que volta da própria caixinha não é renda.

        A liberação do fechamento de um dia cai na conta no dia SEGUINTE
        (o fechamento roda depois que o dia acaba), e o resgate pode
        acontecer a qualquer hora. Se esses créditos contassem, cada
        liberação inflaria a média e puxaria a próxima retenção.
        """
        account_id, days = BankSeed.build_history(WARMUP + ["100.00"])
        BankSeed.add_credit(account_id, days[-1], Decimal("50.00"), "BOX_RELEASE")
        BankSeed.add_credit(account_id, days[-1], Decimal("30.00"), "BOX_WITHDRAWAL")

        closing = close_all(account_id, days)[-1]

        assert closing["income"] == "100.00"

    def test_day_follows_sao_paulo_clock(self):
        """Crédito às 22h de São Paulo é do dia em São Paulo, mesmo já sendo o dia seguinte em UTC."""
        account_id, days = BankSeed.build_history(WARMUP + ["0.00", "0.00"])
        BankSeed.add_credit(account_id, days[-2], Decimal("75.00"), "TRANSFER", hour=22)

        closings = close_all(account_id, days)

        assert closings[-2]["income"] == "75.00"
        assert closings[-1]["income"] == "0.00"


class TestClosingLimits:
    def test_retention_limited_by_account_balance(self):
        """A regra pede 90, mas o cliente já gastou e a conta tem 30: move 30."""
        account_id, days = BankSeed.build_history(WARMUP + ["400.00"], account_balance=Decimal("30.00"))

        closing = close_all(account_id, days)[-1]

        assert closing["amount_calculated"] == "90.00"
        assert closing["amount_moved"] == "30.00"

    def test_empty_account_moves_nothing(self):
        account_id, days = BankSeed.build_history(WARMUP + ["400.00"], account_balance=Decimal("0.00"))

        closing = close_all(account_id, days)[-1]

        assert closing["band"] == "ABOVE"
        assert closing["amount_moved"] == "0.00"
        assert closing["transaction_id"] is None

    def test_retention_stops_at_ten_times_the_baseline(self):
        """Caixinha com 1.990 e média 200: só cabem 10 até o limite de 2.000."""
        account_id, days = BankSeed.build_history(
            WARMUP + ["400.00"], account_balance=Decimal("1000.00"), box_balance=Decimal("1990.00")
        )

        closing = close_all(account_id, days)[-1]

        assert closing["amount_calculated"] == "90.00"
        assert closing["amount_moved"] == "10.00"

    def test_paused_box_records_but_moves_nothing(self):
        account_id, days = BankSeed.build_history(WARMUP + ["400.00"])
        close_all(account_id, days[:-1])
        RequestGenerator.PATCH_smoothing_box(account_id, {"status": "PAUSED"})

        status, closing = RequestGenerator.POST_smoothing_box_closing(account_id, days[-1].isoformat())

        assert status == 201
        assert closing["band"] == "PAUSED"
        assert closing["income"] == "400.00"
        assert closing["baseline"] == "200.00"
        assert closing["amount_moved"] == "0.00"

    def test_retention_percentage_is_applied(self):
        account_id, days = BankSeed.build_history(WARMUP + ["400.00"], retention_pct=20)

        closing = close_all(account_id, days)[-1]

        # (400 − 220) × 20% = 36
        assert closing["amount_moved"] == "36.00"

    def test_rounding_is_always_down(self):
        """(220,03 − 220,00) × 50% = 0,015 → 0,01, nunca 0,02."""
        account_id, days = BankSeed.build_history(WARMUP + ["220.03"])

        closing = close_all(account_id, days)[-1]

        assert closing["band"] == "ABOVE"
        assert closing["amount_calculated"] == "0.01"


class TestClosingIdempotency:
    def test_repeating_a_closed_day_returns_200_and_moves_nothing(self):
        account_id, days = BankSeed.build_history(WARMUP + ["400.00"], account_balance=Decimal("1000.00"))
        first = close_all(account_id, days)[-1]

        status, again = RequestGenerator.POST_smoothing_box_closing(account_id, days[-1].isoformat())

        assert status == 200
        assert again == first
        assert BankSeed.count_transactions(account_id, "BOX_RETENTION") == 1

        status, box = RequestGenerator.GET_smoothing_box(account_id)
        assert box["balance"] == "90.00"

    def test_concurrent_closings_of_the_same_day_move_money_once(self):
        """O agendador dispara duas vezes ao mesmo tempo: um 201, os outros 200, uma retenção."""
        account_id, days = BankSeed.build_history(WARMUP + ["400.00"], account_balance=Decimal("1000.00"))
        close_all(account_id, days[:-1])

        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(
                pool.map(
                    lambda _: RequestGenerator.POST_smoothing_box_closing(account_id, days[-1].isoformat()),
                    range(5),
                )
            )

        statuses = sorted(status for status, _ in results)
        assert statuses == [200, 200, 200, 200, 201]

        closing_keys = {response["closing_key"] for _, response in results}
        assert len(closing_keys) == 1

        assert BankSeed.count_transactions(account_id, "BOX_RETENTION") == 1

        status, box = RequestGenerator.GET_smoothing_box(account_id)
        assert box["balance"] == "90.00"


class TestClosingRefusals:
    def test_previous_day_must_be_closed(self):
        account_id, days = BankSeed.build_history(["200.00"] * 3)

        status, response = RequestGenerator.POST_smoothing_box_closing(account_id, days[2].isoformat())

        assert status == 409
        assert response["code"] == "EB002004"
        assert response["next_reference_date"] == days[0].isoformat()

    def test_today_cannot_be_closed(self):
        account_id, days = BankSeed.build_history(["200.00"])

        status, response = RequestGenerator.POST_smoothing_box_closing(account_id, BankSeed.today().isoformat())

        assert status == 422
        assert response["code"] == "EB002005"

    def test_day_before_activation_cannot_be_closed(self):
        account_id, days = BankSeed.build_history(["200.00"] * 2)
        day_before = days[0] - timedelta(days=1)

        status, response = RequestGenerator.POST_smoothing_box_closing(account_id, day_before.isoformat())

        assert status == 422
        assert response["code"] == "EB002005"

    def test_impossible_date_is_bad_request(self):
        account_id, days = BankSeed.build_history(["200.00"])

        for reference_date in ["2026-02-30", "02/10/2026"]:
            status, response = RequestGenerator.POST_smoothing_box_closing(account_id, reference_date)
            assert status == 400, reference_date
            assert response["code"] == "QIT000001"

    def test_inactive_account_cannot_close(self):
        account_id, days = BankSeed.build_history(["200.00"])
        BankSeed.set_account(account_id, status="SUSPENSA")

        status, response = RequestGenerator.POST_smoothing_box_closing(account_id, days[0].isoformat())

        assert status == 409
        assert response["code"] == "EB002003"

    def test_account_without_box(self):
        account_id = BankSeed.create_account()

        status, response = RequestGenerator.POST_smoothing_box_closing(account_id, "2026-01-01")

        assert status == 404
        assert response["code"] == "EB002001"
