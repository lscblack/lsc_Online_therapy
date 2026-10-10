from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.models import User
from app.models.profile import Profile
from app.repositories.profiles import ProfileRepository
from app.schemas.profile import ProfileOut, ProfileUpdate

_PLAIN = ("nickname", "age_band", "gender", "pronouns", "tone_pref", "interests")


class ProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProfileRepository(session)

    async def get(self, user: User) -> Profile | None:
        return await self.repo.get(user.id)

    async def upsert(self, user: User, data: ProfileUpdate) -> Profile:
        sent = data.model_fields_set
        fields: dict = {}
        for k in _PLAIN:
            if k in sent:
                v = getattr(data, k)
                if v is None and k in ("age_band", "interests"):
                    continue  # non-nullable columns: null means "leave as is"
                fields[k] = v
        if "sensitive_context" in sent:
            existing = await self.repo.get(user.id)
            consent = dict(existing.consent or {}) if existing else {}
            text_ = data.sensitive_context
            granted = bool(text_)
            fields["sensitive_context_enc"] = crypto.encrypt(text_) if granted else None
            consent["sensitive_context"] = {
                "granted": granted, "at": datetime.now(UTC).isoformat()}
            fields["consent"] = consent
        profile = await self.repo.upsert(user.id, fields)
        await self.session.commit()
        return profile

    async def wipe(self, user: User) -> None:
        """Delete the profile plus all conversation/message history for the user.
        The account (users row) is kept."""
        await self.repo.delete(user.id)
        await self.repo.delete_history(user.id)
        await self.session.commit()

    @staticmethod
    def to_out(profile: Profile) -> ProfileOut:
        enc = profile.sensitive_context_enc
        return ProfileOut(
            nickname=profile.nickname, age_band=profile.age_band, gender=profile.gender,
            pronouns=profile.pronouns, tone_pref=profile.tone_pref,
            interests=list(profile.interests or []),
            sensitive_context=crypto.decrypt(enc) if enc else None,
            consent=dict(profile.consent or {}), updated_at=profile.updated_at)
