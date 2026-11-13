# Relational Database Schema & Entity Documentation

## 1. Schema Overview

`CartRecover-AI` uses an embedded SQLite database (`cart_recover.db`) with SQLAlchemy 2.0 ORM mappings.
The relational design incorporates 10 core business entities alongside bridge tables and append-only event ledgers to preserve full audit traceability.

---

## 2. Entity-Relationship Summary

| Entity Table | Primary Key | Foreign Keys | Cardinality | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`customers`** | `customer_id` | *None* | `1:N` Consents, `1:N` Sessions, `1:N` Carts, `1:N` Orders | Master record of registered customers. |
| **`consents`** | `consent_id` | `customer_id` -> `customers` | `N:1` Customer | Point-in-time audit ledger of opt-in/opt-out status by channel. |
| **`products`** | `sku` | *None* | `1:N` CartLines | Product catalog master containing unit prices and categories. |
| **`sessions`** | `session_id` | `customer_id` -> `customers` | `N:1` Customer, `N:M` Carts | Web/app browsing sessions with device metadata. |
| **`carts`** | `cart_id` | `customer_id` -> `customers` | `1:N` CartLines, `1:N` CartEvents, `1:1` Order | Cart master tracking status, item count, and recalculated totals. |
| **`cart_sessions`** | `(cart_id, session_id)` | `cart_id` -> `carts`, `session_id` -> `sessions` | `N:M` Bridge | Cross-device cart ownership and session association bridge. |
| **`cart_lines`** | `cart_line_id` | `cart_id` -> `carts`, `sku` -> `products` | `N:1` Cart, `N:1` Product | Line items representing SKU additions and unit pricing. |
| **`cart_events`** | `cart_event_id` | `cart_id` -> `carts`, `session_id` -> `sessions` | `N:1` Cart | Immutable append-only audit trail of all cart interactions. |
| **`abandonment_decisions`** | `decision_id` | `cart_id` -> `carts` | `1:1` Cart | Explicit audit log of recovery targeting vs holdout classification. |
| **`campaigns`** | `campaign_id` | *None* | `1:N` ScheduledMessages, `N:M` Templates | Recovery marketing campaigns segmented by variant and channel. |
| **`message_templates`** | `template_id` | *None* | `N:M` Campaigns | Message copy, discount configuration, and step sequencing. |
| **`campaign_templates`** | `(campaign_id, template_id)`| `campaign_id`, `template_id` | `N:M` Bridge | Associative table linking campaigns to message templates. |
| **`scheduled_messages`** | `message_id` | `cart_id`, `customer_id`, `campaign_id`, `template_id` | `1:1` SendAttempt | Planned communications prior to policy evaluation. |
| **`send_attempts`** | `send_id` | `message_id`, `customer_id`, `consent_id` | `1:N` SendEvents, `1:N` Attributions | Execution decision (sent vs suppressed) with policy evidence. |
| **`send_events`** | `event_id` | `send_id` -> `send_attempts` | `N:1` SendAttempt | Engagement events: delivered, opened, clicked, unsubscribed. |
| **`orders`** | `order_id` | `customer_id` -> `customers`, `cart_id` -> `carts` | `1:1` Cart, `1:N` Attributions | Completed purchases containing order totals and discounts. |
| **`attributions`** | `attribution_id` | `order_id`, `send_id`, `campaign_id` | `N:1` Order, `N:1` SendAttempt | 7-day last-click conversion attribution records. |

---

## 3. Detailed Table Specifications

### 3.1 `customers`
- `customer_id` (TEXT, PK): Unique customer identifier (`CUS-000001` pattern).
- `email` (TEXT, UNIQUE, NOT NULL): Contact email address.
- `phone` (TEXT, NULLABLE): E.164 phone number for SMS.
- `first_name` (TEXT, NOT NULL): First name.
- `region` (TEXT, NOT NULL): Geographic market (`NA`, `EU`, `APAC`, `LATAM`).
- `signup_source` (TEXT, NOT NULL): Channel origin (`web`, `app`, `store`).
- `created_at` (TEXT, NOT NULL): Registration timestamp (ISO-8601).

