"""
Tests for the 4 mandatory injected anomaly scenarios and ground truth isolation.
"""
import json
import csv
from pathlib import Path

def test_ground_truth_file_isolation(starter_data_dir):
    """
    Verify ground truth files exist strictly in ground_truth/ subfolder
    and operational CSV files do not contain anomaly labels.
    """
    gt_csv = starter_data_dir / "ground_truth" / "ground_truth.csv"
    gt_json = starter_data_dir / "ground_truth" / "ground_truth.json"

    assert gt_csv.exists(), "ground_truth.csv missing"
    assert gt_json.exists(), "ground_truth.json missing"

    # Verify operational table headers have no ground truth / defect columns
    carts_csv = starter_data_dir / "carts.csv"
    with open(carts_csv, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert "issue_type" not in header
        assert "defect" not in header
        assert "is_anomaly" not in header

def test_all_four_mandatory_anomalies_present(starter_data_dir):
    """Verify all four required anomaly scenarios are present in ground truth."""
    gt_json = starter_data_dir / "ground_truth" / "ground_truth.json"
    with open(gt_json, "r", encoding="utf-8") as f:
        records = json.load(f)

    issue_types = set(r["issue_type"] for r in records)
    required_anomalies = {
        "message_sent_after_optout",
        "cart_abandoned_after_purchase",
        "attribution_double_counted_across_campaigns",
        "cart_total_stale_after_quantity_update"
    }
    assert required_anomalies.issubset(issue_types), f"Missing anomalies: {required_anomalies - issue_types}"

def test_validation_detects_100_percent_of_injected_anomalies(starter_data_dir):
    """Verify validate_data.py summary reports 100% exact match detection."""
    summary_file = starter_data_dir / "validation_summary.json"
    assert summary_file.exists(), "validation_summary.json missing"
    with open(summary_file, "r", encoding="utf-8") as f:
        summary = json.load(f)

    anom_results = summary["injected_anomaly_detection"]
    for anom_name in [
        "message_sent_after_optout",
        "cart_abandoned_after_purchase",
        "attribution_double_counted_across_campaigns",
        "cart_total_stale_after_quantity_update"
    ]:
        res = anom_results[anom_name]
        assert res["exact_match"] is True, f"Anomaly {anom_name} was not detected with exact match"
        assert res["injected"] == res["detected"]
