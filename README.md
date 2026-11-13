# CartRecover-AI | Enterprise Cart Recovery & Attribution Platform

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![SQLAlchemy 2.0](https://img.shields.io/badge/ORM-SQLAlchemy%202.0-red.svg)](https://www.sqlalchemy.org/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![Validation](https://img.shields.io/badge/Validation-100%25%20PASS-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Associate AI Forward Deployed Engineer Assessment Submission**  
> An enterprise-grade, local-first platform designed to identify abandoned shopping carts, enforce strict real-time contact consent and frequency limits, coordinate personalized multi-variant recovery campaigns across Email and SMS, and calculate deterministic conversion attribution with anomaly auditing.

---

## 1. Executive Summary & Problem Statement

E-commerce businesses lose significant revenue to cart abandonment. However, naive recovery campaigns face major operational risks:
1. **Regulatory & Consent Violations**: Dispatching messages after customer opt-out or during TCPA quiet hours breaches legal frameworks.
2. **Customer Fatigue**: Multiple concurrent recovery messages erode user trust and spike unsubscribe rates.
3. **Flawed Attribution**: Campaign collisions cause orders to be double-counted across channels, distorting marketing ROI.
4. **Data Desynchronization**: Stale cart totals and post-purchase messaging trigger customer complaints and support overhead.

**CartRecover-AI** delivers an end-to-end, reproducible, relational solution with complete event traceability, point-in-time policy enforcement, mathematical metric reconciliation, and an interactive executive dashboard.

---

## 2. Platform Architecture & Data Flow

```
+---------------------------------------------------------------------------------------+
|                                    PRIMARY ACTORS                                     |
|  [Customer]               [Merchandising Analyst]    [Store Operator]   [Ops Manager] |
+-------+-----------------------------+-----------------------+-----------------+-------+
        |                             |                       |                 |
        v                             v                       v                 v
+---------------------------------------------------------------------------------------+
|                               CartRecover-AI PLATFORM                                 |
|                                                                                       |
|   +---------------------+   +-----------------------+   +-------------------------+   |
|   | Abandonment Engine  |-->| Consent & Suppression |-->| Campaign Personalization|   |
|   | 60-min Inactivity   |   | Point-in-Time Timeline|   | Variant Rules (V1,V2,V3)|   |
|   +---------------------+   +-----------------------+   +-------------------------+   |
|              |                          |                            |                |
|              v                          v                            v                |
|   +---------------------+   +-----------------------+   +-------------------------+   |
|   | Delivery Simulation |-->| Conversion Engine     |-->| Deterministic 7-Day     |   |
|   | Open/Click/Bounces  |   | Multi-Device Returns  |   | Conversion Attribution  |   |
|   +---------------------+   +-----------------------+   +-------------------------+   |
+---------------------------------------------------------------------------------------+
        |                                                              |
        v                                                              v
+-------------------------------+                             +-------------------------+
| Relational Persistence        |                             | Visual Analytics        |
| - SQLite Embedded Database    |                             | - Streamlit Dashboard   |
| - SQLAlchemy 2.0 ORM          |                             | - Acceptance Validator  |
| - 17 Relational Tables        |                             | - Reproducibility Audit |
+-------------------------------+                             +-------------------------+
```

---

## 3. Core Entities & Relational Schema

The relational data model enforces referential integrity across 10 core entities and 7 audit/bridge tables:

| Entity | Primary Key | Foreign Keys | Cardinality | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **`customers`** | `customer_id` | *None* | `1:N` Carts, Consents, Sessions, Orders | Master shopper demographics & regional data. |
| **`consents`** | `consent_id` | `customer_id` | `N:1` Customer | Contiguous point-in-time opt-in/opt-out audit trail. |
| **`products`** | `sku` | *None* | `1:N` CartLines | Catalog SKU pricing and category master. |
| **`sessions`** | `session_id` | `customer_id` | `N:1` Customer, `N:M` Carts | Browsing sessions with device metadata. |
| **`carts`** | `cart_id` | `customer_id` | `1:N` CartLines, `1:N` Events, `1:1` Order | Current cart state, totals, and abandonment status. |
| **`cart_sessions`**| `(cart_id, session_id)` | `cart_id`, `session_id` | `N:M` Bridge | Multi-device cart resumption tracking. |
| **`cart_lines`** | `cart_line_id` | `cart_id`, `sku` | `N:1` Cart, `N:1` Product | Line items, quantities, and line totals. |
| **`cart_events`** | `cart_event_id` | `cart_id`, `session_id` | `N:1` Cart | Immutable append-only cart lifecycle events. |
| **`abandonment_decisions`** | `decision_id` | `cart_id` | `1:1` Cart | Audit log of targeting eligibility (budget/holdout). |
| **`campaigns`** | `campaign_id` | *None* | `1:N` Messages, `N:M` Templates | Weekly recovery campaign waves. |
| **`message_templates`** | `template_id` | *None* | `N:M` Campaigns | Copy, discount rates, and step sequencing. |
| **`campaign_templates`**| `(campaign_id, template_id)` | `campaign_id`, `template_id` | `N:M` Bridge | Campaign to template associations. |
| **`scheduled_messages`** | `message_id` | `cart_id`, `customer_id`, `campaign_id`, `template_id` | `1:1` SendAttempt | Planned communications prior to dispatch. |
| **`send_attempts`**| `send_id` | `message_id`, `customer_id`, `consent_id` | `1:N` Events, `1:N` Attributions | Dispatch decision (sent/suppressed) with evidence. |
| **`send_events`** | `event_id` | `send_id` | `N:1` SendAttempt | Downstream delivery, open, click, unsubscribe events. |
| **`orders`** | `order_id` | `customer_id`, `cart_id`, `session_id` | `1:1` Cart, `1:N` Attributions | Completed purchases with totals and discounts. |
| **`attributions`** | `attribution_id` | `order_id`, `send_id`, `campaign_id` | `N:1` Order, `N:1` SendAttempt | Deterministic 7-day last-click conversion attribution. |

---

## 4. Key Business Rules & Decision Logic

1. **Time-Based Abandonment**:
   - Threshold: **60 minutes** of inactivity after `last_activity_at`.
   - Inclusive Boundary: Orders placed at $t_{\text{order}} \le t_{\text{last\_act}} + 60\text{m}$ are **not abandoned** (direct purchase). Orders placed at $> +60\text{m}$ or unplaced are flagged `abandoned`.
2. **Point-in-Time Consent Evaluation**:
   - Consent is evaluated at the exact dispatch timestamp against the contiguous `consents` timeline.
   - Suppressed reasons: `suppressed_no_consent`, `suppressed_consent_withdrawn`, `suppressed_already_purchased`.
3. **Rolling Frequency Capping**:
   - Maximum **1 message per rolling 24 hours** across all channels.
   - Maximum **3 messages per rolling 7 days** across all channels.
4. **TCPA Quiet Hours Deferral**:
   - SMS messages scheduled between **21:00 and 08:00** are deferred to **08:00 AM** the following day.
5. **Campaign Personalization**:
   - **`V1`**: Email +1 hour delay, 0% promo (Standard Reminder).
   - **`V2`**: Email +4 hours delay, 10% promo (`RECOVER10`).
   - **`V3`**: SMS +2 hours delay, 5% promo (`RECOVER5`) (falls back to V2 if no phone).
6. **Deterministic 7-Day Last-Click Attribution**:
   - Attribution Window: Exactly **168 hours (7 days)** from click to purchase.
   - Orders placed after 7 days are classified as `late_purchase_outside_window`.

---

## 5. Labelled Anomaly Scenarios & Ground Truth Isolation

Four controlled edge cases are injected into the dataset to validate monitoring and audit capabilities without polluting operational features:
- **`message_sent_after_optout`**: Message marked `sent` despite prior opt-out consent.
- **`cart_abandoned_after_purchase`**: Cart flagged abandoned after an order was already completed.
- **`attribution_double_counted_across_campaigns`**: An order credited to two competing campaigns simultaneously.
- **`cart_total_stale_after_quantity_update`**: Cart lines updated without recalculating the cart header total.

> **Ground Truth Isolation**: All anomalies and expected labels are stored exclusively in `data/<scale>/ground_truth/ground_truth.json` and `expected_labels.csv`. They are never leaked into model input features or operational database tables.

---

## 6. Generated Record Counts & Scale Validation

The generator uses deterministic random seed `20261022`. Both starter and full scale configurations use identical business logic:

| Table | Starter Dataset | Full Dataset (Assessment Target) |
| :--- | :--- | :--- |
| **`customers`** | 800 | 20,000 |
| **`consents`** | 1,466 | 36,446 |
| **`products`** | 80 | 80 |
| **`sessions`** | 2,424 | 60,772 |
| **`carts`** | **2,000** | **50,000** |
| **`abandoned_carts`** | **803** | **20,060** |
| **`cart_lines`** | 4,195 | 104,749 |
| **`cart_events`** | 10,367 | 259,584 |
| **`campaigns`** | 109 | 119 |
| **`send_attempts`** | **400** | **10,000** |
| **`orders`** | 1,358 | 34,084 |
| **`attributions`** | 18 | 411 |

---

## 7. Documented Mathematical KPI Formulas

All analytical metrics are computed directly from relational records:

$$\text{Cart Abandonment Rate} = \frac{\text{Count}(\text{carts where } abandoned\_at \text{ IS NOT NULL})}{\text{Total Carts}} \times 100$$

$$\text{Cart Recovery Rate} = \frac{\text{Count}(\text{carts where } status = \text{'recovered'})}{\text{Count}(\text{carts where } abandoned\_at \text{ IS NOT NULL})} \times 100$$

$$\text{Suppression Rate} = \frac{\text{Count}(\text{send\_attempts where } status \neq \text{'sent'})}{\text{Total Send Attempts}} \times 100$$

$$\text{Revenue Per Send (RPS)} = \frac{\sum \text{Attributed Revenue (Deduplicated)}}{\text{Count}(\text{messages sent})}$$

$$\text{Double-Count Bias} = \sum \text{Naive Attributed Revenue} - \sum \text{Deduplicated Attributed Revenue}$$

---

## 8. Quick Start Guide (Windows PowerShell)

### 8.1 Setup & Installation
```powershell
# Clone the repository
git clone https://github.com/<your-username>/CartRecover-AI.git
cd CartRecover-AI

# Install required dependencies
pip install -r requirements.txt
```

### 8.2 End-to-End Automated Pipeline
Run the end-to-end pipeline (generation, SQLite relational loading, acceptance validation, reproducibility audit):
```powershell
python scripts/run_pipeline.py --scale starter
```
To run the full assessment dataset (50k carts, 20k abandoned, 10k sends):
```powershell
python scripts/run_pipeline.py --scale full
```

### 8.3 Launch Interactive Streamlit Dashboard
```powershell
streamlit run app.py
```
The dashboard will open automatically in your browser at `http://localhost:8501`.

### 8.4 Run Test Suite
Execute the comprehensive Pytest suite:
```powershell
pytest tests -v
```

---

## 9. Verification & Acceptance Results

### Acceptance Scorecard
```
* consent_and_suppression_enforced: True
* abandonment_time_based: True
* attribution_deterministic: True
* metrics_reconcile: True
* all_unflagged_checks_clean: True
* all_injected_anomalies_detected_exactly: True
```

### Anomaly Detection Scorecard
- `message_sent_after_optout`: **100% exact match**
- `cart_abandoned_after_purchase`: **100% exact match**
- `cart_total_stale_after_quantity_update`: **100% exact match**
- `attribution_double_counted_across_campaigns`: **100% exact match**
- `boundary_abandonment_window`: **100% rule agreement**

### Reproducibility Verification
```powershell
python repro_check.py --out data/starter --scale starter
# Output: identical: True | files compared: 26 | differing: []
```

---

## 10. Direct GitHub Submission Instructions

Execute the following PowerShell commands to push your project directly to GitHub:

```powershell
# Initialize git repository if not already initialized
git init

# Verify no unwanted files (venv, logs, db journals) are tracked
git status

# Add all project source files, tests, and documentation
git add .

# Create initial commit
git commit -m "feat: complete CartRecover-AI FDE challenge with full relational pipeline and dashboard"

# Rename default branch to main
git branch -M main

# Add your remote GitHub repository
git remote add origin https://github.com/<your-username>/CartRecover-AI.git

# Push to GitHub
git push -u origin main
```

---

## 11. Project Directory Structure

```
CartRecover-AI/
├── .gitignore                      # Git exclusion rules (no venvs, no temporary db journals)
├── README.md                       # Complete executive & technical documentation
├── requirements.txt                # Production Python dependencies
├── pytest.ini                      # Pytest runner configuration
├── app.py                          # Streamlit application entrypoint
├── generate_data.py                # Deterministic synthetic data generator (seed: 20261022)
├── validate_data.py                # 144-rule strict data and acceptance validator
├── repro_check.py                  # SHA-256 reproducibility comparator
├── schema.py                       # Canonical schema definitions and data dictionary
├── cart_recover/
│   ├── __init__.py
│   ├── analytics/
│   │   ├── __init__.py
│   │   └── metrics.py              # Documented mathematical KPI formulas
│   ├── app/
│   │   ├── __init__.py
│   │   └── dashboard.py            # Multi-tab Streamlit intelligence console
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py           # SQLite connection & high-throughput loader
│   │   └── repository.py           # Relational analytics queries
│   └── models/
│       ├── __init__.py
│       ├── enums.py                # Enums for statuses, channels, categories
│       └── orm_models.py           # SQLAlchemy 2.0 ORM Declarative Models
├── config/
│   ├── __init__.py
│   └── settings.py                 # Global configurations, seeds, and scale presets
├── docs/
│   ├── architecture.md             # System architecture & sequence diagrams
│   ├── business_rules.md           # Business logic, quiet hours, caps, variants
│   ├── data_dictionary.md          # Data dictionary for all 10 entities
│   ├── reproducibility_report.md   # Reproducibility audit logs
│   └── schema.md                   # Relational ER schema and constraints
├── scripts/
│   ├── run_generator.py            # CLI generator wrapper
│   ├── run_pipeline.py             # Automated end-to-end pipeline runner
│   ├── run_reproducibility.py      # Reproducibility test CLI
│   └── run_validation.py           # Data acceptance validation CLI
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures and DB sessions
│   ├── test_abandonment.py         # Time-based boundary tests (+60m)
│   ├── test_anomalies.py           # Injected anomaly detection tests
│   ├── test_attribution.py         # 7-day last-click attribution tests
│   ├── test_consent_suppression.py # Point-in-time consent & suppression tests
│   ├── test_database.py            # Relational persistence & ORM tests
│   ├── test_frequency_cap.py       # Rolling 24h & 7d frequency cap tests
│   ├── test_metrics.py             # Metric formula calculation tests
│   └── test_schema.py              # Table, PK, FK, and constraint tests
└── data/
    ├── starter/                    # Starter dataset (2k carts, 800 abandoned)
    └── full/                       # Full dataset (50k carts, 20k abandoned, 10k sends)
```
