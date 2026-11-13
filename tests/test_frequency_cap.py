"""
Tests for customer communication frequency cap enforcement.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from cart_recover.models.orm_models import SendAttempt

FMT = "%Y-%m-%dT%H:%M:%S"

def test_frequency_cap_enforcement_clean(db_session):
    """
    Verify that uncorrupted sent messages never violate:
    - Max 1 message per customer in rolling 24 hours
    - Max 3 messages per customer in rolling 7 days
    """
    sends = db_session.query(SendAttempt).filter(SendAttempt.status == "sent").all()
    by_cust = defaultdict(list)
    for s in sends:
        by_cust[s.customer_id].append(datetime.strptime(s.attempt_ts, FMT))

    for cust_id, timestamps in by_cust.items():
        timestamps.sort()
        for i in range(len(timestamps)):
            if i >= 1:
                diff_24h = timestamps[i] - timestamps[i - 1]
                assert diff_24h >= timedelta(hours=24), f"Customer {cust_id} received >1 send in 24h: {diff_24h}"
            if i >= 3:
                diff_7d = timestamps[i] - timestamps[i - 3]
                assert diff_7d >= timedelta(days=7), f"Customer {cust_id} received >3 sends in 7d: {diff_7d}"
