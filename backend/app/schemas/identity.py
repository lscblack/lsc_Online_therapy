from pydantic import BaseModel, Field

PASSPHRASE_MIN = 8
PASSPHRASE_MAX = 256


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AnonSession(TokenPair):
    """Bootstrap response. anon_id is the recovery handle the user should keep."""
    anon_id: str


class UpgradeRequest(BaseModel):
    passphrase: str = Field(min_length=PASSPHRASE_MIN, max_length=PASSPHRASE_MAX)


class UpgradeResponse(BaseModel):
    is_upgraded: bool


class RecoverRequest(BaseModel):
    anon_id: str = Field(min_length=1, max_length=128)
    passphrase: str = Field(min_length=1, max_length=PASSPHRASE_MAX)


class RefreshRequest(BaseModel):
    refresh_token: str
