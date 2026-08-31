from pydantic import BaseModel


class CreateAPIKeyRequest(BaseModel):
    name: str = "Default API Key"


class APIKeyResponse(BaseModel):
    id: int
    name: str
    prefix: str
    active: bool
    created_at: str


class APIKeyCreatedResponse(APIKeyResponse):
    key: str