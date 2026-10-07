from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.modules.users.models import OrgType, UserRole


class SignupRequest(BaseModel):
    """Onboarding público: crea la organización y su primer usuario (admin)
    en una sola operación. El rol NO se recibe: el primer usuario siempre
    es admin de la organización que acaba de crear."""
    organization_name: str = Field(min_length=2, max_length=200)
    organization_type: OrgType
    tax_id: str | None = Field(default=None, max_length=50)
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class MemberCreate(BaseModel):
    """Un admin agrega a un compañero. La organización NO se recibe: sale
    del token del admin, así nadie puede crear usuarios en otra empresa."""
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
    tax_id: str | None
    created_at: datetime


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: str
    role: UserRole
    organization_id: int
    created_at: datetime


class MeOut(UserOut):
    """Usuario + su organización: el frontend necesita el tipo de
    organización para decidir si muestra la vista de proveedor o constructora."""
    organization: OrganizationOut


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"