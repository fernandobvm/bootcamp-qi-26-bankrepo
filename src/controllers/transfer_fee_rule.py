from decimal import ROUND_HALF_UP, Decimal

from constants import FREE_TRANSFERS_PER_MONTH, TRANSFER_FEE_MINIMUM, TRANSFER_FEE_RATE


def calculate_transfer_fee(value: Decimal, transfers_this_month: int) -> Decimal:
    """A tarifa de uma transferência, dado quantas a conta já fez no mês.

    `transfers_this_month` conta as transferências JÁ feitas, sem esta.
    Enquanto ele estiver abaixo da franquia, a tarifa é zero: a 1ª até a
    5ª do mês saem de graça, e a 6ª é a primeira que paga.

    Fora da franquia, é um percentual do valor com piso: 1% de R$ 500 é
    R$ 5,00, mas 1% de R$ 30 seria R$ 0,30, e aí vale o mínimo de
    R$ 1,00. O percentual é arredondado para o centavo mais próximo
    (meio centavo sobe): 1% de R$ 123,45 é R$ 1,2345, cobrado R$ 1,23.

    Função pura, sem banco: a mesma entrada dá sempre a mesma tarifa, e
    dá pra conferir a regra no papel.
    """
    if transfers_this_month < FREE_TRANSFERS_PER_MONTH:
        return Decimal("0.00")

    percentage_fee = (value * TRANSFER_FEE_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return max(percentage_fee, TRANSFER_FEE_MINIMUM)
