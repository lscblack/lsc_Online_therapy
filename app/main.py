from fastapi import FastAPI

from app.api.v1 import health

app = FastAPI(title="Ubuzima")
app.include_router(health.router)
