"""
Tests for time-based cart abandonment detection and event ordering.
"""
from datetime import datetime, timedelta
from generate_data import is_abandoned, ABANDON_WINDOW

def test_abandonment_boundary_exact_60_minutes():
    """Documented rule: an order placed exactly at last_activity + 60 min is NOT abandoned."""
    last_act = datetime(2026, 5, 1, 12, 0, 0)
    order_ts = last_act + timedelta(minutes=60)
    
    # Boundary is inclusive (order at <= last_activity + 60 min is NOT abandoned)
    assert not is_abandoned(last_act, order_ts), "Order at +60m should not be abandoned"

def test_abandonment_boundary_61_minutes():
    """Documented rule: an order placed at last_activity + 61 min IS abandoned."""
    last_act = datetime(2026, 5, 1, 12, 0, 0)
    order_ts = last_act + timedelta(minutes=61)
    
    assert is_abandoned(last_act, order_ts), "Order at +61m must be abandoned"

def test_abandonment_no_purchase():
    """Cart with no purchase is abandoned."""
    last_act = datetime(2026, 5, 1, 12, 0, 0)
    assert is_abandoned(last_act, None), "Unpurchased cart must be abandoned"

def test_abandonment_events_in_db(db_session):
    """Verify carts flagged abandoned have abandoned_flagged event in event history."""
    from cart_recover.models.orm_models import Cart, CartEvent
    abandoned_carts = db_session.query(Cart).filter(Cart.abandoned_at.isnot(None)).limit(10).all()
    for cart in abandoned_carts:
        events = db_session.query(CartEvent).filter(CartEvent.cart_id == cart.cart_id).all()
        types = [e.event_type for e in events]
        assert "cart_created" in types
        assert "abandoned_flagged" in types
