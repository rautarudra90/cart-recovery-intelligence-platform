# Business Rules & Decision Logic

## 1. Time-Based Cart Abandonment Rule

### 1.1 Inactivity Window Definition
- A cart is evaluated for abandonment strictly based on the time elapsed since `last_activity_at`.
- The inactivity abandonment threshold is exactly **60 minutes** ($\Delta t = 60\text{ minutes}$).
- **Boundary Condition (Inclusive)**:
  - If an order is placed at or before `last_activity_at + 60 min` ($t_{\text{order}} \le t_{\text{last\_act}} + 60\text{m}$), the cart is **NOT abandoned**; its lifecycle state is `purchased`.
  - If no order exists at $t_{\text{last\_act}} + 60\text{m}$, or an order is placed after that point ($t_{\text{order}} > t_{\text{last\_act}} + 60\text{m}$), the cart is flagged as **abandoned**.
  - `abandoned_at = last_activity_at + 60 min`.
  - An immutable event row with `event_type = 'abandoned_flagged'` is appended to `cart_events`.
  - An explicit `abandonment_decisions` record is written documenting eligibility and targeting.

---

## 2. Contact Consent & Policy Verification

### 2.1 Point-in-Time Evaluation
- Consent is NEVER evaluated statically; it is evaluated at the exact dispatch timestamp (`attempt_ts`).
- The system queries the `consents` timeline for the specific `(customer_id, channel)` where:
  $$effective\_from \le attempt\_ts < effective\_to$$
  (where `effective_to IS NULL` represents the currently active state).

### 2.2 Suppression Logic
A scheduled recovery message is suppressed if any of the following conditions hold:
1. **No Active Consent (`suppressed_no_consent`)**: No prior opt-in record exists for the customer on that channel.
2. **Consent Withdrawn (`suppressed_consent_withdrawn`)**: The customer previously opted in but has since opted out prior to `attempt_ts`.
3. **Cart Already Purchased (`suppressed_already_purchased`)**: An order was placed for this cart prior to or at `attempt_ts`.
4. **Frequency Cap Conflict (`suppressed_frequency_cap`)**: The dispatch would violate rolling frequency limits.

---

## 3. Communication Frequency Capping

To protect brand reputation and customer satisfaction, frequency limits are enforced across all marketing channels:
1. **Rolling 24-Hour Cap**: Maximum **1 message** per customer across all channels in any rolling 24-hour window:
   $$\text{Sends in }[attempt\_ts - 24\text{h}, attempt\_ts] < 1$$
2. **Rolling 7-Day Cap**: Maximum **3 messages** per customer across all channels in any rolling 7-day window:
   $$\text{Sends in }[attempt\_ts - 7\text{d}, attempt\_ts] < 3$$
- If either cap is breached, the message status is set to `suppressed_frequency_cap`, and the counters `sends_last_24h` and `sends_last_7d` are preserved as audit evidence.

---

## 4. SMS Quiet Hours Policy

- To comply with TCPA regulations, SMS messages are prohibited from dispatch during quiet night hours: **21:00 to 08:00 local time**.
- Any SMS message planned between 21:00 and 07:59 is automatically deferred to **08:00:00 (plus jitter up to 30 minutes)** on the next qualifying morning.

---

## 5. Campaign Personalization & Variant Strategy

| Variant Code | Channel | Delay After Abandonment | Discount Incentive | Target Segment / Fallback |
| :--- | :--- | :--- | :--- | :--- |
| **`V1`** | `email` | 60 minutes (+1 hour) | 0% (Standard Reminder) | All segments |
| **`V2`** | `email` | 240 minutes (+4 hours) | 10% Promo (`RECOVER10`) | High-value / Price-sensitive |
| **`V3`** | `sms` | 120 minutes (+2 hours) | 5% Promo (`RECOVER5`) | Mobile shoppers with valid phone. *Falls back to V2 if customer has no phone.* |

---

## 6. Deterministic 7-Day Last-Click Attribution

- **Window**: Exactly **168 hours** (7 days) measured from the customer's click event:
  $$click\_ts \le order\_ts \le click\_ts + 168\text{ hours}$$
- **Model**: Deterministic Last-Click. When multiple qualifying clicks precede an order, the most recent click prior to purchase is awarded 100% of attribution credit.
- **Single Primary Rule**: Exactly one primary attribution per order in valid operation. Orders occurring outside the window are classified as `late_purchase_outside_window`.

---

## 7. Labelled Anomaly Scenarios & Ground Truth Isolation

Four controlled defect scenarios are injected into the dataset to validate auditing and monitoring capabilities.
All injected instances are recorded in `data/<scale>/ground_truth/ground_truth.json` and are NEVER leaked into operational features:

1. **`message_sent_after_optout`**: Message marked `sent` despite the customer having an active `opt_out` state in `consents`.
2. **`cart_abandoned_after_purchase`**: Cart flagged `abandoned` and marked `abandoned_flagged` despite an order having been placed within 60 minutes.
3. **`attribution_double_counted_across_campaigns`**: An order is attributed to two competing campaigns simultaneously, duplicating reported revenue.
4. **`cart_total_stale_after_quantity_update`**: Cart lines reflect updated item quantities, but cart `cart_total` reflects the pre-update sum.