### 3.2 `consents`
- `consent_id` (TEXT, PK): Unique consent log identifier (`CON-000001`).
- `customer_id` (TEXT, FK -> customers, NOT NULL): Associated customer.
- `channel` (TEXT, NOT NULL): `email` or `sms`.
- `status` (TEXT, NOT NULL): `opt_in` or `opt_out`.
- `effective_from` (TEXT, NOT NULL): Start timestamp of consent state.
- `effective_to` (TEXT, NULLABLE): Superseded timestamp (NULL if currently active).
- `source` (TEXT, NOT NULL): Source of preference update (`signup`, `preference_center`, `unsubscribe_link`, `sms_stop`).

### 3.3 `carts`
- `cart_id` (TEXT, PK): Unique cart identifier (`CART-2026-000001`).
- `customer_id` (TEXT, FK -> customers, NULLABLE): NULL indicates guest cart.
- `created_at` (TEXT, NOT NULL): Cart inception timestamp.
- `last_activity_at` (TEXT, NOT NULL): Timestamp of latest item addition or update.
- `currency` (TEXT, NOT NULL): `USD`.
- `item_count` (INTEGER, NOT NULL): Sum of quantities across all line items.
- `cart_total` (NUMERIC(12,2), NOT NULL): Sum of line totals ($quantity \times unit\_price$).
- `status` (TEXT, NOT NULL): `purchased`, `abandoned`, or `recovered`.
- `abandoned_at` (TEXT, NULLABLE): Timestamp when inactivity crossed 60 minutes.

### 3.4 `send_attempts`
- `send_id` (TEXT, PK): Unique dispatch attempt identifier (`SEND-2026-000001`).
- `message_id` (TEXT, FK -> scheduled_messages, UNIQUE, NOT NULL).
- `customer_id` (TEXT, FK -> customers, NOT NULL).
- `channel` (TEXT, NOT NULL): `email` or `sms`.
- `attempt_ts` (TEXT, NOT NULL): Scheduled dispatch timestamp.
- `status` (TEXT, NOT NULL): `sent`, `suppressed_no_consent`, `suppressed_consent_withdrawn`, `suppressed_frequency_cap`, `suppressed_already_purchased`.
- `consent_id` (TEXT, FK -> consents, NULLABLE): Evaluated consent row at `attempt_ts`.
- `sends_last_24h` (INTEGER, NOT NULL): Rolling 24-hour sent message counter.
- `sends_last_7d` (INTEGER, NOT NULL): Rolling 7-day sent message counter.
- `delivery_status` (TEXT, NULLABLE): `delivered` or `bounced` (only if status is `sent`).

### 3.5 `attributions`
- `attribution_id` (TEXT, PK): Unique attribution record (`ATT-2026-000001`).
- `order_id` (TEXT, FK -> orders, NOT NULL): Attributed conversion order.
- `send_id` (TEXT, FK -> send_attempts, NOT NULL): Driving recovery message attempt.
- `message_id` (TEXT, FK -> scheduled_messages, NOT NULL).
- `campaign_id` (TEXT, FK -> campaigns, NOT NULL).
- `model` (TEXT, NOT NULL): `last_click`.
- `window_days` (INTEGER, NOT NULL): `7`.
- `click_ts` (TEXT, NOT NULL): Timestamp of qualifying customer click.
- `order_ts` (TEXT, NOT NULL): Purchase timestamp ($click\_ts \le order\_ts \le click\_ts + 7d$).
- `lag_hours` (NUMERIC(12,2), NOT NULL): Elapsed conversion hours.
- `attributed_revenue` (NUMERIC(12,2), NOT NULL): Attributed financial revenue.
