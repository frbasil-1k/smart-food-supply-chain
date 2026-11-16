from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import ViewBase


class DonorImpactView(ViewBase):
    __tablename__ = "vw_donor_impact"
    __table_args__: ClassVar[dict[str, object]] = {"info": {"is_view": True}}  # type: ignore[misc]

    donor_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    donor_name: Mapped[str] = mapped_column(String(100))
    total_donations: Mapped[int] = mapped_column(Integer)
    total_donated_kg: Mapped[Decimal | None] = mapped_column(Numeric(30, 2))
    delivered_kg: Mapped[Decimal | None] = mapped_column(Numeric(30, 2))
    spoiled_kg: Mapped[Decimal | None] = mapped_column(Numeric(30, 2))
    undistributed_balance_kg: Mapped[Decimal | None] = mapped_column(Numeric(30, 2))


class DonorSustainabilityView(ViewBase):
    __tablename__ = "vw_donor_sustainability"
    __table_args__: ClassVar[dict[str, object]] = {"info": {"is_view": True}}  # type: ignore[misc]

    donor_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    donor_name: Mapped[str] = mapped_column(String(100))
    total_donations: Mapped[int] = mapped_column(Integer)
    total_donated_kg: Mapped[Decimal | None] = mapped_column(Numeric(30, 2))
    total_distributed_kg: Mapped[Decimal | None] = mapped_column(Numeric(30, 2))
    total_spoiled_kg: Mapped[Decimal | None] = mapped_column(Numeric(30, 2))


class DriverPerformanceView(ViewBase):
    __tablename__ = "vw_driver_performance"
    __table_args__: ClassVar[dict[str, object]] = {"info": {"is_view": True}}  # type: ignore[misc]

    driver_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_name: Mapped[str] = mapped_column(String(100))
    assigned_routes: Mapped[int] = mapped_column(Integer)
    completed_deliveries: Mapped[int] = mapped_column(Integer)
    delivered_quantity_kg: Mapped[Decimal | None] = mapped_column(Numeric(30, 2))
