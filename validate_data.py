#!/usr/bin/env python3
"""Validate a generated dataset from its CSVs only (ground truth is read last, solely to score detection).

    python validate_data.py --data data/full
Writes validation_summary.json / .md and reports/campaign_performance.csv inside the data dir.
"""
import argparse
import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from schema import TABLES, TABLE_ORDER

FMT = "%Y-%m-%dT%H:%M:%S"
P = lambda s: datetime.strptime(s, FMT)
C = lambda s: int(round(float(s) * 100))


def load(d, t):
    with open(os.path.join(d, t + ".csv"), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/full")
    d = ap.parse_args().data
    D = {t: load(d, t) for t in TABLE_ORDER}
    checks = []

    def chk(name, bad, total=None, note="", expected_bad=None):
        checks.append(dict(check=name, violations=len(bad), checked=total, note=note,
                           sample=list(bad)[:3], status="PASS" if not bad else "FLAGGED", _bad=set(bad)))

    # ---- 1. structure: PK uniqueness / id pattern / required / enums / types
    for t in TABLE_ORDER:
        spec, rows = TABLES[t], D[t]
        keys = [tuple(r[k] for k in spec["pk"]) for r in rows]
        dup = [k for k, n in Counter(keys).items() if n > 1]
        chk("pk_unique:" + t, dup, len(rows))
        if spec["id_regex"]:
            rx = re.compile("^" + spec["id_regex"] + "$")
            chk("id_pattern:" + t, [k[0] for k in keys if not rx.match(k[0])], len(rows))
        miss = [k for r, k in zip(rows, keys) for f in spec["fields"] if f["required"] and r[f["name"]] == ""]
        chk("required_not_null:" + t, miss, len(rows))
        bad = []
        for f in spec["fields"]:
            if isinstance(f["allowed"], list):
                al = set(map(str, f["allowed"]))
                bad += ["%s.%s=%s" % (t, f["name"], r[f["name"]]) for r in rows if r[f["name"]] != "" and r[f["name"]] not in al]
            if f["type"] == "timestamp":
                for r in rows:
                    if r[f["name"]]:
                        try:
                            P(r[f["name"]])
                        except ValueError:
                            bad.append("%s.%s bad ts" % (t, f["name"]))
            if f["unique"] and not (len(spec["pk"]) == 1 and f["name"] == spec["pk"][0]):
                vals = [r[f["name"]] for r in rows if r[f["name"]] != ""]
                bad += ["%s.%s dup" % (t, f["name"]) for v, n in Counter(vals).items() if n > 1]
        chk("enums_types_uniques:" + t, bad, len(rows))

    # ---- 2. FK integrity
    pk_sets = {t: set(tuple(r[k] for k in TABLES[t]["pk"]) if len(TABLES[t]["pk"]) > 1 else r[TABLES[t]["pk"][0]] for r in D[t]) for t in TABLE_ORDER}
    for t in TABLE_ORDER:
        for col, rt, rc in TABLES[t]["fks"]:
            bad = [r[col] for r in D[t] if r[col] != "" and r[col] not in pk_sets[rt]]
            chk("fk:%s.%s->%s" % (t, col, rt), bad, len(D[t]))

    # ---- indexes
    cust = {r["customer_id"]: r for r in D["customers"]}
    cart = {r["cart_id"]: r for r in D["carts"]}
    sess = {r["session_id"]: r for r in D["sessions"]}
    lines = defaultdict(list)
    for r in D["cart_lines"]:
        lines[r["cart_id"]].append(r)
    cev = defaultdict(list)
    for r in D["cart_events"]:
        cev[r["cart_id"]].append(r)
    order_by_cart = {r["cart_id"]: r for r in D["orders"]}
    msg = {r["message_id"]: r for r in D["scheduled_messages"]}
    send = {r["send_id"]: r for r in D["send_attempts"]}
    sev = defaultdict(list)
    for r in D["send_events"]:
        sev[r["send_id"]].append(r)
    prod = {r["sku"]: C(r["unit_price"]) for r in D["products"]}

    # ---- 3. date ordering
    bad = [r["session_id"] for r in D["sessions"] if P(r["ended_at"]) < P(r["started_at"])]
    chk("date:session_end>=start", bad, len(D["sessions"]))
    last_ev = defaultdict(lambda: datetime.min)
    for r in D["cart_events"]:
        if r["session_id"]:
            last_ev[r["session_id"]] = max(last_ev[r["session_id"]], P(r["event_ts"]))
    chk("date:session_end>=last_cart_event", [s for s, t in last_ev.items() if P(sess[s]["ended_at"]) < t], len(last_ev))
    chk("date:cart_created<=last_activity", [c["cart_id"] for c in D["carts"] if P(c["last_activity_at"]) < P(c["created_at"])], len(D["carts"]))
    chk("date:customer_created<=cart_created", [c["cart_id"] for c in D["carts"] if c["customer_id"] and P(cust[c["customer_id"]]["created_at"]) > P(c["created_at"])], len(D["carts"]))
    chk("date:order>cart_created", [o["order_id"] for o in D["orders"] if P(o["order_ts"]) <= P(cart[o["cart_id"]]["created_at"])], len(D["orders"]))
    chk("date:message>=abandoned_at", [m["message_id"] for m in D["scheduled_messages"] if P(m["scheduled_ts"]) < P(m["planned_ts"]) or P(m["planned_ts"]) < P(cart[m["cart_id"]]["abandoned_at"])], len(D["scheduled_messages"]))
    chk("date:attempt_ts==scheduled_ts", [s["send_id"] for s in D["send_attempts"] if s["attempt_ts"] != msg[s["message_id"]]["scheduled_ts"]], len(send))
    bad = [e["event_id"] for e in D["send_events"] if P(e["event_ts"]) < P(send[e["send_id"]]["attempt_ts"])]
    chk("date:send_event>=attempt", bad, len(D["send_events"]))
    bad = []
    for sid, es in sev.items():
        ts_ = {e["event_type"]: P(e["event_ts"]) for e in es}
        for k in ("opened", "clicked"):
            if k in ts_ and ("delivered" not in ts_ or ts_[k] < ts_["delivered"]):
                bad.append(sid)
    chk("date:open/click_after_delivery", bad, len(sev))
    chk("lifecycle:events_only_for_sent", [e["event_id"] for e in D["send_events"] if send[e["send_id"]]["status"] != "sent"], len(D["send_events"]))

    # ---- 4. arithmetic reconciliation
    chk("arith:line_total=qty*price", [l["cart_line_id"] for l in D["cart_lines"] if C(l["line_total"]) != int(l["quantity"]) * C(l["unit_price"])], len(D["cart_lines"]))
    chk("arith:line_price=catalogue", [l["cart_line_id"] for l in D["cart_lines"] if C(l["unit_price"]) != prod[l["sku"]]], len(D["cart_lines"]))
    chk("arith:item_count=sum(qty)", [c["cart_id"] for c in D["carts"] if int(c["item_count"]) != sum(int(l["quantity"]) for l in lines[c["cart_id"]])], len(cart))
    stale = [c["cart_id"] for c in D["carts"] if C(c["cart_total"]) != sum(C(l["line_total"]) for l in lines[c["cart_id"]])]
    chk("arith:cart_total=sum(lines)", stale, len(cart), "stale totals")
    chk("arith:order_subtotal=sum(lines)", [o["order_id"] for o in D["orders"] if C(o["subtotal"]) != sum(C(l["line_total"]) for l in lines[o["cart_id"]])], len(D["orders"]))
    chk("arith:order_total", [o["order_id"] for o in D["orders"] if C(o["order_total"]) != C(o["subtotal"]) - C(o["discount_amount"]) + C(o["shipping_fee"])], len(D["orders"]))
    chk("arith:shipping_rule", [o["order_id"] for o in D["orders"] if C(o["shipping_fee"]) != (599 if C(o["subtotal"]) < 7500 else 0)], len(D["orders"]))
    chk("arith:line_no_unique_per_cart", [c for c, ls in lines.items() if sorted(int(l["line_no"]) for l in ls) != list(range(1, len(ls) + 1))], len(lines))

    # ---- 5. lifecycle / abandonment (time based)
    W = timedelta(minutes=60)
    bad_ab, after_purchase, bad_status, bad_ev = [], [], [], []
    abandon_flag = {}
    for c in D["carts"]:
        cid, evs = c["cart_id"], cev[c["cart_id"]]
        types = [e["event_type"] for e in evs]
        o = order_by_cart.get(cid)
        la = P(c["last_activity_at"])
        exp_ab = o is None or P(o["order_ts"]) > la + W            # documented rule
        flagged = "abandoned_flagged" in types
        abandon_flag[cid] = flagged
        if flagged != exp_ab:
            after_purchase.append(cid) if (flagged and not exp_ab) else bad_ab.append(cid)
        if flagged and c["abandoned_at"] != (la + W).strftime(FMT):
            bad_ab.append(cid)
        exp_status = "abandoned" if o is None else "recovered" if exp_ab else "purchased"
        if c["status"] != exp_status:
            bad_status.append(cid)
        if types[0] != "cart_created" or types.count("purchased") != (1 if o else 0):
            bad_ev.append(cid)
        evt = [P(e["event_ts"]) for e in evs]
        if evt != sorted(evt):
            bad_ev.append(cid)
        if o and types.index("purchased") < (types.index("abandoned_flagged") if flagged else -1) and exp_ab:
            bad_ev.append(cid)
    chk("lifecycle:abandonment_is_time_based", bad_ab, len(cart))
    chk("lifecycle:abandoned_flag_after_purchase", after_purchase, len(cart), "carts flagged abandoned but ordered inside window")
    chk("lifecycle:cart_status_matches_rule", bad_status, len(cart))
    chk("lifecycle:cart_event_order", bad_ev, len(cart))
    dec = {r["cart_id"]: r for r in D["abandonment_decisions"]}
    chk("lifecycle:decision_row_iff_flagged", [c for c, f in abandon_flag.items() if f != (c in dec)], len(cart))
    chk("lifecycle:one_order_per_cart", [c for c, n in Counter(o["cart_id"] for o in D["orders"]).items() if n > 1], len(D["orders"]))
    chk("lifecycle:message_only_for_targeted_cart", [m["message_id"] for m in D["scheduled_messages"] if dec.get(m["cart_id"], {}).get("recovery_decision") != "targeted"], len(msg))
    chk("lifecycle:max_2_messages_per_cart", [c for c, n in Counter(m["cart_id"] for m in D["scheduled_messages"]).items() if n > 2], len(msg))
    chk("join:message_customer==cart_customer", [m["message_id"] for m in D["scheduled_messages"] if m["customer_id"] != cart[m["cart_id"]]["customer_id"]], len(msg))
    tpl = {t["template_id"]: t for t in D["message_templates"]}
    cmp_ = {c["campaign_id"]: c for c in D["campaigns"]}
    chk("join:message_template_step/channel", [m["message_id"] for m in D["scheduled_messages"] if tpl[m["template_id"]]["step"] != m["step"] or tpl[m["template_id"]]["channel"] != m["channel"] or cmp_[m["campaign_id"]]["channel"] != m["channel"]], len(msg))
    chk("join:message_id_format", [m["message_id"] for m in D["scheduled_messages"] if m["message_id"] != "MSG-%s-%02d" % (m["cart_id"], int(m["step"]))], len(msg))
    ct = {(r["campaign_id"], r["template_id"]) for r in D["campaign_templates"]}
    chk("join:campaign_template_bridge", [m["message_id"] for m in D["scheduled_messages"] if (m["campaign_id"], m["template_id"]) not in ct], len(msg))
    chk("join:order_session_in_cart_sessions", [o["order_id"] for o in D["orders"] if (o["cart_id"], o["session_id"]) not in pk_sets["cart_sessions"]], len(D["orders"]),
        "purchasing session must be a session of the cart")

    # ---- 6. consent timeline + enforcement
    tl = defaultdict(list)
    for r in D["consents"]:
        tl[(r["customer_id"], r["channel"])].append(r)
    bad_tl = []
    for k, rows in tl.items():
        rows.sort(key=lambda r: P(r["effective_from"]))
        for i, r in enumerate(rows):
            nxt = rows[i + 1]["effective_from"] if i + 1 < len(rows) else ""
            if r["effective_to"] != nxt or (nxt and P(nxt) <= P(r["effective_from"])):
                bad_tl.append(k[0] + "/" + k[1])
        if P(rows[0]["effective_from"]) < P(cust[k[0]]["created_at"]):
            bad_tl.append(k[0] + "/" + k[1])
    chk("consent:timeline_contiguous", bad_tl, len(tl))

    def consent_at(cid, ch, t):
        cur = None
        for r in tl.get((cid, ch), []):
            if P(r["effective_from"]) <= t:
                cur = r
        return cur
    viol, mism = [], []
    for s in D["send_attempts"]:
        if s["status"] != "sent":
            continue
        cur = consent_at(s["customer_id"], s["channel"], P(s["attempt_ts"]))
        if cur is None or cur["status"] != "opt_in":
            viol.append(s["send_id"])
        if cur is not None and s["consent_id"] != cur["consent_id"]:
            mism.append(s["send_id"])
    chk("consent:no_send_without_opt_in", viol, len(send), "messages sent to a channel in opt_out state")
    chk("consent:evidence_matches_timeline", mism, len(send))
    sup = []
    for s in D["send_attempts"]:
        if s["status"] in ("suppressed_no_consent", "suppressed_consent_withdrawn"):
            cur = consent_at(s["customer_id"], s["channel"], P(s["attempt_ts"]))
            if cur is not None and cur["status"] == "opt_in":
                sup.append(s["send_id"])
    chk("consent:suppressions_justified", sup, len(send))
    # frequency caps
    per = defaultdict(list)
    for s in D["send_attempts"]:
        if s["status"] == "sent":
            per[s["customer_id"]].append(P(s["attempt_ts"]))
    bad = []
    for c, ts_ in per.items():
        ts_.sort()
        for i in range(len(ts_)):
            if i >= 1 and ts_[i] - ts_[i - 1] < timedelta(hours=24):
                bad.append(c)
            if i >= 3 and ts_[i] - ts_[i - 3] < timedelta(days=7):
                bad.append(c)
    chk("suppression:frequency_cap_1_per_24h_3_per_7d", bad, len(per))
    chk("suppression:purchased_before_send_never_sent", [s["send_id"] for s in D["send_attempts"] if s["status"] == "sent" and msg[s["message_id"]]["cart_id"] in order_by_cart
                                                        and P(order_by_cart[msg[s["message_id"]]["cart_id"]]["order_ts"]) <= P(s["attempt_ts"])], len(send))
    chk("suppression:sms_quiet_hours", [s["send_id"] for s in D["send_attempts"] if s["channel"] == "sms" and s["status"] == "sent" and (P(s["attempt_ts"]).hour >= 21 or P(s["attempt_ts"]).hour < 8)], len(send))
    chk("join:delivery_status_iff_sent", [s["send_id"] for s in D["send_attempts"] if (s["status"] == "sent") != (s["delivery_status"] != "")], len(send))

    # ---- 7. attribution determinism + metric reconciliation
    clicks = defaultdict(list)
    for e in D["send_events"]:
        if e["event_type"] == "clicked":
            s = send[e["send_id"]]
            clicks[msg[s["message_id"]]["cart_id"]].append((P(e["event_ts"]), e["send_id"]))
    A = timedelta(days=7)
    exp_attr = {}
    for o in D["orders"]:
        w = [x for x in clicks.get(o["cart_id"], []) if x[0] <= P(o["order_ts"]) <= x[0] + A]
        if w:
            exp_attr[o["order_id"]] = max(w)
    got = defaultdict(list)
    for a in D["attributions"]:
        got[a["order_id"]].append(a)
    chk("attribution:one_per_order", [o for o, v in got.items() if len(v) > 1], len(got), "orders credited more than once")
    chk("attribution:matches_deterministic_rule",
        [o for o in set(exp_attr) | set(got) if (exp_attr.get(o, (None, None))[1] not in [a["send_id"] for a in got.get(o, [])][:1]) and o not in {x for x, v in got.items() if len(v) > 1}], len(D["orders"]))
    bad = [a["attribution_id"] for a in D["attributions"] if not (P(a["click_ts"]) <= P(a["order_ts"]) <= P(a["click_ts"]) + A)]
    chk("attribution:within_window", bad, len(D["attributions"]))
    clk = {(e["send_id"], e["event_ts"]) for e in D["send_events"] if e["event_type"] == "clicked"}
    chk("attribution:backed_by_click_event", [a["attribution_id"] for a in D["attributions"] if (a["send_id"], a["click_ts"]) not in clk], len(D["attributions"]))
    ordr = {o["order_id"]: o for o in D["orders"]}
    chk("attribution:fields_consistent", [a["attribution_id"] for a in D["attributions"] if a["order_ts"] != ordr[a["order_id"]]["order_ts"] or a["attributed_revenue"] != ordr[a["order_id"]]["order_total"]
                                          or msg[send[a["send_id"]]["message_id"]]["campaign_id"] != a["campaign_id"] or send[a["send_id"]]["message_id"] != a["message_id"]], len(D["attributions"]))

    perf = {}
    for c in D["campaigns"]:
        perf[c["campaign_id"]] = Counter()
    for s in D["send_attempts"]:
        p = perf[msg[s["message_id"]]["campaign_id"]]
        p["attempts"] += 1
        if s["status"] == "sent":
            p["sent"] += 1
            p["delivered"] += s["delivery_status"] == "delivered"
            p["bounced"] += s["delivery_status"] == "bounced"
        else:
            p["suppressed"] += 1
    for e in D["send_events"]:
        if e["event_type"] in ("opened", "clicked", "unsubscribed"):
            perf[msg[send[e["send_id"]]["message_id"]]["campaign_id"]][e["event_type"]] += 1
    seen = set()
    for a in D["attributions"]:
        p = perf[a["campaign_id"]]
        p["attributed_orders_naive"] += 1
        p["revenue_naive_cents"] += C(a["attributed_revenue"])
    dedup_rev = 0
    for o, v in got.items():
        v = sorted(v, key=lambda a: (a["click_ts"], a["send_id"]))
        a = v[-1]
        perf[a["campaign_id"]]["attributed_orders"] += 1
        perf[a["campaign_id"]]["revenue_cents"] += C(a["attributed_revenue"])
        dedup_rev += C(a["attributed_revenue"])
    os.makedirs(os.path.join(d, "reports"), exist_ok=True)
    cols = ["campaign_id", "variant", "channel", "start_date", "attempts", "sent", "suppressed", "delivered", "bounced", "opened", "clicked", "unsubscribed",
            "attributed_orders", "revenue", "attributed_orders_naive", "revenue_naive", "delivery_rate", "click_rate", "conversion_rate_per_sent", "revenue_per_sent"]
    with open(os.path.join(d, "reports", "campaign_performance.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for cid, p in perf.items():
            c = cmp_[cid]
            sent = p["sent"] or 1
            w.writerow([cid, c["variant"], c["channel"], c["start_date"], p["attempts"], p["sent"], p["suppressed"], p["delivered"], p["bounced"], p["opened"], p["clicked"], p["unsubscribed"],
                        p["attributed_orders"], "%.2f" % (p["revenue_cents"] / 100), p["attributed_orders_naive"], "%.2f" % (p["revenue_naive_cents"] / 100),
                        "%.4f" % (p["delivered"] / sent), "%.4f" % (p["clicked"] / sent), "%.4f" % (p["attributed_orders"] / sent), "%.2f" % (p["revenue_cents"] / 100 / sent)])
    tot = Counter()
    for p in perf.values():
        tot.update(p)
    chk("reconcile:attempts=sent+suppressed", [c for c, p in perf.items() if p["attempts"] != p["sent"] + p["suppressed"]], len(perf))
    chk("reconcile:sent=delivered+bounced", [c for c, p in perf.items() if p["sent"] != p["delivered"] + p["bounced"]], len(perf))
    chk("reconcile:clicks<=sent & orders<=clicks", [c for c, p in perf.items() if p["clicked"] > p["sent"] or p["attributed_orders"] > p["clicked"]], len(perf))
    chk("reconcile:campaign_revenue_sum==attribution_sum", [] if tot["revenue_naive_cents"] == sum(C(a["attributed_revenue"]) for a in D["attributions"]) else ["mismatch"], 1)
    chk("reconcile:attributed_revenue<=total_order_revenue", [] if dedup_rev <= sum(C(o["order_total"]) for o in D["orders"]) else ["exceeds"], 1)
    chk("reconcile:naive_vs_dedup_attributed_revenue", [] if tot["revenue_naive_cents"] == dedup_rev else ["double-count $%.2f" % ((tot["revenue_naive_cents"] - dedup_rev) / 100)], 1, "naive credited revenue exceeds de-duplicated")

    # ---- 8. score detection against ground truth (read only now)
    with open(os.path.join(d, "ground_truth", "ground_truth.csv"), encoding="utf-8", newline="") as f:
        gt = list(csv.DictReader(f))
    by = defaultdict(set)
    for g in gt:
        by[g["issue_type"]].add(g["entity_id"])
    cm = {c["check"]: c["_bad"] for c in checks}
    dbl = {a["attribution_id"] for o, v in got.items() if len(v) > 1 for a in sorted(v, key=lambda a: a["attribution_id"])[1:]}
    detect = {
        "message_sent_after_optout": cm["consent:no_send_without_opt_in"],
        "cart_abandoned_after_purchase": cm["lifecycle:abandoned_flag_after_purchase"],
        "cart_total_stale_after_quantity_update": cm["arith:cart_total=sum(lines)"],
        "attribution_double_counted_across_campaigns": dbl,
    }
    anomalies = {}
    for k, found in detect.items():
        exp = by.get(k, set())
        anomalies[k] = dict(injected=len(exp), detected=len(found), exact_match=found == exp)
    boundary = {g["entity_id"]: g["expected_value"] for g in gt if g["issue_type"] == "boundary_abandonment_window"}
    anomalies["boundary_abandonment_window"] = dict(cases=len(boundary), rule_agrees=all((abandon_flag[c] == (v == "abandoned")) or c in by["cart_abandoned_after_purchase"] for c, v in boundary.items()))

    unexpected = {c["check"]: c["violations"] for c in checks if c["violations"] and c["check"] not in (
        "consent:no_send_without_opt_in", "lifecycle:abandoned_flag_after_purchase", "arith:cart_total=sum(lines)", "attribution:one_per_order",
        "reconcile:naive_vs_dedup_attributed_revenue", "attribution:backed_by_click_event", "attribution:matches_deterministic_rule",
        "attribution:fields_consistent", "lifecycle:cart_status_matches_rule")}
    summary = dict(
        data_dir=d.replace("\\", "/"), row_counts={t: len(D[t]) for t in TABLE_ORDER},
        total_checks=len(checks), passed=sum(c["status"] == "PASS" for c in checks), flagged=sum(c["status"] == "FLAGGED" for c in checks),
        unexpected_violations=unexpected,
        injected_anomaly_detection=anomalies,
        metrics=dict(sends=tot["sent"], suppressed=tot["suppressed"], delivered=tot["delivered"], clicked=tot["clicked"],
                     attributed_orders_dedup=tot["attributed_orders"], attributed_revenue_dedup=round(dedup_rev / 100, 2),
                     attributed_revenue_naive=round(tot["revenue_naive_cents"] / 100, 2), orders=len(D["orders"]),
                     abandoned_carts=sum(abandon_flag.values()), recovered_carts=sum(c["status"] == "recovered" for c in D["carts"]),
                     send_status=dict(Counter(s["status"] for s in D["send_attempts"]))),
        checks=[{k: v for k, v in c.items() if k != "_bad"} for c in checks])
    summary["acceptance"] = dict(
        consent_and_suppression_enforced=anomalies["message_sent_after_optout"]["exact_match"] and not cm["suppression:frequency_cap_1_per_24h_3_per_7d"] and not cm["consent:suppressions_justified"],
        abandonment_time_based=not cm["lifecycle:abandonment_is_time_based"],
        attribution_deterministic=anomalies["attribution_double_counted_across_campaigns"]["exact_match"] and not cm["attribution:within_window"],
        metrics_reconcile=all(not c["_bad"] for c in checks if c["check"].startswith("reconcile:") and "naive_vs_dedup" not in c["check"]),
        all_unflagged_checks_clean=not unexpected,
        all_injected_anomalies_detected_exactly=all(v.get("exact_match", True) for v in anomalies.values()))
    with open(os.path.join(d, "validation_summary.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=1)
    md = ["# Validation summary\n", "%d checks: %d PASS, %d FLAGGED (flagged = findings explained by labelled anomalies)\n" % (summary["total_checks"], summary["passed"], summary["flagged"]),
          "## Acceptance\n"] + ["* %s: **%s**" % (k, v) for k, v in summary["acceptance"].items()] + \
         ["\n## Injected anomaly detection\n"] + ["* %s: %s" % (k, json.dumps(v)) for k, v in anomalies.items()] + \
         ["\n## Metrics\n", "```", json.dumps(summary["metrics"], indent=1), "```", "\n## Flagged checks\n"] + \
         ["* %s: %d violation(s) %s" % (c["check"], c["violations"], c["note"]) for c in summary["checks"] if c["violations"]]
    with open(os.path.join(d, "validation_summary.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
