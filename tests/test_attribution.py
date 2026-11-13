"""
Tests for deterministic 7-day conversion attribution rules and reconciliation.
"""
from datetime import datetime, timedelta
from cart_recover.models.orm_models import Attribution, Order, SendEvent

FMT = "%Y-%m-%dT%H:%M:%S"

def test_attribution_within_seven_day_window(db_session):
    """Verify all attributed orders fall strictly within the 7-day window [click_ts, click_ts + 7d]."""
    attrs = db_session.query(Attribution).all()
    assert len(attrs) > 0, "Attribution table has no rows"

    for a in attrs:
        click_dt = datetime.strptime(a.click_ts, FMT)
        order_dt = datetime.strptime(a.order_ts, FMT)
        assert click_dt <= order_dt, f"Order {a.order_id} occurred before the attributed click"
        assert order_dt <= click_dt + timedelta(days=7), f"Order {a.order_id} occurred after 7-day window"

def test_attribution_lag_hours_calculation(db_session):
    """Verify lag_hours accurately reflects the elapsed time between click and order."""
    attrs = db_session.query(Attribution).limit(30).all()
    for a in attrs:
        click_dt = datetime.strptime(a.click_ts, FMT)
        order_dt = datetime.strptime(a.order_ts, FMT)
        expected_lag = round((order_dt - click_dt).total_seconds() / 3600.0, 2)
        assert abs(a.lag_hours - expected_lag) < 0.05, f"Lag hours discrepancy in {a.attribution_id}"

def test_attributed_revenue_reconciliation(db_session):
    """Verify attributed revenue equals order total."""
    attrs = db_session.query(Attribution).limit(30).all()
    for a in attrs:
        order = db_session.query(Order).filter(Order.order_id == a.order_id).first()
        assert order is not None
        assert abs(a.attributed_revenue - order.order_total) < 0.01
