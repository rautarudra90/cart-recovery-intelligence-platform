"""
Data access repository providing high-level query methods
and aggregated analytical metrics from the SQLite relational store.
"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
from sqlalchemy import text, func, select
from sqlalchemy.orm import Session

from cart_recover.models.orm_models import (
    Customer, Cart, Order, SendAttempt, Attribution, Consent,
    Campaign, MessageTemplate, CartLine, Product, AbandonmentDecision
)

class AnalyticsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_executive_kpis(self) -> Dict[str, Any]:
        """
        Computes core executive KPIs strictly from relational tables:
        - Total carts created
        - Abandoned carts count & rate
        - Recovery messages sent vs suppressed
        - Recovered carts count & recovery rate
        - Total order revenue & attributed recovery revenue
        """
        # Cart metrics
        total_carts = self.session.query(func.count(Cart.cart_id)).scalar() or 0
        abandoned_carts = self.session.query(func.count(Cart.cart_id)).filter(Cart.abandoned_at.isnot(None)).scalar() or 0
        recovered_carts = self.session.query(func.count(Cart.cart_id)).filter(Cart.status == "recovered").scalar() or 0
        purchased_carts = self.session.query(func.count(Cart.cart_id)).filter(Cart.status == "purchased").scalar() or 0

        abandonment_rate = (abandoned_carts / total_carts * 100) if total_carts else 0.0
        recovery_rate = (recovered_carts / abandoned_carts * 100) if abandoned_carts else 0.0

        # Messaging metrics
        total_attempts = self.session.query(func.count(SendAttempt.send_id)).scalar() or 0
        sent_messages = self.session.query(func.count(SendAttempt.send_id)).filter(SendAttempt.status == "sent").scalar() or 0
        suppressed_messages = total_attempts - sent_messages

        # Financial metrics
        total_order_revenue = self.session.query(func.sum(Order.order_total)).scalar() or 0.0
        
        # Attributed revenue (deduplicated by order)
        dedup_attr_revenue = self.session.execute(
            text("""
                SELECT COALESCE(SUM(order_total), 0.0)
                FROM orders
                WHERE order_id IN (SELECT DISTINCT order_id FROM attributions)
            """)
        ).scalar() or 0.0

        naive_attr_revenue = self.session.query(func.sum(Attribution.attributed_revenue)).scalar() or 0.0

        return {
            "total_carts": total_carts,
            "abandoned_carts": abandoned_carts,
            "abandonment_rate": round(abandonment_rate, 2),
            "recovered_carts": recovered_carts,
            "recovery_rate": round(recovery_rate, 2),
            "purchased_direct_carts": purchased_carts,
            "total_send_attempts": total_attempts,
            "messages_sent": sent_messages,
            "messages_suppressed": suppressed_messages,
            "total_order_revenue": round(total_order_revenue, 2),
            "attributed_revenue_dedup": round(dedup_attr_revenue, 2),
            "attributed_revenue_naive": round(naive_attr_revenue, 2),
            "double_counted_revenue": round(naive_attr_revenue - dedup_attr_revenue, 2),
        }

    def get_cart_status_breakdown(self) -> pd.DataFrame:
        stmt = text("""
            SELECT status, COUNT(*) as count, 
                   ROUND(SUM(cart_total), 2) as total_value,
                   ROUND(AVG(cart_total), 2) as avg_value,
                   ROUND(AVG(item_count), 1) as avg_items
            FROM carts
            GROUP BY status
            ORDER BY count DESC
        """)
        return pd.read_sql(stmt, self.session.bind)

    def get_campaign_performance(self) -> pd.DataFrame:
        stmt = text("""
            SELECT 
                c.campaign_id,
                c.name,
                c.variant,
                c.channel,
                c.start_date,
                COUNT(s.send_id) as total_attempts,
                SUM(CASE WHEN s.status = 'sent' THEN 1 ELSE 0 END) as sent_count,
                SUM(CASE WHEN s.status != 'sent' THEN 1 ELSE 0 END) as suppressed_count,
                SUM(CASE WHEN s.delivery_status = 'delivered' THEN 1 ELSE 0 END) as delivered_count,
                COALESCE(att.attr_orders, 0) as attributed_orders,
                COALESCE(att.attr_revenue, 0.0) as attributed_revenue
            FROM campaigns c
            LEFT JOIN scheduled_messages m ON c.campaign_id = m.campaign_id
            LEFT JOIN send_attempts s ON m.message_id = s.message_id
            LEFT JOIN (
                SELECT campaign_id, COUNT(DISTINCT order_id) as attr_orders, ROUND(SUM(attributed_revenue), 2) as attr_revenue
                FROM attributions
                GROUP BY campaign_id
            ) att ON c.campaign_id = att.campaign_id
            GROUP BY c.campaign_id, c.name, c.variant, c.channel, c.start_date
            ORDER BY c.start_date DESC, c.variant
        """)
        return pd.read_sql(stmt, self.session.bind)

    def get_suppression_reasons(self) -> pd.DataFrame:
        stmt = text("""
            SELECT status as reason, COUNT(*) as count,
                   ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM send_attempts WHERE status != 'sent'), 2) as percentage
            FROM send_attempts
            WHERE status != 'sent'
            GROUP BY status
            ORDER BY count DESC
        """)
        return pd.read_sql(stmt, self.session.bind)

    def get_consent_summary(self) -> pd.DataFrame:
        stmt = text("""
            SELECT 
                channel,
                status,
                source,
                COUNT(*) as count
            FROM consents
            GROUP BY channel, status, source
            ORDER BY channel, count DESC
        """)
        return pd.read_sql(stmt, self.session.bind)

    def get_customer_summary(self) -> pd.DataFrame:
        stmt = text("""
            SELECT 
                region,
                signup_source,
                COUNT(*) as customer_count,
                SUM(CASE WHEN phone IS NOT NULL AND phone != '' THEN 1 ELSE 0 END) as with_phone
            FROM customers
            GROUP BY region, signup_source
            ORDER BY customer_count DESC
        """)
        return pd.read_sql(stmt, self.session.bind)

    def get_table_sample(self, table_name: str, limit: int = 50) -> pd.DataFrame:
        safe_tables = [
            "customers", "consents", "products", "sessions", "carts",
            "cart_lines", "cart_events", "abandonment_decisions",
            "campaigns", "message_templates", "scheduled_messages",
            "send_attempts", "send_events", "orders", "attributions"
        ]
        if table_name not in safe_tables:
            raise ValueError(f"Invalid table: {table_name}")
        stmt = text(f"SELECT * FROM {table_name} LIMIT :limit")
        return pd.read_sql(stmt, self.session.bind, params={"limit": limit})
