from fastapi import FastAPI

from app.api.v1 import health, identity

app = FastAPI(title="Ubuzima")
app.include_router(health.router)
app.include_router(identity.router)
