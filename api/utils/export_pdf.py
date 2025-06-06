import io
from typing import Iterable, Mapping

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def export_evaluation_pdf(
    rows: Iterable[Mapping[str, object]], suggestion: str
) -> io.BytesIO:
    """Return PDF buffer for given evaluation rows and summary."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    style = getSampleStyleSheet()

    data = [
        [
            "coin_id",
            "estrategia",
            "fecha",
            "retorno_estrategia",
            "retorno_hold",
            "comparacion",
        ]
    ]
    for row in rows:
        data.append(
            [
                row.get("coin_id", ""),
                row.get("estrategia", ""),
                row.get("fecha", ""),
                f"{row.get('retorno_estrategia', '')}",
                f"{row.get('retorno_hold', '')}",
                row.get("comparacion", ""),
            ]
        )
    table = Table(data)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )

    elements = [
        table,
        Spacer(1, 12),
        Paragraph(f"Sugerencia: {suggestion}", style["Normal"]),
    ]
    doc.build(elements)
    buffer.seek(0)
    return buffer
