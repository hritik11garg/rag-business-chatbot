from pydantic import BaseModel, EmailStr, Field

# bcrypt only hashes the first 72 BYTES; capping length here keeps a
# multibyte password from silently overflowing that limit, and enforces
# a minimum so trivially weak passwords are rejected at the edge.
PASSWORD_MIN = 8
PASSWORD_MAX = 72


class SignupRequest(BaseModel):
    organization_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
