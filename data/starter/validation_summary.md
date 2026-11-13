# Validation summary

144 checks: 137 PASS, 7 FLAGGED (flagged = findings explained by labelled anomalies)

## Acceptance

* consent_and_suppression_enforced: **True**
* abandonment_time_based: **True**
* attribution_deterministic: **True**
* metrics_reconcile: **True**
* all_unflagged_checks_clean: **True**
* all_injected_anomalies_detected_exactly: **True**

## Injected anomaly detection

* message_sent_after_optout: {"injected": 3, "detected": 3, "exact_match": true}
* cart_abandoned_after_purchase: {"injected": 3, "detected": 3, "exact_match": true}
* cart_total_stale_after_quantity_update: {"injected": 3, "detected": 3, "exact_match": true}
* attribution_double_counted_across_campaigns: {"injected": 1, "detected": 1, "exact_match": true}
* boundary_abandonment_window: {"cases": 7, "rule_agrees": true}

## Metrics

```
{
 "sends": 280,
 "suppressed": 120,
 "delivered": 270,
 "clicked": 35,
 "attributed_orders_dedup": 17,
 "attributed_revenue_dedup": 3426.55,
 "attributed_revenue_naive": 3508.59,
 "orders": 1358,
 "abandoned_carts": 803,
 "recovered_carts": 158,
 "send_status": {
  "sent": 280,
  "suppressed_no_consent": 75,
  "suppressed_already_purchased": 23,
  "suppressed_consent_withdrawn": 16,
  "suppressed_frequency_cap": 6
 }
}
```

## Flagged checks

* arith:cart_total=sum(lines): 3 violation(s) stale totals
* lifecycle:abandoned_flag_after_purchase: 3 violation(s) carts flagged abandoned but ordered inside window
* lifecycle:cart_status_matches_rule: 3 violation(s) 
* consent:no_send_without_opt_in: 3 violation(s) messages sent to a channel in opt_out state
* attribution:one_per_order: 1 violation(s) orders credited more than once
* attribution:backed_by_click_event: 1 violation(s) 
* reconcile:naive_vs_dedup_attributed_revenue: 1 violation(s) naive credited revenue exceeds de-duplicated
