from fastapi import FastAPI

from app.api.v1 import admin, chat, health, identity, profile, voice

app = FastAPI(title="Ubuzima")
app.include_router(health.router)
app.include_router(admin.router)
app.include_router(identity.router)
app.include_router(profile.router)
app.include_router(chat.router)
app.include_router(voice.router)
