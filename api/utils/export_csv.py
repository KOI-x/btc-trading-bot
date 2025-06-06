import io
from typing import Iterable, Mapping

import pandas as pd


def export_evaluation_csv(
    rows: Iterable[Mapping[str, object]], suggestion: str
) -> io.StringIO:
    """Return CSV buffer for given evaluation rows and summary."""
    df = pd.DataFrame(list(rows))
    # Append suggestion as a final row for readability
    df.loc[len(df)] = {
        "coin_id": "",
        "estrategia": "",
        "fecha": "",
        "retorno_estrategia": "",
        "retorno_hold": "",
        "comparacion": "",
        "equity_curve": "",
        "comentario": suggestion,
    }
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return buffer
