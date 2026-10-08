"""A regra da Caixinha de Equilíbrio, sem banco e sem HTTP.

Recebe números e devolve números. Ficar fora do controller não é
enfeite: é o que permite refazer qualquer fechamento no papel com as
colunas gravadas em `daily_closing` — e é a parte do sistema que mais
precisa ser explicável a quem teve dinheiro retido.

Os parâmetros são os da tabela "Parâmetros da regra" do RFC. Mudar um
deles aqui muda a regra para todo mundo a partir do próximo fechamento;
os dias já fechados continuam com os números que usaram.
"""

from decimal import ROUND_DOWN, Decimal
from typing import List

from models import DailyClosing, SmoothingBox

WINDOW_DAYS = 28
WARMUP_DAYS = 14
UPPER_FACTOR = Decimal("1.10")
LOWER_FACTOR = Decimal("0.90")
BOX_CAP_FACTOR = Decimal("10")

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def to_cents(value: Decimal) -> Decimal:
    """Arredonda para BAIXO, no centavo.

    Para baixo, e não para o mais próximo, porque é o lado seguro dos dois
    movimentos: a retenção nunca guarda um centavo a mais do que a regra
    pediu, e a liberação nunca devolve um centavo que a caixinha não tem.
    """
    return value.quantize(CENT, rounding=ROUND_DOWN)


def calculate_closing(
    window_incomes: List[Decimal],
    income: Decimal,
    box_status: str,
    retention_pct: int,
    box_balance: Decimal,
    account_balance: Decimal,
) -> dict:
    """Classifica o dia e diz quanto mover — e em que direção.

    Toda conta usa os valores JÁ arredondados no centavo: a média é
    arredondada primeiro, o teto e o piso saem dela. Assim quem refaz o
    dia a partir das colunas gravadas chega no mesmo centavo, sem
    precisar de casas decimais que o banco não guardou.
    """
    window_days = len(window_incomes)

    if window_days > 0:
        baseline = to_cents(sum(window_incomes, ZERO) / window_days)
    else:
        baseline = ZERO

    upper_bound = to_cents(baseline * UPPER_FACTOR)
    lower_bound = to_cents(baseline * LOWER_FACTOR)

    result = {
        "income": income,
        "baseline": baseline,
        "window_days": window_days,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "band": DailyClosing.NEUTRAL,
        "amount_calculated": ZERO,
        "amount_moved": ZERO,
    }

    # A ordem das perguntas é a do fluxograma do RFC, e ela importa:
    # quem está aquecendo ou pausado não chega a ser comparado com a média.
    if window_days < WARMUP_DAYS:
        result["band"] = DailyClosing.WARMUP
        return result

    if box_status == SmoothingBox.PAUSED:
        result["band"] = DailyClosing.PAUSED
        return result

    # Média zero: o cliente não teve renda nenhuma no último mês. Não há
    # excedente a guardar nem piso a garantir.
    if baseline == ZERO:
        return result

    if income > upper_bound:
        # Só o que passou do TETO é dividido — a renda até o teto é do
        # cliente, inteira. O movimento ainda esbarra em dois limites: o
        # que cabe na caixinha até 10× a média, e o que existe na conta
        # (o cliente pode já ter gastado o excedente durante o dia).
        amount_calculated = to_cents((income - upper_bound) * retention_pct / Decimal(100))
        box_room = max(to_cents(baseline * BOX_CAP_FACTOR) - box_balance, ZERO)

        result["band"] = DailyClosing.ABOVE
        result["amount_calculated"] = amount_calculated
        result["amount_moved"] = min(amount_calculated, box_room, account_balance)
        return result

    if income < lower_bound:
        # Devolve o que falta para o piso, até onde a caixinha tiver.
        amount_calculated = lower_bound - income

        result["band"] = DailyClosing.BELOW
        result["amount_calculated"] = amount_calculated
        result["amount_moved"] = min(amount_calculated, box_balance)
        return result

    return result
