from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.modules.users.models import OrgType, UserRole


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    type: OrgType
    tax_id: str | None = None


class UserCreate(BaseModel):
    organization_id: int
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=2, max_length=200)
    role: UserRole = UserRole.lector


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    type: OrgType
    created_at: datetime


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: str
    role: UserRole
    organization_id: int
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"