"""
SQLAlchemy ORM models mirroring the canonical schema.py tables.
Supports direct querying and relational operations across all 10 core entities
plus the audit event and bridge tables.
"""
from typing import List, Optional
from sqlalchemy import (
    String, Integer, Float, DateTime, ForeignKey, Text, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    region: Mapped[str] = mapped_column(String(16), nullable=False)
    signup_source: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    # Relationships
    consents: Mapped[List["Consent"]] = relationship("Consent", back_populates="customer")
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="customer")
    carts: Mapped[List["Cart"]] = relationship("Cart", back_populates="customer")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="customer")
    scheduled_messages: Mapped[List["ScheduledMessage"]] = relationship("ScheduledMessage", back_populates="customer")
    send_attempts: Mapped[List["SendAttempt"]] = relationship("SendAttempt", back_populates="customer")


class Consent(Base):
    __tablename__ = "consents"

    consent_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32), ForeignKey("customers.customer_id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_from: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    effective_to: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="consents")


class Product(Base):
    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(32), primary_key=True)
    product_name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)

    cart_lines: Mapped[List["CartLine"]] = relationship("CartLine", back_populates="product")


class Session(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[Optional[str]] = mapped_column(String(32), ForeignKey("customers.customer_id"), nullable=True, index=True)
    device_id: Mapped[str] = mapped_column(String(32), nullable=False)
    device_type: Mapped[str] = mapped_column(String(16), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[str] = mapped_column(String(32), nullable=False)
    ended_at: Mapped[str] = mapped_column(String(32), nullable=False)

    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="sessions")
    cart_sessions: Mapped[List["CartSession"]] = relationship("CartSession", back_populates="session")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="session")


class Cart(Base):
    __tablename__ = "carts"

    cart_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[Optional[str]] = mapped_column(String(32), ForeignKey("customers.customer_id"), nullable=True, index=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    last_activity_at: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    cart_total: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    abandoned_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)

    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="carts")
    cart_lines: Mapped[List["CartLine"]] = relationship("CartLine", back_populates="cart")
    cart_events: Mapped[List["CartEvent"]] = relationship("CartEvent", back_populates="cart")
    cart_sessions: Mapped[List["CartSession"]] = relationship("CartSession", back_populates="cart")
    abandonment_decision: Mapped[Optional["AbandonmentDecision"]] = relationship("AbandonmentDecision", back_populates="cart", uselist=False)
    scheduled_messages: Mapped[List["ScheduledMessage"]] = relationship("ScheduledMessage", back_populates="cart")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="cart")


