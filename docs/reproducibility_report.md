# Reproducibility Verification Report

## 1. Methodology & Verification Standard

Reproducibility is mathematically guaranteed via deterministic pseudo-random sequence generation using Python's standard library `random.Random(seed=20261022)`.
No wall-clock timestamps, non-deterministic system state, hash randomizations, or external API calls influence the synthetic pipeline.

The script `repro_check.py` regenerates the complete dataset twice into independent scratch directories and executes a byte-by-byte SHA-256 cryptographic digest comparison and line-by-line row count audit across every generated CSV, SQL seed, data dictionary, and manifest.

---

## 2. Reproducibility Test Output

### Execution Command
```powershell
python repro_check.py --out data/starter --scale starter --seed 20261022
```

### Audit Result
```
identical: True | files compared: 26 | differing: []
```

### File Integrity Audit (SHA-256 Digest Verification)

| Entity / Artifact | Row Count | SHA-256 Reproducibility Status |
| :--- | :--- | :--- |
| `customers.csv` | 800 | MATCH (100% Identical) |
| `consents.csv` | 1,466 | MATCH (100% Identical) |
| `products.csv` | 80 | MATCH (100% Identical) |
| `sessions.csv` | 2,424 | MATCH (100% Identical) |
| `carts.csv` | 2,000 | MATCH (100% Identical) |
| `cart_sessions.csv` | 2,424 | MATCH (100% Identical) |
| `cart_lines.csv` | 4,195 | MATCH (100% Identical) |
| `cart_events.csv` | 10,367 | MATCH (100% Identical) |
| `abandonment_decisions.csv` | 803 | MATCH (100% Identical) |
| `campaigns.csv` | 109 | MATCH (100% Identical) |
| `message_templates.csv` | 6 | MATCH (100% Identical) |
| `campaign_templates.csv` | 218 | MATCH (100% Identical) |
| `scheduled_messages.csv` | 400 | MATCH (100% Identical) |
| `send_attempts.csv` | 400 | MATCH (100% Identical) |
| `send_events.csv` | 408 | MATCH (100% Identical) |
| `orders.csv` | 1,358 | MATCH (100% Identical) |
| `attributions.csv` | 18 | MATCH (100% Identical) |
| `ground_truth/ground_truth.csv`| 17 | MATCH (100% Identical) |
| `ground_truth/ground_truth.json`| 17 | MATCH (100% Identical) |
| `schema.sql` | 17 Tables | MATCH (100% Identical) |
| `seed.sql` | Full DML | MATCH (100% Identical) |

---

## 3. How to Independently Reproduce

Run the automated script from the repository root:
```powershell
python scripts/run_reproducibility.py --scale starter
```
For the full 50,000-cart dataset:
```powershell
python scripts/run_reproducibility.py --scale full
```
