from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

USER_ROLES = ("DONOR", "NGO_MANAGER", "DRIVER", "SAFETY_INSPECTOR")
ACCOUNT_STATUSES = ("ACTIVE", "INACTIVE", "SUSPENDED")


class Organization(Base):
    __tablename__ = "organization"

    organization_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_name: Mapped[str] = mapped_column(String(150), nullable=False)
    hq_address: Mapped[str] = mapped_column(String(255), nullable=False)
    hq_pincode: Mapped[str] = mapped_column(String(10), nullable=False)
    hq_contact_no: Mapped[str] = mapped_column(String(15), nullable=False)

    branches: Mapped[list[Branch]] = relationship(back_populates="organization")


class Branch(Base):
    __tablename__ = "branch"

    branch_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organization.organization_id"), nullable=False, index=True
    )
    branch_name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    pincode: Mapped[str] = mapped_column(String(10), nullable=False)
    contact_no: Mapped[str] = mapped_column(String(15), nullable=False)
    established_date: Mapped[date] = mapped_column(Date, nullable=False)
    regional_manager_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.user_id"), nullable=True, index=True
    )

    organization: Mapped[Organization] = relationship(back_populates="branches")
    regional_manager: Mapped[AppUser | None] = relationship(
        back_populates="managed_branches", foreign_keys=[regional_manager_user_id]
    )
    routes: Mapped[list[Route]] = relationship(back_populates="managing_branch")
    primary_users: Mapped[list[AppUser]] = relationship(
        foreign_keys="AppUser.primary_branch_id", back_populates="primary_branch"
    )


class AppUser(Base):
    __tablename__ = "app_user"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(15), nullable=False)
    user_role: Mapped[str] = mapped_column(
        Enum(*USER_ROLES, name="user_role", native_enum=True), nullable=False
    )
    account_status: Mapped[str | None] = mapped_column(
        Enum(*ACCOUNT_STATUSES, name="account_status", native_enum=True),
        nullable=True,
        default="ACTIVE",
    )
    primary_branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branch.branch_id"), nullable=True, index=True
    )
    supervisor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.user_id"), nullable=True
    )

    primary_branch: Mapped[Branch | None] = relationship(
        foreign_keys=[primary_branch_id], back_populates="primary_users"
    )
    managed_branches: Mapped[list[Branch]] = relationship(
        foreign_keys="Branch.regional_manager_user_id", back_populates="regional_manager"
    )
    credential: Mapped[UserCredential | None] = relationship(back_populates="user", uselist=False)
    donations: Mapped[list[Donation]] = relationship(
        back_populates="donor", foreign_keys="Donation.donor_user_id"
    )
    dependents: Mapped[list[Dependent]] = relationship(back_populates="driver")


class UserCredential(Base):
    __tablename__ = "user_credential"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.user_id", ondelete="CASCADE"), primary_key=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reset_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped[AppUser] = relationship(back_populates="credential")


class Dependent(Base):
    __tablename__ = "dependent"

    driver_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.user_id"), primary_key=True)
    dependent_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    relationship_name: Mapped[str] = mapped_column("relationship", String(50), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(15), nullable=True)

    driver: Mapped[AppUser] = relationship(back_populates="dependents")


# Imported late so relationship annotations can resolve without a cycle.
from .donations import Donation, Route  # noqa: E402
