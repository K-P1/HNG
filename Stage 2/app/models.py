from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, Float, DateTime, func
from app.database import Base
from sqlalchemy.orm import Mapped, mapped_column


class Country(Base):
    __tablename__ = "countries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    capital: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    population: Mapped[int] = mapped_column(Integer, nullable=False)
    currency_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    exchange_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_gdp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    flag_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_refreshed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )


class RefreshMeta(Base):
    """Singleton-style table to store application-level metadata such as last refresh time."""
    __tablename__ = "refresh_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
