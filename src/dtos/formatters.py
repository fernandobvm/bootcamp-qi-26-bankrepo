from datetime import datetime
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from constants import BANK_TIMEZONE


def money(value: Optional[Decimal]) -> Optional[str]:
    """Dinheiro sai como texto com duas casas: "50.00", nunca 50.0.

    Um número decimal no JSON vira `float` em quem lê (o JavaScript, por
    exemplo, não tem outro tipo), e é aí que R$ 0,10 + R$ 0,20 deixa de
    dar R$ 0,30. Mandando texto, o valor chega do jeito que o banco
    guardou, e quem consome converte para o tipo exato da linguagem dele.
    """
    if value is None:
        return None

    return f"{value:.2f}"


def bank_datetime(value: Optional[datetime]) -> Optional[str]:
    """Um instante no fuso do banco, com o deslocamento escrito: "2026-10-10T14:30:00-03:00".

    O banco de dados guarda o instante absoluto (TIMESTAMPTZ); a resposta
    mostra esse instante no relógio de São Paulo, que é o do cliente. O
    "-03:00" no fim faz o texto continuar sendo um instante só, sem
    ambiguidade, para quem estiver em outro fuso.
    """
    if value is None:
        return None

    return value.astimezone(ZoneInfo(BANK_TIMEZONE)).isoformat()
