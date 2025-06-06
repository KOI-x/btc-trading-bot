from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.evaluation import evaluate_request

from ..schemas import PortfolioItem
from ..utils.export_csv import export_evaluation_csv
from ..utils.export_pdf import export_evaluation_pdf


class ExportRequest(BaseModel):
    portfolio: List[PortfolioItem]
    strategy: str
    format: str = "csv"


router = APIRouter()


@router.post("/api/evaluation/export")
def export_evaluation(request: ExportRequest) -> StreamingResponse:
    try:
        result = evaluate_request(request.dict())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if request.format == "pdf":
        pdf_buffer = export_evaluation_pdf(result["results"], result["suggestion"])
        headers = {"Content-Disposition": "attachment; filename=evaluation.pdf"}
        return StreamingResponse(
            pdf_buffer, media_type="application/pdf", headers=headers
        )

    csv_buffer = export_evaluation_csv(result["results"], result["suggestion"])
    headers = {"Content-Disposition": "attachment; filename=evaluation.csv"}
    return StreamingResponse(csv_buffer, media_type="text/csv", headers=headers)
