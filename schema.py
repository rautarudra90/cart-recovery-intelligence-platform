"""Single source of truth for the cart-recovery dataset: tables, fields, keys, enums.

Used by generate_data.py (CSV headers, SQL DDL, data dictionary) and validate_data.py
(enum / required / pattern checks).  Empty CSV cell == NULL for optional fields.
"""


def F(name, typ, req=True, allowed="", unit="", uniq=False, rule=""):
    return dict(name=name, type=typ, required=req, allowed=allowed, unit=unit, unique=uniq, rule=rule)


CHANNELS = ["email", "sms"]
VARIANTS = ["V1", "V2", "V3"]
SEND_STATUSES = ["sent", "suppressed_no_consent", "suppressed_consent_withdrawn",
                 "suppressed_frequency_cap", "suppressed_already_purchased"]
EVENT_TYPES = ["cart_created", "item_added", "quantity_updated", "checkout_started",
               "abandoned_flagged", "cart_resumed", "purchased"]

TABLES = {
    "customers": dict(
        desc="Master. Known (registered) shoppers. Guest carts have no customer row.",
        pk=["customer_id"], id_regex=r"CUS-\d{6}", fks=[],
        cardinality="Customer 1:N Cart, 1:N Consent, 1:N Session, 1:N Order (all optional on the child side: guests).",
        fields=[
            F("customer_id", "string", uniq=True, rule="CUS-000001 pattern; immutable"),
            F("email", "string", uniq=True, rule="synthetic address on reserved example.test domain"),
            F("phone", "string", False, uniq=True, rule="synthetic E.164-like number; NULL => no SMS channel"),
            F("first_name", "string"),
            F("region", "string", allowed=["NA", "EU", "APAC", "LATAM"]),
            F("signup_source", "string", allowed=["web", "app", "store"]),
            F("created_at", "timestamp", rule="<= first session/cart of the customer"),
        ]),
    "consents": dict(
        desc="Master + event history. One row per consent state change per customer/channel; never updated in place "
             "(effective_to is the only derived back-fill = next row's effective_from).",
        pk=["consent_id"], id_regex=r"CON-\d{6,}",
        fks=[("customer_id", "customers", "customer_id")],
        cardinality="Customer 1:N Consent; per (customer, channel) rows form a contiguous, non-overlapping timeline.",
        fields=[
            F("consent_id", "string", uniq=True, rule="CON-000001 pattern"),
            F("customer_id", "string", rule="FK customers"),
            F("channel", "string", allowed=CHANNELS),
            F("status", "string", allowed=["opt_in", "opt_out"], rule="consecutive rows for a channel alternate or restate state"),
            F("effective_from", "timestamp", rule=">= customer.created_at"),
            F("effective_to", "timestamp", False, rule="NULL = current; == next row effective_from"),
            F("source", "string", allowed=["signup", "preference_center", "unsubscribe_link", "sms_stop"]),
        ]),
    "products": dict(
        desc="Master. Small synthetic catalogue (no external data).",
        pk=["sku"], id_regex=r"SKU-\d{4}", fks=[], cardinality="Product 1:N CartLine.",
        fields=[
            F("sku", "string", uniq=True, rule="SKU-0001 pattern"),
            F("product_name", "string"),
            F("category", "string"),
            F("unit_price", "decimal", unit="USD", rule="> 0, 2 dp"),
        ]),
    "sessions": dict(
        desc="Master/event. Browsing sessions. A cart can span several sessions on different devices.",
        pk=["session_id"], id_regex=r"SES-2026-\d{6}",
        fks=[("customer_id", "customers", "customer_id")],
        cardinality="Customer 0..1:N Session (guest sessions have NULL customer); Cart N:M Session via cart_sessions.",
        fields=[
            F("session_id", "string", uniq=True, rule="SES-2026-000001; numbered by started_at"),
            F("customer_id", "string", False, rule="FK customers; NULL for guests"),
            F("device_id", "string", rule="stable per customer device; one customer has 1-3 devices"),
            F("device_type", "string", allowed=["mobile", "desktop", "tablet"]),
            F("purpose", "string", allowed=["shopping", "recovery_return"]),
            F("started_at", "timestamp"),
            F("ended_at", "timestamp", rule=">= started_at and >= last cart event in the session"),
        ]),
    "carts": dict(
        desc="Master. Current-state view of a cart; full history lives in cart_events.",
        pk=["cart_id"], id_regex=r"CART-2026-\d{6}",
        fks=[("customer_id", "customers", "customer_id")],
        cardinality="Customer 0..1:N Cart; Cart 1:N CartLine; Cart 1:N CartEvent; Cart 0..1:1 Order.",
        fields=[
            F("cart_id", "string", uniq=True, rule="CART-2026-000001; numbered by created_at"),
            F("customer_id", "string", False, rule="FK customers; NULL = guest (not contactable)"),
            F("created_at", "timestamp"),
            F("last_activity_at", "timestamp", rule="time of last cart-modifying/checkout event; >= created_at"),
            F("currency", "string", allowed=["USD"]),
            F("item_count", "int", unit="units", rule="sum(cart_lines.quantity)"),
            F("cart_total", "decimal", unit="USD", rule="== sum(cart_lines.line_total) (violated only by labelled stale-total cases)"),
            F("status", "string", allowed=["purchased", "abandoned", "recovered"],
              rule="purchased=ordered inside window; recovered=abandoned then ordered; abandoned=never ordered"),
            F("abandoned_at", "timestamp", False,
              rule="== last_activity_at + 60 min when flagged; NULL if never flagged"),
        ]),
    "cart_sessions": dict(
        desc="Bridge (N:M) Cart <-> Session.",
        pk=["cart_id", "session_id"], id_regex=None,
        fks=[("cart_id", "carts", "cart_id"), ("session_id", "sessions", "session_id")],
        cardinality="Cart N:M Session.",
        fields=[
            F("cart_id", "string", rule="FK carts"),
            F("session_id", "string", rule="FK sessions"),
            F("role", "string", allowed=["created", "modified", "recovery_visit"]),
        ]),
    "cart_lines": dict(
        desc="Child. Final line items of the cart (quantity reflects the last quantity update).",
        pk=["cart_line_id"], id_regex=r"LINE-2026-\d{6}",
        fks=[("cart_id", "carts", "cart_id"), ("sku", "products", "sku")],
        cardinality="Cart 1:N CartLine; Product 1:N CartLine.",
        fields=[
            F("cart_line_id", "string", uniq=True, rule="LINE-2026-000001"),
            F("cart_id", "string", rule="FK carts"),
            F("line_no", "int", rule="1..n within the cart; unique per cart"),
            F("sku", "string", rule="FK products"),
            F("quantity", "int", unit="units", rule="1..5"),
            F("unit_price", "decimal", unit="USD", rule="== products.unit_price at add time"),
            F("line_total", "decimal", unit="USD", rule="== quantity * unit_price"),
            F("added_at", "timestamp", rule=">= cart.created_at"),
        ]),
    "cart_events": dict(
        desc="Event history of cart lifecycle (append-only).",
        pk=["cart_event_id"], id_regex=r"CEV-2026-\d{6,}",
        fks=[("cart_id", "carts", "cart_id"), ("session_id", "sessions", "session_id"),
             ("cart_line_id", "cart_lines", "cart_line_id")],
        cardinality="Cart 1:N CartEvent.",
        fields=[
            F("cart_event_id", "string", uniq=True, rule="CEV-2026-000001; numbered by event_ts"),
            F("cart_id", "string", rule="FK carts"),
            F("session_id", "string", False, rule="FK sessions; NULL for system events (abandoned_flagged)"),
            F("event_type", "string", allowed=EVENT_TYPES),
            F("event_ts", "timestamp"),
            F("cart_line_id", "string", False, rule="FK cart_lines for item_added/quantity_updated"),
            F("old_quantity", "int", False, rule="quantity_updated only"),
            F("new_quantity", "int", False, rule="item_added / quantity_updated"),
        ]),
    "abandonment_decisions": dict(
        desc="Event. Explicit decision taken when a cart is flagged abandoned (traceability of targeting).",
        pk=["decision_id"], id_regex=r"ABD-2026-\d{6}",
        fks=[("cart_id", "carts", "cart_id")],
        cardinality="Cart 0..1:1 AbandonmentDecision.",
        fields=[
            F("decision_id", "string", uniq=True, rule="ABD-2026-000001"),
            F("cart_id", "string", uniq=True, rule="FK carts; exactly the carts having an abandoned_flagged event"),
            F("abandoned_at", "timestamp", rule="== carts.abandoned_at"),
            F("recovery_decision", "string",
              allowed=["targeted", "holdout", "ineligible_guest", "ineligible_low_value"]),
            F("reason", "string"),
        ]),
    "campaigns": dict(
        desc="Master. Weekly recovery campaign per variant (created on first scheduled message).",
        pk=["campaign_id"], id_regex=r"CMP-2026-\d{6}", fks=[],
        cardinality="Campaign N:M MessageTemplate via campaign_templates; Campaign 1:N ScheduledMessage.",
        fields=[
            F("campaign_id", "string", uniq=True, rule="CMP-2026-000001; numbered by first use"),
            F("name", "string"),
            F("variant", "string", allowed=VARIANTS),
            F("channel", "string", allowed=CHANNELS),
            F("start_date", "date", rule="Monday of the ISO week"),
            F("end_date", "date", rule="== start_date + 6 days"),
            F("delay_minutes", "int", unit="minutes", rule="step-1 delay after abandoned_at"),
            F("attribution_window_days", "int", unit="days", allowed=[7]),
            F("status", "string", allowed=["completed"]),
        ]),
    "message_templates": dict(
        desc="Master. One template per variant x step.",
        pk=["template_id"], id_regex=r"TPL-V\d-S\d", fks=[],
        cardinality="Template N:M Campaign.",
        fields=[
            F("template_id", "string", uniq=True, rule="TPL-V1-S1 pattern"),
            F("variant", "string", allowed=VARIANTS),
            F("channel", "string", allowed=CHANNELS),
            F("step", "int", allowed=[1, 2]),
            F("subject", "string", False, rule="email only"),
            F("discount_pct", "int", unit="percent", allowed=[0, 5, 10]),
            F("version", "int"),
            F("effective_from", "date"),
        ]),
    "campaign_templates": dict(
        desc="Bridge (N:M) Campaign <-> MessageTemplate.",
        pk=["campaign_id", "template_id"], id_regex=None,
        fks=[("campaign_id", "campaigns", "campaign_id"), ("template_id", "message_templates", "template_id")],
        cardinality="Campaign N:M MessageTemplate.",
        fields=[F("campaign_id", "string", rule="FK campaigns"), F("template_id", "string", rule="FK message_templates")]),
    "scheduled_messages": dict(
        desc="Event. A planned recovery message for a cart/step (one per cart x step).",
        pk=["message_id"], id_regex=r"MSG-CART-2026-\d{6}-\d{2}",
        fks=[("cart_id", "carts", "cart_id"), ("customer_id", "customers", "customer_id"),
             ("campaign_id", "campaigns", "campaign_id"), ("template_id", "message_templates", "template_id")],
        cardinality="Cart 1:N ScheduledMessage (max 2); ScheduledMessage 1:1 SendAttempt.",
        fields=[
            F("message_id", "string", uniq=True, rule="MSG-<cart_id>-<step 2 digits>"),
            F("cart_id", "string", rule="FK carts; cart must be abandoned"),
            F("customer_id", "string", rule="FK customers; == carts.customer_id"),
            F("campaign_id", "string", rule="FK campaigns"),
            F("template_id", "string", rule="FK message_templates; template step == step"),
            F("step", "int", allowed=[1, 2]),
            F("channel", "string", allowed=CHANNELS),
            F("planned_ts", "timestamp", rule=">= carts.abandoned_at"),
            F("scheduled_ts", "timestamp", rule="planned_ts after SMS quiet-hours deferral (21:00-08:00)"),
        ]),
    "send_attempts": dict(
        desc="Event. Final decision for each scheduled message: sent or suppressed (with reason and evidence).",
        pk=["send_id"], id_regex=r"SEND-2026-\d{6}",
        fks=[("message_id", "scheduled_messages", "message_id"), ("customer_id", "customers", "customer_id"),
             ("consent_id", "consents", "consent_id")],
        cardinality="ScheduledMessage 1:1 SendAttempt; SendAttempt 1:N SendEvent.",
        fields=[
            F("send_id", "string", uniq=True, rule="SEND-2026-000001; numbered by attempt_ts"),
            F("message_id", "string", uniq=True, rule="FK scheduled_messages"),
            F("customer_id", "string", rule="FK customers"),
            F("channel", "string", allowed=CHANNELS),
            F("attempt_ts", "timestamp", rule="== scheduled_ts"),
            F("status", "string", allowed=SEND_STATUSES),
            F("consent_id", "string", False, rule="FK consents: the consent row evaluated at attempt_ts"),
            F("sends_last_24h", "int", rule="sent messages to customer in the preceding 24h (cap 1)"),
            F("sends_last_7d", "int", rule="sent messages to customer in the preceding 7d (cap 3)"),
            F("delivery_status", "string", False, allowed=["delivered", "bounced"], rule="only when status == sent"),
        ]),
    "send_events": dict(
        desc="Event history for sent messages (delivery/open/click/unsubscribe).",
        pk=["event_id"], id_regex=r"EVT-2026-\d{6}",
        fks=[("send_id", "send_attempts", "send_id")],
        cardinality="SendAttempt 1:N SendEvent.",
        fields=[
            F("event_id", "string", uniq=True, rule="EVT-2026-000001; numbered by event_ts"),
            F("send_id", "string", rule="FK send_attempts with status sent"),
            F("event_type", "string", allowed=["delivered", "bounced", "opened", "clicked", "unsubscribed"]),
            F("event_ts", "timestamp", rule=">= send attempt_ts; opened/clicked only after delivered"),
        ]),
    "orders": dict(
        desc="Transaction. One order per purchased/recovered cart.",
        pk=["order_id"], id_regex=r"ORD-2026-\d{6}",
        fks=[("customer_id", "customers", "customer_id"), ("cart_id", "carts", "cart_id"),
             ("session_id", "sessions", "session_id")],
        cardinality="Cart 1:0..1 Order; Order 0..N Attribution (rule: exactly 0..1).",
        fields=[
            F("order_id", "string", uniq=True, rule="ORD-2026-000001; numbered by order_ts"),
            F("customer_id", "string", False, rule="FK customers; NULL for guest orders"),
            F("cart_id", "string", uniq=True, rule="FK carts"),
            F("session_id", "string", rule="FK sessions: purchasing session"),
            F("order_ts", "timestamp", rule="> cart.created_at"),
            F("subtotal", "decimal", unit="USD", rule="== sum(cart_lines.line_total)"),
            F("discount_amount", "decimal", unit="USD", rule="== round(subtotal * pct/100) when promo_code set"),
            F("shipping_fee", "decimal", unit="USD", rule="5.99 if subtotal < 75.00 else 0.00"),
            F("order_total", "decimal", unit="USD", rule="== subtotal - discount_amount + shipping_fee"),
            F("promo_code", "string", False, rule="RECOVER5 / RECOVER10 (valid 7 days after the click that issued it)"),
        ]),
    "attributions": dict(
        desc="Derived. Last-click attribution of an order to one SendAttempt within 7 days of the click.",
        pk=["attribution_id"], id_regex=r"ATT-2026-\d{6}",
        fks=[("order_id", "orders", "order_id"), ("send_id", "send_attempts", "send_id"),
             ("message_id", "scheduled_messages", "message_id"), ("campaign_id", "campaigns", "campaign_id")],
        cardinality="Order 0..1:1 Attribution (more than one is a defect); SendAttempt 1:N Attribution.",
        fields=[
            F("attribution_id", "string", uniq=True, rule="ATT-2026-000001"),
            F("order_id", "string", rule="FK orders; should be unique"),
            F("send_id", "string", rule="FK send_attempts"),
            F("message_id", "string", rule="FK scheduled_messages"),
            F("campaign_id", "string", rule="FK campaigns"),
            F("model", "string", allowed=["last_click"]),
            F("window_days", "int", unit="days", allowed=[7]),
            F("click_ts", "timestamp", rule="<= order_ts <= click_ts + window_days"),
            F("order_ts", "timestamp", rule="== orders.order_ts"),
            F("lag_hours", "decimal", unit="hours", rule="(order_ts - click_ts) in hours, 2 dp"),
            F("attributed_revenue", "decimal", unit="USD", rule="== orders.order_total"),
        ]),
}

TABLE_ORDER = list(TABLES.keys())  # parents before children

SQL_TYPES = {"string": "TEXT", "int": "INTEGER", "decimal": "NUMERIC(12,2)", "timestamp": "TEXT", "date": "TEXT"}


def columns(table):
    return [f["name"] for f in TABLES[table]["fields"]]