class CartSession(Base):
    __tablename__ = "cart_sessions"

    cart_id: Mapped[str] = mapped_column(String(32), ForeignKey("carts.cart_id"), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(32), ForeignKey("sessions.session_id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)

    cart: Mapped["Cart"] = relationship("Cart", back_populates="cart_sessions")
    session: Mapped["Session"] = relationship("Session", back_populates="cart_sessions")


class CartLine(Base):
    __tablename__ = "cart_lines"

    cart_line_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cart_id: Mapped[str] = mapped_column(String(32), ForeignKey("carts.cart_id"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sku: Mapped[str] = mapped_column(String(32), ForeignKey("products.sku"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    line_total: Mapped[float] = mapped_column(Float, nullable=False)
    added_at: Mapped[str] = mapped_column(String(32), nullable=False)

    cart: Mapped["Cart"] = relationship("Cart", back_populates="cart_lines")
    product: Mapped["Product"] = relationship("Product", back_populates="cart_lines")


class CartEvent(Base):
    __tablename__ = "cart_events"

    cart_event_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cart_id: Mapped[str] = mapped_column(String(32), ForeignKey("carts.cart_id"), nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(32), ForeignKey("sessions.session_id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_ts: Mapped[str] = mapped_column(String(32), nullable=False)
    cart_line_id: Mapped[Optional[str]] = mapped_column(String(32), ForeignKey("cart_lines.cart_line_id"), nullable=True)
    old_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    new_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    cart: Mapped["Cart"] = relationship("Cart", back_populates="cart_events")


class AbandonmentDecision(Base):
    __tablename__ = "abandonment_decisions"

    decision_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cart_id: Mapped[str] = mapped_column(String(32), ForeignKey("carts.cart_id"), unique=True, nullable=False)
    abandoned_at: Mapped[str] = mapped_column(String(32), nullable=False)
    recovery_decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)

    cart: Mapped["Cart"] = relationship("Cart", back_populates="abandonment_decision")


class Campaign(Base):
    __tablename__ = "campaigns"

    campaign_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    variant: Mapped[str] = mapped_column(String(16), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    start_date: Mapped[str] = mapped_column(String(16), nullable=False)
    end_date: Mapped[str] = mapped_column(String(16), nullable=False)
    delay_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    attribution_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)

    scheduled_messages: Mapped[List["ScheduledMessage"]] = relationship("ScheduledMessage", back_populates="campaign")
    attributions: Mapped[List["Attribution"]] = relationship("Attribution", back_populates="campaign")


class MessageTemplate(Base):
    __tablename__ = "message_templates"

    template_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    variant: Mapped[str] = mapped_column(String(16), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    discount_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[str] = mapped_column(String(16), nullable=False)

    scheduled_messages: Mapped[List["ScheduledMessage"]] = relationship("ScheduledMessage", back_populates="template")


class CampaignTemplate(Base):
    __tablename__ = "campaign_templates"

    campaign_id: Mapped[str] = mapped_column(String(32), ForeignKey("campaigns.campaign_id"), primary_key=True)
    template_id: Mapped[str] = mapped_column(String(32), ForeignKey("message_templates.template_id"), primary_key=True)


class ScheduledMessage(Base):
    __tablename__ = "scheduled_messages"

    message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cart_id: Mapped[str] = mapped_column(String(32), ForeignKey("carts.cart_id"), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(32), ForeignKey("customers.customer_id"), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(String(32), ForeignKey("campaigns.campaign_id"), nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(String(32), ForeignKey("message_templates.template_id"), nullable=False)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    planned_ts: Mapped[str] = mapped_column(String(32), nullable=False)
    scheduled_ts: Mapped[str] = mapped_column(String(32), nullable=False)

    cart: Mapped["Cart"] = relationship("Cart", back_populates="scheduled_messages")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="scheduled_messages")
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="scheduled_messages")
    template: Mapped["MessageTemplate"] = relationship("MessageTemplate", back_populates="scheduled_messages")
    send_attempt: Mapped[Optional["SendAttempt"]] = relationship("SendAttempt", back_populates="scheduled_message", uselist=False)


class SendAttempt(Base):
    __tablename__ = "send_attempts"

    send_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    message_id: Mapped[str] = mapped_column(String(64), ForeignKey("scheduled_messages.message_id"), unique=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(32), ForeignKey("customers.customer_id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    attempt_ts: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    consent_id: Mapped[Optional[str]] = mapped_column(String(32), ForeignKey("consents.consent_id"), nullable=True)
    sends_last_24h: Mapped[int] = mapped_column(Integer, nullable=False)
    sends_last_7d: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    scheduled_message: Mapped["ScheduledMessage"] = relationship("ScheduledMessage", back_populates="send_attempt")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="send_attempts")
    send_events: Mapped[List["SendEvent"]] = relationship("SendEvent", back_populates="send_attempt")
    attributions: Mapped[List["Attribution"]] = relationship("Attribution", back_populates="send_attempt")


class SendEvent(Base):
    __tablename__ = "send_events"

    event_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    send_id: Mapped[str] = mapped_column(String(32), ForeignKey("send_attempts.send_id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_ts: Mapped[str] = mapped_column(String(32), nullable=False)

    send_attempt: Mapped["SendAttempt"] = relationship("SendAttempt", back_populates="send_events")


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[Optional[str]] = mapped_column(String(32), ForeignKey("customers.customer_id"), nullable=True, index=True)
    cart_id: Mapped[str] = mapped_column(String(32), ForeignKey("carts.cart_id"), unique=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(32), ForeignKey("sessions.session_id"), nullable=False)
    order_ts: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    subtotal: Mapped[float] = mapped_column(Float, nullable=False)
    discount_amount: Mapped[float] = mapped_column(Float, nullable=False)
    shipping_fee: Mapped[float] = mapped_column(Float, nullable=False)
    order_total: Mapped[float] = mapped_column(Float, nullable=False)
    promo_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="orders")
    cart: Mapped["Cart"] = relationship("Cart", back_populates="orders")
    session: Mapped["Session"] = relationship("Session", back_populates="orders")
    attributions: Mapped[List["Attribution"]] = relationship("Attribution", back_populates="order")


class Attribution(Base):
    __tablename__ = "attributions"

    attribution_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(32), ForeignKey("orders.order_id"), nullable=False, index=True)
    send_id: Mapped[str] = mapped_column(String(32), ForeignKey("send_attempts.send_id"), nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(String(64), ForeignKey("scheduled_messages.message_id"), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(32), ForeignKey("campaigns.campaign_id"), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(32), nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    click_ts: Mapped[str] = mapped_column(String(32), nullable=False)
    order_ts: Mapped[str] = mapped_column(String(32), nullable=False)
    lag_hours: Mapped[float] = mapped_column(Float, nullable=False)
    attributed_revenue: Mapped[float] = mapped_column(Float, nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="attributions")
    send_attempt: Mapped["SendAttempt"] = relationship("SendAttempt", back_populates="attributions")
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="attributions")
