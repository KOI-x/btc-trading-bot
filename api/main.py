from fastapi import FastAPI

from .routes.core import router as core_router
from .routes.export import router as export_router

app = FastAPI()
app.include_router(core_router)
app.include_router(export_router)
