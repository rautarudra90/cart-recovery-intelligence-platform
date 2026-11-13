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

* message_sent_after_optout: {"injected": 44, "detected": 44, "exact_match": true}
* cart_abandoned_after_purchase: {"injected": 60, "detected": 60, "exact_match": true}
* cart_total_stale_after_quantity_update: {"injected": 75, "detected": 75, "exact_match": true}
* attribution_double_counted_across_campaigns: {"injected": 8, "detected": 8, "exact_match": true}
* boundary_abandonment_window: {"cases": 329, "rule_agrees": true}

## Metrics

```
{
 "sends": 7172,
 "suppressed": 2828,
 "delivered": 6982,
 "clicked": 890,
 "attributed_orders_dedup": 403,
 "attributed_revenue_dedup": 63208.5,
 "attributed_revenue_naive": 63960.2,
 "orders": 34084,
 "abandoned_carts": 20060,
 "recovered_carts": 4084,
 "send_status": {
  "sent": 7172,
  "suppressed_consent_withdrawn": 368,
  "suppressed_no_consent": 1874,
  "suppressed_frequency_cap": 80,
  "suppressed_already_purchased": 506
 }
}
```

## Flagged checks

* arith:cart_total=sum(lines): 75 violation(s) stale totals
* lifecycle:abandoned_flag_after_purchase: 60 violation(s) carts flagged abandoned but ordered inside window
* lifecycle:cart_status_matches_rule: 60 violation(s) 
* consent:no_send_without_opt_in: 44 violation(s) messages sent to a channel in opt_out state
* attribution:one_per_order: 8 violation(s) orders credited more than once
* attribution:backed_by_click_event: 8 violation(s) 
* reconcile:naive_vs_dedup_attributed_revenue: 1 violation(s) naive credited revenue exceeds de-duplicated
