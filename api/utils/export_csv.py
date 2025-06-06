import io
from typing import Iterable, Mapping

import pandas as pd


def export_evaluation_csv(rows: Iterable[Mapping[str, object]]) -> io.StringIO:
    """Return CSV buffer for given evaluation rows."""
    df = pd.DataFrame(list(rows))
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return buffer
