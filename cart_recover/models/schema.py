"""
SQLAlchemy schema definitions for all 10 core entities in CartRecover-AI.
Implements primary keys, foreign keys, indexes, relationships and constraints.
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from cart_recover.models.base import Base

class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    segment: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/New_York")
    registered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    lifetime_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Relationships
    consents: Mapped[List["Consent"]] = relationship("Consent", back_populates="customer", cascade="all, delete-orphan")
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="customer", cascade="all, delete-orphan")
    carts: Mapped[List["Cart"]] = relationship("Cart", back_populates="customer", cascade="all, delete-orphan")
    send_attempts: Mapped[List["SendAttempt"]] = relationship("SendAttempt", back_populates="customer", cascade="all, delete-orphan")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="customer", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "customer_id": self.customer_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "segment": self.segment,
            "timezone": self.timezone,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None,
            "lifetime_value": round(self.lifetime_value, 2)
        }


class Consent(Base):
    __tablename__ = "consents"

    consent_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32), ForeignKey("customers.customer_id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)   # EMAIL, SMS
    status: Mapped[str] = mapped_column(String(16), nullable=False)    # OPTED_IN, OPTED_OUT
    source: Mapped[str] = mapped_column(String(32), nullable=False)    # CHECKOUT_FORM, ACCOUNT_SETTINGS, PREFERENCE_CENTER, UNSUBSCRIBE_LINK
    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    opt_out_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="consents")

    __table_args__ = (
        Index("ix_consent_cust_chan_date", "customer_id", "channel", "effective_at"),
    )

    def to_dict(self):
        return {
            "consent_id": self.consent_id,
            "customer_id": self.customer_id,
            "channel": self.channel,
            "status": self.status,
            "source": self.source,
            "effective_at": self.effective_at.isoformat() if self.effective_at else None,
            "opt_out_reason": self.opt_out_reason
        }


class Session(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32), ForeignKey("customers.customer_id"), nullable=False, index=True)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False) # DESKTOP, MOBILE, TABLET
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[str] = mapped_column(String(256), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="sessions")
    cart: Mapped[Optional["Cart"]] = relationship("Cart", back_populates="session", uselist=False)

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "customer_id": self.customer_id,
            "device_type": self.device_type,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "last_activity_at": self.last_activity_at.isoformat() if self.last_activity_at else None
        }


class Cart(Base):
    __tablename__ = "carts"

    cart_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(32), ForeignKey("sessions.session_id"), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(32), ForeignKey("customers.customer_id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True) # ACTIVE, ABANDONED, CHECKOUT_STARTED, CONVERTED, EXPIRED
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    subtotal: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tax_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    discount_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    abandoned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    is_stale_total: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="carts")
    session: Mapped["Session"] = relationship("Session", back_populates="cart")
    cart_lines: Mapped[List["CartLine"]] = relationship("CartLine", back_populates="cart", cascade="all, delete-orphan")
    send_attempts: Mapped[List["SendAttempt"]] = relationship("SendAttempt", back_populates="cart", cascade="all, delete-orphan")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="cart")
    attributions: Mapped[List["Attribution"]] = relationship("Attribution", back_populates="cart")

    def to_dict(self):
        return {
            "cart_id": self.cart_id,
            "session_id": self.session_id,
            "customer_id": self.customer_id,
            "status": self.status,
            "currency": self.currency,
            "subtotal": round(self.subtotal, 2),
            "tax_amount": round(self.tax_amount, 2),
            "discount_amount": round(self.discount_amount, 2),
            "total_amount": round(self.total_amount, 2),
            "item_count": self.item_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "abandoned_at": self.abandoned_at.isoformat() if self.abandoned_at else None,
            "is_stale_total": self.is_stale_total
        }


class CartLine(Base):
    __tablename__ = "cart_lines"

    cart_line_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cart_id: Mapped[str] = mapped_column(String(32), ForeignKey("carts.cart_id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(32), nullable=False)
    product_name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total: Mapped[float] = mapped_column(Float, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationships
    cart: Mapped["Cart"] = relationship("Cart", back_populates="cart_lines")

    def to_dict(self):
        return {
            "cart_line_id": self.cart_line_id,
            "cart_id": self.cart_id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "category": self.category,
            "unit_price": round(self.unit_price, 2),
            "quantity": self.quantity,
            "line_total": round(self.line_total, 2),
            "added_at": self.added_at.isoformat() if self.added_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class Campaign(Base):
    __tablename__ = "campaigns"

    campaign_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    variant_code: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False) # EMAIL, SMS
    target_segment: Mapped[str] = mapped_column(String(32), nullable=False)
    discount_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    discount_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    min_cart_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_cart_value: Mapped[float] = mapped_column(Float, nullable=False, default=999999.0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationships
    message_templates: Mapped[List["MessageTemplate"]] = relationship("MessageTemplate", back_populates="campaign", cascade="all, delete-orphan")
    send_attempts: Mapped[List["SendAttempt"]] = relationship("SendAttempt", back_populates="campaign")
    attributions: Mapped[List["Attribution"]] = relationship("Attribution", back_populates="campaign")

    def to_dict(self):
        return {
            "campaign_id": self.campaign_id,
            "name": self.name,
            "variant_code": self.variant_code,
            "channel": self.channel,
            "target_segment": self.target_segment,
            "discount_percent": round(self.discount_percent, 2),
            "discount_code": self.discount_code,
            "min_cart_value": round(self.min_cart_value, 2),
            "max_cart_value": round(self.max_cart_value, 2),
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class MessageTemplate(Base):
    __tablename__ = "message_templates"

    template_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(32), ForeignKey("campaigns.campaign_id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_line: Mapped[str] = mapped_column(String(256), nullable=False)
    body_template: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="message_templates")
    send_attempts: Mapped[List["SendAttempt"]] = relationship("SendAttempt", back_populates="template")

    def to_dict(self):
        return {
            "template_id": self.template_id,
            "campaign_id": self.campaign_id,
            "channel": self.channel,
            "subject_line": self.subject_line,
            "body_template": self.body_template,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class SendAttempt(Base):
    __tablename__ = "send_attempts"

    send_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cart_id: Mapped[str] = mapped_column(String(32), ForeignKey("carts.cart_id"), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(32), ForeignKey("customers.customer_id"), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(String(32), ForeignKey("campaigns.campaign_id"), nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(String(64), ForeignKey("message_templates.template_id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    suppression_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    cart: Mapped["Cart"] = relationship("Cart", back_populates="send_attempts")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="send_attempts")
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="send_attempts")
    template: Mapped["MessageTemplate"] = relationship("MessageTemplate", back_populates="send_attempts")
    attributions: Mapped[List["Attribution"]] = relationship("Attribution", back_populates="send_attempt")

    __table_args__ = (
        Index("ix_send_cust_chan_sent", "customer_id", "channel", "sent_at"),
    )

    def to_dict(self):
        return {
            "send_id": self.send_id,
            "cart_id": self.cart_id,
            "customer_id": self.customer_id,
            "campaign_id": self.campaign_id,
            "template_id": self.template_id,
            "channel": self.channel,
            "status": self.status,
            "suppression_reason": self.suppression_reason,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "clicked_at": self.clicked_at.isoformat() if self.clicked_at else None
        }


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32), ForeignKey("customers.customer_id"), nullable=False, index=True)
    cart_id: Mapped[Optional[str]] = mapped_column(String(32), ForeignKey("carts.cart_id"), nullable=True, index=True)
    order_status: Mapped[str] = mapped_column(String(32), nullable=False, default="COMPLETED")
    subtotal: Mapped[float] = mapped_column(Float, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Float, nullable=False)
    discount_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(32), nullable=False)
    placed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    cart: Mapped[Optional["Cart"]] = relationship("Cart", back_populates="orders")
    attributions: Mapped[List["Attribution"]] = relationship("Attribution", back_populates="order")

    def to_dict(self):
        return {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "cart_id": self.cart_id,
            "order_status": self.order_status,
            "subtotal": round(self.subtotal, 2),
            "tax_amount": round(self.tax_amount, 2),
            "discount_amount": round(self.discount_amount, 2),
            "total_amount": round(self.total_amount, 2),
            "payment_method": self.payment_method,
            "placed_at": self.placed_at.isoformat() if self.placed_at else None
        }


class Attribution(Base):
    __tablename__ = "attributions"

    attribution_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(32), ForeignKey("orders.order_id"), nullable=False, index=True)
    send_id: Mapped[str] = mapped_column(String(32), ForeignKey("send_attempts.send_id"), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(String(32), ForeignKey("campaigns.campaign_id"), nullable=False, index=True)
    cart_id: Mapped[str] = mapped_column(String(32), ForeignKey("carts.cart_id"), nullable=False, index=True)
    attribution_model: Mapped[str] = mapped_column(String(32), nullable=False, default="LAST_TOUCH_7D")
    attributed_revenue: Mapped[float] = mapped_column(Float, nullable=False)
    attribution_window_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=168)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    attributed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="attributions")
    send_attempt: Mapped["SendAttempt"] = relationship("SendAttempt", back_populates="attributions")
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="attributions")
    cart: Mapped["Cart"] = relationship("Cart", back_populates="attributions")

    def to_dict(self):
        return {
            "attribution_id": self.attribution_id,
            "order_id": self.order_id,
            "send_id": self.send_id,
            "campaign_id": self.campaign_id,
            "cart_id": self.cart_id,
            "attribution_model": self.attribution_model,
            "attributed_revenue": round(self.attributed_revenue, 2),
            "attribution_window_hours": self.attribution_window_hours,
            "is_valid": self.is_valid,
            "is_primary": self.is_primary,
            "attributed_at": self.attributed_at.isoformat() if self.attributed_at else None
        }
