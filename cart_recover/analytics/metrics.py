"""
Analytical metric formulas and KPI computation engine.
All calculations operate on actual database records with explicit mathematical definitions.
"""
from dataclasses import dataclass
from typing import Dict, Any
from sqlalchemy.orm import Session
from cart_recover.database.repository import AnalyticsRepository


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    formula: str
    description: str
    unit: str


METRIC_DEFINITIONS = {
    "abandonment_rate": MetricDefinition(
        name="Cart Abandonment Rate",
        formula="Count(carts where abandoned_at IS NOT NULL) / Total(carts) * 100",
        description="Percentage of created carts that met or exceeded the 60-minute inactivity threshold without a purchase.",
        unit="%"
    ),
    "recovery_rate": MetricDefinition(
        name="Cart Recovery Rate",
        formula="Count(carts where status = 'recovered') / Count(carts where abandoned_at IS NOT NULL) * 100",
        description="Percentage of previously abandoned carts that subsequently placed an order within the measurement window.",
        unit="%"
    ),
    "suppression_rate": MetricDefinition(
        name="Message Suppression Rate",
        formula="Count(send_attempts where status != 'sent') / Total(send_attempts) * 100",
        description="Percentage of scheduled recovery attempts suppressed due to consent absence/withdrawal, frequency caps, or prior purchase.",
        unit="%"
    ),
    "delivery_rate": MetricDefinition(
        name="Delivery Rate",
        formula="Count(send_attempts where delivery_status = 'delivered') / Count(send_attempts where status = 'sent') * 100",
        description="Percentage of sent recovery messages confirmed delivered without bouncing.",
        unit="%"
    ),
    "conversion_rate_per_sent": MetricDefinition(
        name="Campaign Conversion Rate per Send",
        formula="Count(distinct orders attributed to campaign) / Count(messages sent) * 100",
        description="Conversion efficiency per delivered/sent recovery message.",
        unit="%"
    ),
    "revenue_per_send": MetricDefinition(
        name="Revenue Per Send (RPS)",
        formula="Sum(Attributed Revenue) / Count(messages sent)",
        description="Average monetary recovery generated per message sent.",
        unit="USD"
    ),
    "attribution_double_count_delta": MetricDefinition(
        name="Attribution Double Counting Delta",
        formula="Sum(Naive Attributed Revenue) - Sum(Deduplicated Attributed Revenue)",
        description="Financial reporting distortion caused by multi-campaign collision on the same order.",
        unit="USD"
    )
}


class MetricEngine:
    """Computes verified business KPIs with traceability to database tables."""

    def __init__(self, session: Session):
        self.repo = AnalyticsRepository(session)

    def calculate_all(self) -> Dict[str, Any]:
        kpis = self.repo.get_executive_kpis()
        sent = kpis["messages_sent"] or 1
        delivered = kpis.get("delivered_count", sent) # approximate if not queried

        # Computed rates
        suppression_rate = (kpis["messages_suppressed"] / (kpis["total_send_attempts"] or 1)) * 100
        rps = kpis["attributed_revenue_dedup"] / sent

        return {
            "kpis": kpis,
            "calculated_rates": {
                "abandonment_rate": kpis["abandonment_rate"],
                "recovery_rate": kpis["recovery_rate"],
                "suppression_rate": round(suppression_rate, 2),
                "revenue_per_send": round(rps, 2),
            },
            "definitions": METRIC_DEFINITIONS
        }
