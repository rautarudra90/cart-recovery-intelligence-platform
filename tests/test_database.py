"""
Tests for SQLite relational persistence, SQLAlchemy ORM mappings, and repository queries.
"""
from sqlalchemy import func
from cart_recover.models.orm_models import (
    Customer, Cart, Order, SendAttempt, Attribution, Consent, Campaign
)
from cart_recover.database.repository import AnalyticsRepository

def test_sqlite_tables_populated(db_session):
    customer_count = db_session.query(func.count(Customer.customer_id)).scalar()
    cart_count = db_session.query(func.count(Cart.cart_id)).scalar()
    order_count = db_session.query(func.count(Order.order_id)).scalar()
    send_count = db_session.query(func.count(SendAttempt.send_id)).scalar()

    assert customer_count > 0, "Customers table empty"
    assert cart_count >= 1000, "Carts table has insufficient rows"
    assert order_count > 0, "Orders table empty"
    assert send_count > 0, "Send attempts table empty"

def test_orm_relationships_navigation(db_session):
    # Test Cart -> CartLines navigation
    cart = db_session.query(Cart).filter(Cart.item_count > 1).first()
    assert cart is not None
    assert len(cart.cart_lines) > 0
    assert cart.cart_lines[0].cart_id == cart.cart_id

    # Test Order -> Attribution navigation
    attr = db_session.query(Attribution).first()
    if attr:
        assert attr.order is not None
        assert attr.send_attempt is not None
        assert attr.campaign is not None

def test_analytics_repository_kpis(db_session):
    repo = AnalyticsRepository(db_session)
    kpis = repo.get_executive_kpis()

    assert kpis["total_carts"] > 0
    assert 0 <= kpis["abandonment_rate"] <= 100
    assert 0 <= kpis["recovery_rate"] <= 100
    assert kpis["total_send_attempts"] == kpis["messages_sent"] + kpis["messages_suppressed"]
    assert kpis["attributed_revenue_dedup"] <= kpis["total_order_revenue"]
