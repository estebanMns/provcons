import enum
from passlib.context import CryptContext
from sqlalchemy import String, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
from app.db.mixins import TimestampMixin

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class OrgType(str, enum.Enum):
    constructora = "constructora"
    proveedor = "proveedor"


class UserRole(str, enum.Enum):
    admin = "admin"
    gestor = "gestor"
    lector = "lector"


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[OrgType] = mapped_column(Enum(OrgType))
    tax_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=True)

    users: Mapped[list["User"]] = relationship(back_populates="organization")

    def is_provider(self) -> bool:
        return self.type == OrgType.proveedor


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.lector)

    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    organization: Mapped["Organization"] = relationship(back_populates="users")

    def set_password(self, raw_password: str) -> None:
        self.password_hash = _pwd_context.hash(raw_password)

    def verify_password(self, raw_password: str) -> bool:
        return _pwd_context.verify(raw_password, self.password_hash)

    def is_admin(self) -> bool:
        return self.role == UserRole.admin