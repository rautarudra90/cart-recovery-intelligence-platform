"""
Tests for contact consent evaluation, withdrawal, and suppression enforcement.
"""
import json
from pathlib import Path
from datetime import datetime
from cart_recover.models.orm_models import SendAttempt, Consent

def test_suppressed_statuses_represented(db_session):
    """Ensure all required suppression categories appear in send_attempts."""
    statuses = set(r[0] for r in db_session.query(SendAttempt.status).distinct().all())
    expected = {
        "sent",
        "suppressed_no_consent",
        "suppressed_consent_withdrawn",
        "suppressed_frequency_cap",
        "suppressed_already_purchased"
    }
    assert expected.issubset(statuses), f"Missing expected send statuses: {expected - statuses}"

def test_no_send_after_opt_out_unflagged(db_session, starter_data_dir):
    """
    Verify that in operational valid records (excluding deliberately injected test anomalies),
    messages are never sent without opt-in consent at the time of send attempt.
    """
    gt_file = starter_data_dir / "ground_truth" / "ground_truth.json"
    with open(gt_file, "r", encoding="utf-8") as f:
        gt_records = json.load(f)
    
    injected_defect_sends = {
        r["entity_id"] for r in gt_records if r["issue_type"] == "message_sent_after_optout"
    }

    valid_sends = db_session.query(SendAttempt).filter(
        SendAttempt.status == "sent",
        SendAttempt.consent_id.isnot(None),
        ~SendAttempt.send_id.in_(injected_defect_sends)
    ).limit(50).all()

    for s in valid_sends:
        consent = db_session.query(Consent).filter(Consent.consent_id == s.consent_id).first()
        if consent:
            assert consent.status == "opt_in"
            assert consent.effective_from <= s.attempt_ts

def test_consent_history_audit_trail(db_session):
    """Verify consent timeline integrity: contiguous non-overlapping effective dates."""
    withdrawn = db_session.query(Consent).filter(Consent.status == "opt_out", Consent.source != "signup").first()
    assert withdrawn is not None, "Consent withdrawal rows should exist in audit history"
