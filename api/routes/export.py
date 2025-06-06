from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.evaluation import evaluate_request

from ..schemas import PortfolioItem
from ..utils.export_csv import export_evaluation_csv


class ExportRequest(BaseModel):
    portfolio: List[PortfolioItem]
    strategy: str


router = APIRouter()


@router.post("/api/evaluation/export")
def export_evaluation(request: ExportRequest) -> StreamingResponse:
    try:
        result = evaluate_request(request.dict())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    csv_buffer = export_evaluation_csv(result["results"])
    headers = {"Content-Disposition": "attachment; filename=evaluation.csv"}
    return StreamingResponse(csv_buffer, media_type="text/csv", headers=headers)
