"""
Tests for analytical KPI metrics, mathematical formulas, and revenue reconciliation.
"""
from cart_recover.analytics.metrics import MetricEngine, METRIC_DEFINITIONS

def test_metric_definitions_documented():
    required_metrics = [
        "abandonment_rate",
        "recovery_rate",
        "suppression_rate",
        "delivery_rate",
        "conversion_rate_per_sent",
        "revenue_per_send",
        "attribution_double_count_delta"
    ]
    for m in required_metrics:
        assert m in METRIC_DEFINITIONS
        assert METRIC_DEFINITIONS[m].formula != ""
        assert METRIC_DEFINITIONS[m].description != ""

def test_metric_engine_calculation(db_session):
    engine = MetricEngine(db_session)
    result = engine.calculate_all()

    kpis = result["kpis"]
    rates = result["calculated_rates"]

    assert rates["abandonment_rate"] >= 0.0
    assert rates["recovery_rate"] >= 0.0
    assert rates["suppression_rate"] >= 0.0
    assert rates["revenue_per_send"] >= 0.0

    # Reconciliation: Attributed revenue (dedup) must not exceed total revenue
    assert kpis["attributed_revenue_dedup"] <= kpis["total_order_revenue"]
