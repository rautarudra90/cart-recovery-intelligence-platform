# Cart-abandonment recovery dataset

Synthetic, fully reproducible data for: identify abandoned carts -> respect consent -> run personalised recovery
campaigns -> attribute conversions. **No external/public data is used** (see `source_manifest.json`); all names,
e-mails (`@example.test`) and phones are fabricated.

* Generator command: `python generate_data.py --out <dir> --seed 20261022 --carts 2000 --abandoned 800 --sends 400 --customers 800`
* Fixed seed: `20261022` (carts=2000, abandoned=800, sends=400, customers=800)
* Validate: `python validate_data.py --data <dir>`; reproducibility: `python repro_check.py --out <dir>`

## Files
`*.csv` one per entity (see `data_dictionary.md` / `data_dictionary.json`), `schema.sql` (DDL with PK/FK),
`seed.sql` (INSERTs), `ground_truth/` (**labels only - never use as model/analysis input**), `source_manifest.json`
(row counts + SHA-256), `validation_summary.json`, `reproducibility_report.json`.

| table | rows |
|---|---|
| customers | 800 |
| consents | 1466 |
| products | 80 |
| sessions | 2424 |
| carts | 2000 |
| cart_sessions | 2424 |
| cart_lines | 4195 |
| cart_events | 10367 |
| abandonment_decisions | 803 |
| campaigns | 109 |
| message_templates | 6 |
| campaign_templates | 218 |
| scheduled_messages | 400 |
| send_attempts | 400 |
| send_events | 408 |
| orders | 1358 |
| attributions | 18 |

## Documented rules
1. **Abandonment (time based):** a cart is abandoned iff it has no order at or before `last_activity_at + 60 min` (boundary inclusive: an order exactly at +60 min is *not* abandoned; +61 min is). `abandoned_at = last_activity_at + 60 min`; an `abandoned_flagged` event and an `abandonment_decisions` row are written. Later orders turn the cart into `recovered` (history preserved in `cart_events`).
2. **Eligibility:** guests (no customer) and carts < $15.00 are not messaged. Remaining carts are randomly split into `targeted` (send budget) and `holdout` (control group).
3. **Variants:** V1 email +1h no promo, V2 email +4h 10% promo, V3 SMS +2h 5% promo (V3 falls back to V2 without a phone). Step 2 follows 48h after step 1 for ~30% of targeted carts. SMS quiet hours 21:00-08:00 defer to 08:00.
4. **Send decision order (each scheduled message becomes exactly one `send_attempts` row):** consent for the channel *at send time* (`consents` timeline) -> cart already purchased -> frequency cap (max 1 sent / 24h and 3 / 7d per customer across channels). Suppressed attempts keep their reason and the evidence (`consent_id`, `sends_last_24h/7d`). Unsubscribe / STOP events append a new opt-out consent row.
5. **Outcomes:** delivery/open/click/unsubscribe events are drawn from channel-specific rates; a click converts with propensity = channel base (30% email / 38% SMS) + 1.2pt per promo % scaled by cart value; organic returns are drawn from cart intent (checkout reached or not). The earliest purchase wins. Promo is valid 7 days after the click.
6. **Attribution:** deterministic *last click within 7 days* before the order for the same cart; at most one attribution per order. Orders after the window are `late_purchase_outside_window`.
7. **Derived values** (`item_count`, `cart_total`, `line_total`, order totals, `lag_hours`, `effective_to`, cart status) are computed from source records.

## Labelled edge cases (injected after valid baseline; listed in `ground_truth/ground_truth.csv`)
`message_sent_after_optout`, `cart_abandoned_after_purchase`, `attribution_double_counted_across_campaigns`,
`cart_total_stale_after_quantity_update`, plus naturally generated `boundary_abandonment_window` cases, consent withdrawal,
multi-device carts, recovered carts, late purchases and frequency-cap conflicts.
`ground_truth/expected_labels.csv` holds the rule-derived expected decisions (abandoned?, status, attribution, true driver).

## Notes / assumptions
* "10,000 campaigns/sends" is interpreted as 10,000 scheduled messages/send attempts; campaigns are weekly variant waves.
* IDs use year 2026 for the whole dataset; MSG ids embed the cart id (`MSG-CART-2026-000001-01`).
* Timestamps are naive local time; data cut-off is 2026-11-15 (later orders are censored).
