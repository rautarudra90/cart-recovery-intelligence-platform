# Data dictionary

Empty CSV cell = NULL (allowed only where Required = N). Timestamps are naive ISO-8601 (store-local), money is USD with 2 dp.


## customers

Master. Known (registered) shoppers. Guest carts have no customer row.

* **Primary key:** customer_id
* **Foreign keys:** none
* **Cardinality:** Customer 1:N Cart, 1:N Consent, 1:N Session, 1:N Order (all optional on the child side: guests).

| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| customer_id | string | Y |  |  | Y | CUS-000001 pattern; immutable |
| email | string | Y |  |  | Y | synthetic address on reserved example.test domain |
| phone | string | N |  |  | Y | synthetic E.164-like number; NULL => no SMS channel |
| first_name | string | Y |  |  |  |  |
| region | string | Y | NA, EU, APAC, LATAM |  |  |  |
| signup_source | string | Y | web, app, store |  |  |  |
| created_at | timestamp | Y |  |  |  | <= first session/cart of the customer |

## consents

Master + event history. One row per consent state change per customer/channel; never updated in place (effective_to is the only derived back-fill = next row's effective_from).

* **Primary key:** consent_id
* **Foreign keys:** customer_id -> customers.customer_id
* **Cardinality:** Customer 1:N Consent; per (customer, channel) rows form a contiguous, non-overlapping timeline.

| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| consent_id | string | Y |  |  | Y | CON-000001 pattern |
| customer_id | string | Y |  |  |  | FK customers |
| channel | string | Y | email, sms |  |  |  |
| status | string | Y | opt_in, opt_out |  |  | consecutive rows for a channel alternate or restate state |
| effective_from | timestamp | Y |  |  |  | >= customer.created_at |
| effective_to | timestamp | N |  |  |  | NULL = current; == next row effective_from |
| source | string | Y | signup, preference_center, unsubscribe_link, sms_stop |  |  |  |

## products

Master. Small synthetic catalogue (no external data).

* **Primary key:** sku
* **Foreign keys:** none
* **Cardinality:** Product 1:N CartLine.

| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| sku | string | Y |  |  | Y | SKU-0001 pattern |
| product_name | string | Y |  |  |  |  |
| category | string | Y |  |  |  |  |
| unit_price | decimal | Y |  | USD |  | > 0, 2 dp |

## sessions

Master/event. Browsing sessions. A cart can span several sessions on different devices.

* **Primary key:** session_id
* **Foreign keys:** customer_id -> customers.customer_id
* **Cardinality:** Customer 0..1:N Session (guest sessions have NULL customer); Cart N:M Session via cart_sessions.

| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| session_id | string | Y |  |  | Y | SES-2026-000001; numbered by started_at |
| customer_id | string | N |  |  |  | FK customers; NULL for guests |
| device_id | string | Y |  |  |  | stable per customer device; one customer has 1-3 devices |
| device_type | string | Y | mobile, desktop, tablet |  |  |  |
| purpose | string | Y | shopping, recovery_return |  |  |  |
| started_at | timestamp | Y |  |  |  |  |
| ended_at | timestamp | Y |  |  |  | >= started_at and >= last cart event in the session |

## carts

Master. Current-state view of a cart; full history lives in cart_events.

* **Primary key:** cart_id
* **Foreign keys:** customer_id -> customers.customer_id
* **Cardinality:** Customer 0..1:N Cart; Cart 1:N CartLine; Cart 1:N CartEvent; Cart 0..1:1 Order.

| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| cart_id | string | Y |  |  | Y | CART-2026-000001; numbered by created_at |
| customer_id | string | N |  |  |  | FK customers; NULL = guest (not contactable) |
| created_at | timestamp | Y |  |  |  |  |
| last_activity_at | timestamp | Y |  |  |  | time of last cart-modifying/checkout event; >= created_at |
| currency | string | Y | USD |  |  |  |
| item_count | int | Y |  | units |  | sum(cart_lines.quantity) |
| cart_total | decimal | Y |  | USD |  | == sum(cart_lines.line_total) (violated only by labelled stale-total cases) |
| status | string | Y | purchased, abandoned, recovered |  |  | purchased=ordered inside window; recovered=abandoned then ordered; abandoned=never ordered |
| abandoned_at | timestamp | N |  |  |  | == last_activity_at + 60 min when flagged; NULL if never flagged |

## cart_sessions

Bridge (N:M) Cart <-> Session.

* **Primary key:** cart_id, session_id
* **Foreign keys:** cart_id -> carts.cart_id; session_id -> sessions.session_id
* **Cardinality:** Cart N:M Session.

| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| cart_id | string | Y |  |  |  | FK carts |
| session_id | string | Y |  |  |  | FK sessions |
| role | string | Y | created, modified, recovery_visit |  |  |  |

## cart_lines

Child. Final line items of the cart (quantity reflects the last quantity update).

* **Primary key:** cart_line_id
* **Foreign keys:** cart_id -> carts.cart_id; sku -> products.sku
* **Cardinality:** Cart 1:N CartLine; Product 1:N CartLine.

| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| cart_line_id | string | Y |  |  | Y | LINE-2026-000001 |
| cart_id | string | Y |  |  |  | FK carts |
| line_no | int | Y |  |  |  | 1..n within the cart; unique per cart |
| sku | string | Y |  |  |  | FK products |
| quantity | int | Y |  | units |  | 1..5 |
| unit_price | decimal | Y |  | USD |  | == products.unit_price at add time |
| line_total | decimal | Y |  | USD |  | == quantity * unit_price |
| added_at | timestamp | Y |  |  |  | >= cart.created_at |

## cart_events

Event history of cart lifecycle (append-only).

* **Primary key:** cart_event_id
* **Foreign keys:** cart_id -> carts.cart_id; session_id -> sessions.session_id; cart_line_id -> cart_lines.cart_line_id
* **Cardinality:** Cart 1:N CartEvent.

| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| cart_event_id | string | Y |  |  | Y | CEV-2026-000001; numbered by event_ts |
| cart_id | string | Y |  |  |  | FK carts |
| session_id | string | N |  |  |  | FK sessions; NULL for system events (abandoned_flagged) |
| event_type | string | Y | cart_created, item_added, quantity_updated, checkout_started, abandoned_flagged, cart_resumed, purchased |  |  |  |
| event_ts | timestamp | Y |  |  |  |  |
| cart_line_id | string | N |  |  |  | FK cart_lines for item_added/quantity_updated |
| old_quantity | int | N |  |  |  | quantity_updated only |
| new_quantity | int | N |  |  |  | item_added / quantity_updated |

## abandonment_decisions

Event. Explicit decision taken when a cart is flagged abandoned (traceability of targeting).

* **Primary key:** decision_id
* **Foreign keys:** cart_id -> carts.cart_id
* **Cardinality:** Cart 0..1:1 AbandonmentDecision.

| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| decision_id | string | Y |  |  | Y | ABD-2026-000001 |
| cart_id | string | Y |  |  | Y | FK carts; exactly the carts having an abandoned_flagged event |
| abandoned_at | timestamp | Y |  |  |  | == carts.abandoned_at |
| recovery_decision | string | Y | targeted, holdout, ineligible_guest, ineligible_low_value |  |  |  |
| reason | string | Y |  |  |  |  |

## campaigns

Master. Weekly recovery campaign per variant (created on first scheduled message).

* **Primary key:** campaign_id
* **Foreign keys:** none
* **Cardinality:** Campaign N:M MessageTemplate via campaign_templates; Campaign 1:N ScheduledMessage.

| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| campaign_id | string | Y |  |  | Y | CMP-2026-000001; numbered by first use |
| name | string | Y |  |  |  |  |
| variant | string | Y | V1, V2, V3 |  |  |  |
| channel | string | Y | email, sms |  |  |  |
| start_date | date | Y |  |  |  | Monday of the ISO week |
| end_date | date | Y |  |  |  | == start_date + 6 days |
| delay_minutes | int | Y |  | minutes |  | step-1 delay after abandoned_at |
| attribution_window_days | int | Y | 7 | days |  |  |
| status | string | Y | completed |  |  |  |

## message_templates

Master. One template per variant x step.

* **Primary key:** template_id
* **Foreign keys:** none
* **Cardinality:** Template N:M Campaign.

| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| template_id | string | Y |  |  | Y | TPL-V1-S1 pattern |
| variant | string | Y | V1, V2, V3 |  |  |  |
| channel | string | Y | email, sms |  |  |  |
| step | int | Y | 1, 2 |  |  |  |
| subject | string | N |  |  |  | email only |
| discount_pct | int | Y | 0, 5, 10 | percent |  |  |
| version | int | Y |  |  |  |  |
| effective_from | date | Y |  |  |  |  |

## campaign_templates

Bridge (N:M) Campaign <-> MessageTemplate.

* **Primary key:** campaign_id, template_id
* **Foreign keys:** campaign_id -> campaigns.campaign_id; template_id -> message_templates.template_id
* **Cardinality:** Campaign N:M MessageTemplate.

| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| campaign_id | string | Y |  |  |  | FK campaigns |
| template_id | string | Y |  |  |  | FK message_templates |

## scheduled_messages

Event. A planned recovery message for a cart/step (one per cart x step).

* **Primary key:** message_id
* **Foreign keys:** cart_id -> carts.cart_id; customer_id -> customers.customer_id; campaign_id -> campaigns.campaign_id; template_id -> message_templates.template_id
* **Cardinality:** Cart 1:N ScheduledMessage (max 2); ScheduledMessage 1:1 SendAttempt.

| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| message_id | string | Y |  |  | Y | MSG-<cart_id>-<step 2 digits> |
| cart_id | string | Y |  |  |  | FK carts; cart must be abandoned |
| customer_id | string | Y |  |  |  | FK customers; == carts.customer_id |
| campaign_id | string | Y |  |  |  | FK campaigns |
| template_id | string | Y |  |  |  | FK message_templates; template step == step |
| step | int | Y | 1, 2 |  |  |  |
| channel | string | Y | email, sms |  |  |  |
| planned_ts | timestamp | Y |  |  |  | >= carts.abandoned_at |
| scheduled_ts | timestamp | Y |  |  |  | planned_ts after SMS quiet-hours deferral (21:00-08:00) |

## send_attempts

Event. Final decision for each scheduled message: sent or suppressed (with reason and evidence).

* **Primary key:** send_id
* **Foreign keys:** message_id -> scheduled_messages.message_id; customer_id -> customers.customer_id; consent_id -> consents.consent_id
* **Cardinality:** ScheduledMessage 1:1 SendAttempt; SendAttempt 1:N SendEvent.

| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| send_id | string | Y |  |  | Y | SEND-2026-000001; numbered by attempt_ts |
| message_id | string | Y |  |  | Y | FK scheduled_messages |
| customer_id | string | Y |  |  |  | FK customers |
| channel | string | Y | email, sms |  |  |  |
| attempt_ts | timestamp | Y |  |  |  | == scheduled_ts |
| status | string | Y | sent, suppressed_no_consent, suppressed_consent_withdrawn, suppressed_frequency_cap, suppressed_already_purchased |  |  |  |
| consent_id | string | N |  |  |  | FK consents: the consent row evaluated at attempt_ts |
| sends_last_24h | int | Y |  |  |  | sent messages to customer in the preceding 24h (cap 1) |
| sends_last_7d | int | Y |  |  |  | sent messages to customer in the preceding 7d (cap 3) |
| delivery_status | string | N | delivered, bounced |  |  | only when status == sent |

## send_events

Event history for sent messages (delivery/open/click/unsubscribe).

* **Primary key:** event_id
* **Foreign keys:** send_id -> send_attempts.send_id
* **Cardinality:** SendAttempt 1:N SendEvent.

| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| event_id | string | Y |  |  | Y | EVT-2026-000001; numbered by event_ts |
| send_id | string | Y |  |  |  | FK send_attempts with status sent |
| event_type | string | Y | delivered, bounced, opened, clicked, unsubscribed |  |  |  |
| event_ts | timestamp | Y |  |  |  | >= send attempt_ts; opened/clicked only after delivered |

## orders

Transaction. One order per purchased/recovered cart.

* **Primary key:** order_id
* **Foreign keys:** customer_id -> customers.customer_id; cart_id -> carts.cart_id; session_id -> sessions.session_id
* **Cardinality:** Cart 1:0..1 Order; Order 0..N Attribution (rule: exactly 0..1).

| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| order_id | string | Y |  |  | Y | ORD-2026-000001; numbered by order_ts |
| customer_id | string | N |  |  |  | FK customers; NULL for guest orders |
| cart_id | string | Y |  |  | Y | FK carts |
| session_id | string | Y |  |  |  | FK sessions: purchasing session |
| order_ts | timestamp | Y |  |  |  | > cart.created_at |
| subtotal | decimal | Y |  | USD |  | == sum(cart_lines.line_total) |
| discount_amount | decimal | Y |  | USD |  | == round(subtotal * pct/100) when promo_code set |
| shipping_fee | decimal | Y |  | USD |  | 5.99 if subtotal < 75.00 else 0.00 |
| order_total | decimal | Y |  | USD |  | == subtotal - discount_amount + shipping_fee |
| promo_code | string | N |  |  |  | RECOVER5 / RECOVER10 (valid 7 days after the click that issued it) |

## attributions

Derived. Last-click attribution of an order to one SendAttempt within 7 days of the click.

* **Primary key:** attribution_id
* **Foreign keys:** order_id -> orders.order_id; send_id -> send_attempts.send_id; message_id -> scheduled_messages.message_id; campaign_id -> campaigns.campaign_id
* **Cardinality:** Order 0..1:1 Attribution (more than one is a defect); SendAttempt 1:N Attribution.

| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| attribution_id | string | Y |  |  | Y | ATT-2026-000001 |
| order_id | string | Y |  |  |  | FK orders; should be unique |
| send_id | string | Y |  |  |  | FK send_attempts |
| message_id | string | Y |  |  |  | FK scheduled_messages |
| campaign_id | string | Y |  |  |  | FK campaigns |
| model | string | Y | last_click |  |  |  |
| window_days | int | Y | 7 | days |  |  |
| click_ts | timestamp | Y |  |  |  | <= order_ts <= click_ts + window_days |
| order_ts | timestamp | Y |  |  |  | == orders.order_ts |
| lag_hours | decimal | Y |  | hours |  | (order_ts - click_ts) in hours, 2 dp |
| attributed_revenue | decimal | Y |  | USD |  | == orders.order_total |
