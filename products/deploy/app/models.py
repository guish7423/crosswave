"""CrossDeploy — deployment order data model."""

import enum
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Enum, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./crossdeploy.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class OrderStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class OrderTier(str, enum.Enum):
    basic = "basic"
    standard = "standard"
    enterprise = "enterprise"


TIER_PRICES = {
    OrderTier.basic: 2000,
    OrderTier.standard: 3000,
    OrderTier.enterprise: 5000,
}

TIER_PRODUCTS = {
    OrderTier.basic: "CrossBridge",
    OrderTier.standard: "CrossBridge + CrossBlog",
    OrderTier.enterprise: "Polsia Fork",
}


class DeployOrder(Base):
    __tablename__ = "deploy_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_name = Column(String(128), nullable=False)
    customer_email = Column(String(256), nullable=False)
    company = Column(String(256), default="")
    tier = Column(Enum(OrderTier), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.pending)
    notes = Column(Text, default="")
    stripe_session_id = Column(String(128), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    @property
    def price(self) -> int:
        return TIER_PRICES.get(self.tier, 0)

    @property
    def product_label(self) -> str:
        return TIER_PRODUCTS.get(self.tier, "—")


def init_db():
    Base.metadata.create_all(bind=engine)
