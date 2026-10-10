from fastapi import FastAPI

from app.api.v1 import chat, health, identity, profile

app = FastAPI(title="Ubuzima")
app.include_router(health.router)
app.include_router(identity.router)
app.include_router(profile.router)
app.include_router(chat.router)
