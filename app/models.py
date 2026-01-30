# app/models.py
from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Boolean,
    Text,
    Numeric,
    ForeignKey,
    DateTime,
    JSON,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import relationship

from .db import Base


class Fund(Base):
    __tablename__ = "funds"

    id = Column(BigInteger, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    base_ccy = Column(String, nullable=False, default="USD")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Investor(Base):
    __tablename__ = "investors"

    id = Column(BigInteger, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    memo = Column(Text)

    is_active = Column(Boolean, nullable=False, default=True)

    deleted_at = Column(DateTime(timezone=True))
    deleted_by = Column(BigInteger)
    deleted_reason = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    positions = relationship("InvestorPosition", back_populates="investor")


class InvestorPosition(Base):
    __tablename__ = "investor_positions"

    fund_id = Column(BigInteger, ForeignKey("funds.id"), primary_key=True)
    investor_id = Column(BigInteger, ForeignKey("investors.id"), primary_key=True)

    units = Column(Numeric(30, 10), nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    fund = relationship("Fund")
    investor = relationship("Investor", back_populates="positions")


class UnitPricePoint(Base):
    __tablename__ = "unit_price_points"
    __table_args__ = (
        UniqueConstraint("fund_id", "asof_at", name="unit_price_points_fund_id_asof_at_key"),
        Index("ix_unit_price_points_fund_asof_desc", "fund_id", "asof_at"),
    )

    id = Column(BigInteger, primary_key=True)
    fund_id = Column(BigInteger, ForeignKey("funds.id"), nullable=False)

    asof_at = Column(DateTime(timezone=True), nullable=False)
    price = Column(Numeric(30, 10), nullable=False)
    note = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    fund = relationship("Fund")


class FXAccount(Base):
    __tablename__ = "fx_accounts"
    __table_args__ = (
        # broker + login + server(없으면 '') 유니크를 DB 인덱스로 잡고 싶으면 DDL에서 expression index로 잡는게 정석
        Index("ix_fx_accounts_fund_active", "fund_id", "is_active"),
    )

    id = Column(BigInteger, primary_key=True)
    fund_id = Column(BigInteger, ForeignKey("funds.id"), nullable=False)

    broker = Column(String, nullable=False, default="MT5")
    account_login = Column(String, nullable=False)
    account_server = Column(String)
    account_ccy = Column(String, nullable=False, default="USD")

    is_active = Column(Boolean, nullable=False, default=True)
    secret = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    fund = relationship("Fund")
    snapshots = relationship("FXAccountSnapshot", back_populates="fx_account")


class FXAccountSnapshot(Base):
    __tablename__ = "fx_account_snapshots"
    __table_args__ = (
        UniqueConstraint("fx_account_id", "asof_at", name="fx_account_snapshots_fx_account_id_asof_at_key"),
        Index("ix_fx_account_snapshots_fxid_asof_desc", "fx_account_id", "asof_at"),
    )

    id = Column(BigInteger, primary_key=True)
    fx_account_id = Column(BigInteger, ForeignKey("fx_accounts.id"), nullable=False)

    asof_at = Column(DateTime(timezone=True), nullable=False)

    balance = Column(Numeric(30, 10), nullable=False)
    equity = Column(Numeric(30, 10), nullable=False)
    margin = Column(Numeric(30, 10))
    free_margin = Column(Numeric(30, 10))
    profit = Column(Numeric(30, 10))

    raw = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    fx_account = relationship("FXAccount", back_populates="snapshots")


class CashflowRequest(Base):
    __tablename__ = "cashflow_requests"

    id = Column(BigInteger, primary_key=True)
    fund_id = Column(BigInteger, ForeignKey("funds.id"), nullable=False)
    investor_id = Column(BigInteger, ForeignKey("investors.id"), nullable=False)

    kind = Column(String, nullable=False)  # 'DEPOSIT' / 'WITHDRAW'
    currency = Column(String, nullable=False, default="USD")
    amount = Column(Numeric(30, 10), nullable=False)

    status = Column(String, nullable=False, default="PENDING")  # PENDING/CONFIRMED/CANCELLED

    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    confirmed_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        Index("ix_ledger_entries_source", "source_type", "source_id"),
    )

    id = Column(BigInteger, primary_key=True)

    source_type = Column(String, nullable=False)
    source_id = Column(BigInteger, nullable=False)

    account = Column(String, nullable=False)  # 'CASH' / 'UNITS'
    amount = Column(Numeric(30, 10), nullable=False)
    unit_price = Column(Numeric(30, 10))

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True)
    actor_admin_id = Column(BigInteger, nullable=False)

    action = Column(String, nullable=False)
    target_type = Column(String, nullable=False)
    target_id = Column(BigInteger, nullable=False)

    diff = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
