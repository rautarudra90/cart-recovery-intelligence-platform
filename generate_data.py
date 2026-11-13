#!/usr/bin/env python3
"""Cart-abandonment recovery synthetic data generator (stdlib only, deterministic).

    python generate_data.py --out data/full                       # 50k carts / 20k abandoned / 10k sends
    python generate_data.py --scale starter --out data/starter    # 2k carts / 800 abandoned / 400 sends

Pipeline: master data -> carts/sessions/events -> abandonment decisions -> message plan ->
chronological send engine (consent, purchase, frequency-cap rules) -> events/conversions ->
orders -> last-click attribution -> labelled anomaly injection -> exports + ground truth.
Everything random comes from one random.Random(seed); nothing depends on hash order or wall clock.
"""
import argparse
import bisect
import csv
import hashlib
import json
import os
import random
import sys
from datetime import datetime, timedelta

from schema import TABLES, TABLE_ORDER, SQL_TYPES, columns

GENERATOR_VERSION = "1.0"
DEFAULT_SEED = 20261022
FMT = "%Y-%m-%dT%H:%M:%S"
SCALES = {"full": (50000, 20000, 10000), "starter": (2000, 800, 400)}

# ---- documented business rules ------------------------------------------------------------
ABANDON_WINDOW = timedelta(minutes=60)   # no order within 60 min of last cart activity (inclusive) => abandoned
ATTR_WINDOW = timedelta(days=7)          # last-click attribution window, measured from the click
PROMO_VALID = timedelta(days=7)          # promo issued by a click is valid 7 days
MIN_CART_VALUE = 1500                    # cents: below this, abandoned carts are not worth a message
CAP_24H, CAP_7D = 1, 3                   # frequency caps (sent messages per customer, any channel)
STEP2_GAP = timedelta(hours=48)
QUIET_START, QUIET_END = 21, 8           # SMS quiet hours: deferred to 08:00
VARIANTS = {  # channel, step-1 delay (min), discount %, assignment weight
    "V1": dict(channel="email", delay=60, disc=0, w=0.40),
    "V2": dict(channel="email", delay=240, disc=10, w=0.35),
    "V3": dict(channel="sms", delay=120, disc=5, w=0.25),
}
AS_OF = datetime(2026, 11, 15)           # data cut-off: later events are censored
CART_START, CART_END_DAYS = datetime(2026, 1, 1), 273   # carts created 2026-01-01 .. 2026-09-30
HOUR_W = [1, 1, 1, 1, 1, 2, 3, 5, 7, 8, 8, 9, 10, 9, 8, 8, 8, 9, 11, 12, 12, 10, 6, 3]
FIRST = ["Ava", "Liam", "Noah", "Mia", "Zoe", "Ethan", "Ivy", "Leo", "Maya", "Omar", "Priya", "Sara", "Tom", "Uma",
         "Vik", "Wen", "Yara", "Zane", "Ana", "Ben"]
CATS = ["Apparel", "Footwear", "Home", "Beauty", "Electronics", "Outdoor", "Kitchen", "Toys"]


def ts(d):
    return d.strftime(FMT)


def money(c):
    return "%d.%02d" % (c // 100, c % 100)


def pid(prefix, n, width=6):
    return "%s%0*d" % (prefix, width, n)


def is_abandoned(last_activity, purchase_ts):
    return purchase_ts is None or purchase_ts > last_activity + ABANDON_WINDOW


class Gen:
    def __init__(self, a):
        self.a = a
        self.rng = random.Random(a.seed)
        self.sessions = []
        self.gt = []            # ground-truth anomaly rows
        self.labels = []        # expected-decision labels

    # ------------------------------------------------------------------ master data
    def customers_and_consent(self):
        r, n = self.rng, self.a.customers
        t0, span = datetime(2025, 1, 1), int((datetime(2026, 9, 15) - datetime(2025, 1, 1)).total_seconds())
        created = sorted(t0 + timedelta(seconds=r.randrange(span)) for _ in range(n))
        self.customers, self.cons, self.consent_rows = [], {}, []
        self.cons_n = 0
        end = AS_OF - timedelta(days=10)
        for i, c in enumerate(created, 1):
            cust = dict(customer_id=pid("CUS-", i), email="user%06d@example.test" % i,
                        phone=("+1555%07d" % i) if r.random() < 0.75 else "", first_name=r.choice(FIRST),
                        region=r.choices(["NA", "EU", "APAC", "LATAM"], [45, 30, 17, 8])[0],
                        signup_source=r.choices(["web", "app", "store"], [55, 35, 10])[0], created_at=c)
            k = 1 + (r.random() < 0.45) + (r.random() < 0.15)
            cust["devices"] = [("DEV-%06d-%d" % (i, j + 1), dt) for j, dt in enumerate(r.sample(["mobile", "desktop", "tablet"], k))]
            self.customers.append(cust)
            for ch in ("email", "sms"):
                if ch == "sms" and not cust["phone"]:
                    continue
                opt = r.random() < (0.88 if ch == "email" else 0.55)
                self.add_consent(cust["customer_id"], ch, "opt_in" if opt else "opt_out", c, "signup")
                lo = c + timedelta(days=1)
                if opt and r.random() < 0.07 and lo < end:           # consent withdrawal
                    w = lo + timedelta(seconds=r.randrange(int((end - lo).total_seconds())))
                    self.add_consent(cust["customer_id"], ch, "opt_out", w, "preference_center" if ch == "email" or r.random() < .5 else "sms_stop")
                    if r.random() < 0.03 and w + timedelta(days=2) < end:   # re-opt-in
                        self.add_consent(cust["customer_id"], ch, "opt_in", w + timedelta(seconds=r.randrange(2 * 86400, int((end - w).total_seconds()))), "preference_center")
                elif not opt and r.random() < 0.05 and lo < end:      # late opt-in
                    self.add_consent(cust["customer_id"], ch, "opt_in", lo + timedelta(seconds=r.randrange(int((end - lo).total_seconds()))), "preference_center")
        self.cust_created = [c["created_at"] for c in self.customers]
        r = self.rng
        self.products = []
        for i in range(1, 81):
            price = int(min(39900, max(499, r.lognormvariate(3.4, 0.7) * 100)))
            self.products.append(dict(sku="SKU-%04d" % i, product_name="Product %04d" % i, category=r.choice(CATS), price=price))

    def add_consent(self, cid, ch, status, t, source):
        self.cons_n += 1
        row = dict(consent_id=pid("CON-", self.cons_n), customer_id=cid, channel=ch, status=status,
                   effective_from=t, effective_to=None, source=source)
        self.consent_rows.append(row)
        lst = self.cons.setdefault((cid, ch), [])
        lst.append(row)
        lst.sort(key=lambda x: x["effective_from"])

    def consent_at(self, cid, ch, t):
        for row in reversed(self.cons.get((cid, ch), [])):
            if row["effective_from"] <= t:
                return row
        return None

    # ------------------------------------------------------------------ sessions / carts
    def new_session(self, cust, dev, start, purpose="shopping"):
        s = dict(idx=len(self.sessions), customer_id=cust["customer_id"] if cust else "", device_id=dev[0],
                 device_type=dev[1], purpose=purpose, started_at=start, last_ts=start)
        self.sessions.append(s)
        return s

    def ev(self, cart, typ, t, sess, line=None, oq=None, nq=None):
        cart["events"].append(dict(type=typ, ts=t, sess=sess, line=line, oq=oq, nq=nq, seq=len(cart["events"])))
        if sess is not None and t > sess["last_ts"]:
            sess["last_ts"] = t

    def carts_build(self):
        r, n = self.rng, self.a.carts
        hours = r.choices(range(24), HOUR_W, k=n)
        created = sorted(CART_START + timedelta(days=r.randrange(CART_END_DAYS), hours=hours[i],
                                                seconds=r.randrange(3600)) for i in range(n))
        ab = set(r.sample(range(n), self.a.abandoned))
        self.carts, line_n, guest_n = [], 0, 0
        for i, created_at in enumerate(created):
            grp = "abandon" if i in ab else "purchase"
            cust = None
            if r.random() >= (0.25 if grp == "abandon" else 0.15):
                m = bisect.bisect_right(self.cust_created, created_at)
                if m:
                    cust = self.customers[int(m * r.random() ** 2.5)]
            if cust:
                dev = r.choice(cust["devices"])
            else:
                guest_n += 1
                dev = ("DEV-G%06d" % guest_n, r.choice(["mobile", "mobile", "desktop", "tablet"]))
            cart = dict(cart_id=pid("CART-2026-", i + 1), seq=i, cust=cust, created=created_at, grp=grp, lines=[],
                        events=[], sess_roles=[], purchase_ts=None, purchase_sess=None, driver=None, driver_click=None,
                        promo_pct=0, pre_total=None, flag_anomaly=False, stale=False, dev=dev)
            s1 = self.new_session(cust, dev, created_at)
            cart["sess_roles"].append((s1, "created"))
            t = created_at
            self.ev(cart, "cart_created", t, s1)
            nl = r.choices([1, 2, 3, 4, 5], [40, 28, 17, 10, 5])[0]
            for p in r.sample(self.products, nl):
                t += timedelta(seconds=r.randint(15, 420))
                line_n += 1
                q0 = r.choices([1, 2, 3, 4], [62, 25, 9, 4])[0]
                line = dict(id=pid("LINE-2026-", line_n), no=len(cart["lines"]) + 1, sku=p["sku"], qty=q0, price=p["price"], added=t)
                cart["lines"].append(line)
                self.ev(cart, "item_added", t, s1, line, None, q0)
            cur = s1
            multi = bool(cust) and len(cust["devices"]) > 1 and r.random() < 0.28
            if multi:
                other = r.choice([d for d in cust["devices"] if d != dev])
                t += timedelta(seconds=r.randint(120, 2400))
                cur = self.new_session(cust, other, t)
                cart["sess_roles"].append((cur, "modified"))
            if r.random() < 0.22:
                line = r.choice(cart["lines"])
                q_new = r.choice([q for q in (1, 2, 3, 4, 5) if q != line["qty"]])
                cart["pre_total"] = sum(l["qty"] * l["price"] for l in cart["lines"])
                t += timedelta(seconds=r.randint(20, 600))
                self.ev(cart, "quantity_updated", t, cur, line, line["qty"], q_new)
                line["qty"] = q_new
            if multi or r.random() < (0.85 if grp == "purchase" else 0.35):
                t += timedelta(seconds=r.randint(30, 900))
                self.ev(cart, "checkout_started", t, cur)
                cart["checkout"] = True
            else:
                cart["checkout"] = False
            cart["last"] = t
            cart["total"] = sum(l["qty"] * l["price"] for l in cart["lines"])
            if cart["pre_total"] is not None and cart["pre_total"] == cart["total"]:
                cart["pre_total"] = None
            if grp == "purchase":
                x = r.random()
                d = 3600 if x < 0.01 else r.randint(3300, 3599) if x < 0.03 else r.randint(60, 3300)
                cart["purchase_ts"], cart["purchase_sess"] = t + timedelta(seconds=d), cur
                cart["boundary"] = d == 3600
                self.ev(cart, "purchased", cart["purchase_ts"], cur)
            else:                                   # latent organic return (decided by cart intent, documented)
                if r.random() < (0.28 if cart["checkout"] else 0.12):
                    x = r.random()
                    if x < 0.01:
                        d, cart["boundary"] = 3660, True
                    elif x < 0.46:
                        d = 3660 + int(r.expovariate(1 / 21600))
                    else:
                        d = 3660 + int(min(r.lognormvariate(12.3, 1.0), 35 * 86400))
                    p_ts = t + timedelta(seconds=d)
                    if p_ts <= AS_OF:
                        cart["purchase_ts"] = p_ts
                cart["organic"] = cart["purchase_ts"]
            cart["abandoned"] = is_abandoned(cart["last"], cart["purchase_ts"])
            assert cart["abandoned"] == (grp == "abandon")
            cart["abandoned_at"] = cart["last"] + ABANDON_WINDOW if cart["abandoned"] else None
            if cart["abandoned"]:
                self.ev(cart, "abandoned_flagged", cart["abandoned_at"], None)
            self.carts.append(cart)

    # ------------------------------------------------------------------ decisions & plan
    def decisions_and_plan(self):
        r = self.rng
        elig = []
        for c in self.carts:
            if not c["abandoned"]:
                continue
            if c["cust"] is None:
                c["decision"] = ("ineligible_guest", "no_contactable_customer")
            elif c["total"] < MIN_CART_VALUE:
                c["decision"] = ("ineligible_low_value", "cart_total_below_min_value")
            else:
                elig.append(c)
        k = min(len(elig), round(self.a.sends / 1.3))
        targeted = set(x["cart_id"] for x in r.sample(elig, k))
        for c in elig:
            c["decision"] = ("targeted", "selected_within_send_budget") if c["cart_id"] in targeted else ("holdout", "send_budget_holdout")
        tl = [c for c in elig if c["cart_id"] in targeted]
        k2 = min(len(tl), self.a.sends - k)
        step2 = set(x["cart_id"] for x in r.sample(tl, k2))
        self.msgs = []
        for c in tl:
            v = r.choices(list(VARIANTS), [VARIANTS[x]["w"] for x in VARIANTS])[0]
            if v == "V3" and not c["cust"]["phone"]:
                v = "V2"                           # no phone => email fallback
            c["variant"] = v
            planned = c["abandoned_at"] + timedelta(minutes=VARIANTS[v]["delay"])
            for step in ((1, 2) if c["cart_id"] in step2 else (1,)):
                p = planned + (STEP2_GAP if step == 2 else timedelta(0))
                ch = VARIANTS[v]["channel"]
                eff = p
                if ch == "sms" and (p.hour >= QUIET_START or p.hour < QUIET_END):
                    day = p.date() + timedelta(days=1 if p.hour >= QUIET_START else 0)
                    eff = datetime(day.year, day.month, day.day, QUIET_END) + timedelta(seconds=r.randrange(1800))
                self.msgs.append(dict(message_id="MSG-%s-%02d" % (c["cart_id"], step), cart=c, step=step, variant=v,
                                      channel=ch, planned=p, eff=eff))

    # ------------------------------------------------------------------ send engine
    def send_engine(self):
        r = self.rng
        tpl = {}
        for v, d in VARIANTS.items():
            for step in (1, 2):
                tpl[(v, step)] = dict(template_id="TPL-%s-S%d" % (v, step), variant=v, channel=d["channel"], step=step,
                                      subject=("We saved your cart" if step == 1 else "Still thinking it over?") + (" - %d%% off" % d["disc"] if d["disc"] else "") if d["channel"] == "email" else "",
                                      discount_pct=d["disc"], version=1, effective_from="2026-01-01")
        self.templates = tpl
        self.camps, self.campaign_templates = {}, []
        self.sends, self.send_events, self.sent_by_cust = [], [], {}
        optout_budget = max(3, round(self.a.sends * 0.005))
        send_n = 0
        for m in sorted(self.msgs, key=lambda x: (x["eff"], x["message_id"])):
            c, t, ch, cid = m["cart"], m["eff"], m["channel"], m["cart"]["cust"]["customer_id"]
            wk = (t - timedelta(days=t.weekday())).date()
            key = (m["variant"], wk)
            if key not in self.camps:
                v = VARIANTS[m["variant"]]
                camp = dict(campaign_id=pid("CMP-2026-", len(self.camps) + 1), name="Cart recovery %s wk %s" % (m["variant"], wk.isoformat()),
                            variant=m["variant"], channel=v["channel"], start_date=wk.isoformat(),
                            end_date=(wk + timedelta(days=6)).isoformat(), delay_minutes=v["delay"], attribution_window_days=7, status="completed")
                self.camps[key] = camp
                for step in (1, 2):
                    self.campaign_templates.append((camp["campaign_id"], tpl[(m["variant"], step)]["template_id"]))
            m["camp"], m["tpl"] = self.camps[key], tpl[(m["variant"], m["step"])]
            cons = self.consent_at(cid, ch, t)
            status, inj = "sent", None
            if cons is None or cons["status"] != "opt_in":
                ever = any(x["status"] == "opt_in" and x["effective_from"] <= t for x in self.cons.get((cid, ch), []))
                reason = "suppressed_consent_withdrawn" if ever else "suppressed_no_consent"   # withdrawn = had opted in before
                if cons is not None and optout_budget > 0 and r.random() < 0.08:
                    inj, optout_budget, status = reason, optout_budget - 1, "sent"   # labelled defect: sent despite opt-out
                else:
                    status = reason
            hist = self.sent_by_cust.setdefault(cid, [])
            n24 = sum(1 for x in hist if x > t - timedelta(hours=24))
            n7 = sum(1 for x in hist if x > t - timedelta(days=7))
            if status == "sent":
                if c["purchase_ts"] is not None and c["purchase_ts"] <= t:
                    status = "suppressed_already_purchased"
                elif n24 >= CAP_24H or n7 >= CAP_7D:
                    status = "suppressed_frequency_cap"
            send_n += 1
            snd = dict(send_id=pid("SEND-2026-", send_n), msg=m, customer_id=cid, channel=ch, ts=t, status=status,
                       consent_id=cons["consent_id"] if cons else "", n24=n24, n7=n7, delivery="", inj=inj, click=None)
            self.sends.append(snd)
            m["send"] = snd
            if inj and status == "sent":
                self.gt.append(dict(issue_type="message_sent_after_optout", entity_type="send_attempt", entity_id=snd["send_id"],
                                    related_entity_id=cons["consent_id"], expected_value=inj, observed_value="sent",
                                    description="Message sent while the channel consent in force was opt_out"))
            if status != "sent":
                continue
            hist.append(t)
            self.events_for(snd, m, c)

    def events_for(self, snd, m, c):
        r, t, ch, d = self.rng, snd["ts"], snd["channel"], m["tpl"]["discount_pct"]
        E = lambda typ, when: self.send_events.append(dict(send=snd, type=typ, ts=when))
        if r.random() < (0.025 if ch == "email" else 0.015):
            snd["delivery"] = "bounced"
            E("bounced", t + timedelta(seconds=r.randint(5, 300)))
            return
        snd["delivery"] = "delivered"
        dl = t + timedelta(seconds=r.randint(2, 120) if ch == "email" else r.randint(1, 30))
        E("delivered", dl)
        last, click = dl, None
        if ch == "email":
            if r.random() < 0.42 + (0.04 if d else 0):
                last = dl + timedelta(seconds=int(r.lognormvariate(6.5, 1.1)) + 1)
                E("opened", last)
                if r.random() < 0.28 + d * 0.004 and not snd["inj"]:
                    click = last + timedelta(seconds=r.randint(5, 600))
        elif r.random() < 0.09 + d * 0.004 and not snd["inj"]:
            click = dl + timedelta(seconds=int(r.lognormvariate(5.5, 1.0)) + 1)
        if click:
            E("clicked", click)
            last = click
            snd["click"] = click
            self.convert(c, snd, click, d)
        if not snd["inj"] and r.random() < (0.004 if ch == "email" else 0.008):
            u = last + timedelta(seconds=r.randint(10, 900))
            E("unsubscribed", u)
            self.add_consent(snd["customer_id"], ch, "opt_out", u, "unsubscribe_link" if ch == "email" else "sms_stop")

    def convert(self, c, snd, click, disc):
        """Click -> purchase propensity rule: channel base + discount uplift, scaled by cart value."""
        r = self.rng
        if c["purchase_ts"] is not None and c["purchase_ts"] <= click:
            return
        p = (0.30 if snd["channel"] == "email" else 0.38) + disc * 0.012
        p *= 0.8 if c["total"] < 4000 else 1.2 if c["total"] > 20000 else 1.0
        if r.random() >= p:
            return
        delay = r.randint(2 * 86400, 14 * 86400) if r.random() < 0.12 else 240 + int(r.expovariate(1 / 14400))
        conv = click + timedelta(seconds=delay)
        if conv <= AS_OF and (c["purchase_ts"] is None or conv < c["purchase_ts"]):
            c["purchase_ts"], c["driver"], c["driver_click"] = conv, snd["send_id"], click
            c["promo_pct"] = disc if conv <= click + PROMO_VALID else 0

    # ------------------------------------------------------------------ orders & attribution
    def finalize_carts_orders(self):
        r = self.rng
        for c in self.carts:                        # recovery sessions
            if c["abandoned"] and c["purchase_ts"] is not None:
                p = c["purchase_ts"]
                start = max(p - timedelta(seconds=r.randint(60, 1200)), c["abandoned_at"] + timedelta(seconds=1))
                if c["driver_click"]:
                    start = max(start, c["driver_click"] + timedelta(seconds=10))
                if start >= p:
                    start = p - timedelta(seconds=5)
                dev = r.choice(c["cust"]["devices"]) if c["cust"] else c["dev"]
                s = self.new_session(c["cust"], dev, start, "recovery_return")
                c["sess_roles"].append((s, "recovery_visit"))
                c["purchase_sess"] = s
                self.ev(c, "cart_resumed", start, s)
                self.ev(c, "purchased", p, s)
            c["status"] = ("purchased" if not c["abandoned"] else "recovered" if c["purchase_ts"] else "abandoned")
            c["expected_status"] = c["status"]
            self.labels.append(("cart", c["cart_id"], "expected_abandoned", str(c["abandoned"]).lower()))
            self.labels.append(("cart", c["cart_id"], "expected_status", c["status"]))
            if c.get("boundary"):
                self.gt.append(dict(issue_type="boundary_abandonment_window", entity_type="cart", entity_id=c["cart_id"], related_entity_id="",
                                    expected_value=("not_abandoned" if not c["abandoned"] else "abandoned"), observed_value="",
                                    description="Order placed at last_activity+60min (inclusive => not abandoned) or +61min (abandoned)"))
        self.orders = []
        for c in sorted((c for c in self.carts if c["purchase_ts"] is not None), key=lambda c: (c["purchase_ts"], c["cart_id"])):
            sub = c["total"]
            disc = int(round(sub * c["promo_pct"] / 100.0))
            ship = 599 if sub < 7500 else 0
            self.orders.append(dict(order_id=pid("ORD-2026-", len(self.orders) + 1), cart=c, customer_id=c["cust"]["customer_id"] if c["cust"] else "",
                                    session=c["purchase_sess"], ts=c["purchase_ts"], subtotal=sub, discount=disc, shipping=ship,
                                    total=sub - disc + ship, promo=("RECOVER%d" % c["promo_pct"]) if c["promo_pct"] else ""))
        clicks = {}
        for s in self.sends:
            if s["click"]:
                clicks.setdefault(s["msg"]["cart"]["cart_id"], []).append((s["click"], s["send_id"], s))
        self.attrs = []
        for o in self.orders:
            cc = clicks.get(o["cart"]["cart_id"], [])
            win = [x for x in cc if x[0] <= o["ts"] <= x[0] + ATTR_WINDOW]
            before = [x for x in cc if x[0] <= o["ts"]]
            true_driver = "campaign:" + o["cart"]["driver"] if o["cart"]["driver"] else "organic_or_in_session"
            if win:
                click_ts, sid, s = max(win, key=lambda x: (x[0], x[1]))
                self.attrs.append(dict(attribution_id=pid("ATT-2026-", len(self.attrs) + 1), order=o, send=s, click=click_ts))
                exp, why = sid, "last_click_within_7d"
            else:
                exp, why = "", ("late_purchase_outside_window" if before else "no_click_before_order")
            self.labels.append(("order", o["order_id"], "expected_attributed_send_id", exp))
            self.labels.append(("order", o["order_id"], "expected_attribution_reason", why))
            self.labels.append(("order", o["order_id"], "true_conversion_driver", true_driver))

    # ------------------------------------------------------------------ anomalies
    def inject(self):
        r, n = self.rng, self.a.carts
        k = max(3, round(n * 0.0015))
        pool = [c for c in self.carts if c["pre_total"] is not None]
        for c in r.sample(pool, min(k, len(pool))):                    # stale cart total after quantity update
            c["stale"] = True
            self.gt.append(dict(issue_type="cart_total_stale_after_quantity_update", entity_type="cart", entity_id=c["cart_id"], related_entity_id="",
                                expected_value=money(c["total"]), observed_value=money(c["pre_total"]),
                                description="cart_total kept pre-update value after quantity_updated event"))
        pool = [c for c in self.carts if not c["abandoned"] and not c["stale"]]
        for c in r.sample(pool, min(max(3, round(n * 0.0012)), len(pool))):   # abandoned flag raised after purchase
            c["flag_anomaly"] = True
            c["abandoned_at"] = c["last"] + ABANDON_WINDOW
            c["decision"] = ("holdout", "send_budget_holdout")
            c["status"] = "abandoned"
            self.ev(c, "abandoned_flagged", c["abandoned_at"], None)
            self.gt.append(dict(issue_type="cart_abandoned_after_purchase", entity_type="cart", entity_id=c["cart_id"], related_entity_id="",
                                expected_value="purchased", observed_value="abandoned",
                                description="abandoned_flagged event and status=abandoned although order exists before abandoned_at"))
        by_cust = {}
        for s in self.sends:
            if s["status"] == "sent":
                by_cust.setdefault(s["customer_id"], []).append(s)
        want, done = max(3, round(len(self.attrs) * 0.02)), 0
        extra = []
        for a in r.sample(self.attrs, len(self.attrs)):
            if done >= want:
                break
            o = a["order"]
            alt = [s for s in by_cust.get(o["customer_id"], []) if s["msg"]["camp"]["campaign_id"] != a["send"]["msg"]["camp"]["campaign_id"]
                   and s["ts"] + timedelta(seconds=60) <= o["ts"] <= s["ts"] + timedelta(seconds=30) + ATTR_WINDOW]
            if alt:
                s = r.choice(alt)
                extra.append(dict(attribution_id=pid("ATT-2026-", len(self.attrs) + len(extra) + 1), order=o, send=s, click=s["ts"] + timedelta(seconds=30)))
                done += 1
                self.gt.append(dict(issue_type="attribution_double_counted_across_campaigns", entity_type="attribution", entity_id=extra[-1]["attribution_id"],
                                    related_entity_id=a["attribution_id"], expected_value="1 attribution per order", observed_value="2 attributions",
                                    description="order %s credited to campaigns %s and %s" % (o["order_id"], a["send"]["msg"]["camp"]["campaign_id"], s["msg"]["camp"]["campaign_id"])))
        self.attrs += extra

    # ------------------------------------------------------------------ tables
    def build_tables(self):
        r, T = self.rng, {}
        # consent effective_to (back-fill only)
        for lst in self.cons.values():
            for i, row in enumerate(lst):
                row["effective_to"] = lst[i + 1]["effective_from"] if i + 1 < len(lst) else None
        T["customers"] = [dict(c, created_at=ts(c["created_at"])) for c in self.customers]
        T["consents"] = [dict(x, effective_from=ts(x["effective_from"]), effective_to=ts(x["effective_to"]) if x["effective_to"] else "")
                         for x in sorted(self.consent_rows, key=lambda x: x["consent_id"])]
        T["products"] = [dict(sku=p["sku"], product_name=p["product_name"], category=p["category"], unit_price=money(p["price"])) for p in self.products]
        ss = sorted(self.sessions, key=lambda s: (s["started_at"], s["idx"]))
        for i, s in enumerate(ss, 1):
            s["session_id"] = pid("SES-2026-", i)
            s["ended_at"] = s["last_ts"] + timedelta(seconds=r.randint(30, 900))
        T["sessions"] = [dict(s, started_at=ts(s["started_at"]), ended_at=ts(s["ended_at"])) for s in ss]
        T["carts"], T["cart_sessions"], T["cart_lines"], evs, T["abandonment_decisions"] = [], [], [], [], []
        for c in self.carts:
            true_total = c["total"]
            stored = c["pre_total"] if c["stale"] else true_total
            T["carts"].append(dict(cart_id=c["cart_id"], customer_id=c["cust"]["customer_id"] if c["cust"] else "", created_at=ts(c["created"]),
                                   last_activity_at=ts(c["last"]), currency="USD", item_count=sum(l["qty"] for l in c["lines"]),
                                   cart_total=money(stored), status=c["status"],
                                   abandoned_at=ts(c["abandoned_at"]) if (c["abandoned"] or c["flag_anomaly"]) else ""))
            for s, role in c["sess_roles"]:
                T["cart_sessions"].append(dict(cart_id=c["cart_id"], session_id=s["session_id"], role=role))
            for l in c["lines"]:
                T["cart_lines"].append(dict(cart_line_id=l["id"], cart_id=c["cart_id"], line_no=l["no"], sku=l["sku"], quantity=l["qty"],
                                            unit_price=money(l["price"]), line_total=money(l["qty"] * l["price"]), added_at=ts(l["added"])))
            for e in c["events"]:
                evs.append((e["ts"], c["seq"], e["seq"], c, e))
            if c["abandoned"] or c["flag_anomaly"]:
                d = c["decision"]
                T["abandonment_decisions"].append(dict(decision_id=pid("ABD-2026-", len(T["abandonment_decisions"]) + 1), cart_id=c["cart_id"],
                                                       abandoned_at=ts(c["abandoned_at"]), recovery_decision=d[0], reason=d[1]))
        evs.sort(key=lambda x: x[:3])
        T["cart_events"] = [dict(cart_event_id=pid("CEV-2026-", i), cart_id=c["cart_id"], session_id=e["sess"]["session_id"] if e["sess"] else "",
                                 event_type=e["type"], event_ts=ts(e["ts"]), cart_line_id=e["line"]["id"] if e["line"] else "",
                                 old_quantity="" if e["oq"] is None else e["oq"], new_quantity="" if e["nq"] is None else e["nq"])
                            for i, (_, _, _, c, e) in enumerate(evs, 1)]
        T["campaigns"] = list(self.camps.values())
        T["message_templates"] = [self.templates[k] for k in sorted(self.templates)]
        T["campaign_templates"] = [dict(campaign_id=a, template_id=b) for a, b in self.campaign_templates]
        T["scheduled_messages"] = [dict(message_id=m["message_id"], cart_id=m["cart"]["cart_id"], customer_id=m["cart"]["cust"]["customer_id"],
                                        campaign_id=m["camp"]["campaign_id"], template_id=m["tpl"]["template_id"], step=m["step"], channel=m["channel"],
                                        planned_ts=ts(m["planned"]), scheduled_ts=ts(m["eff"])) for m in sorted(self.msgs, key=lambda m: m["message_id"])]
        T["send_attempts"] = [dict(send_id=s["send_id"], message_id=s["msg"]["message_id"], customer_id=s["customer_id"], channel=s["channel"],
                                   attempt_ts=ts(s["ts"]), status=s["status"], consent_id=s["consent_id"], sends_last_24h=s["n24"],
                                   sends_last_7d=s["n7"], delivery_status=s["delivery"]) for s in self.sends]
        order_pri = {"delivered": 0, "bounced": 0, "opened": 1, "clicked": 2, "unsubscribed": 3}
        se = sorted(self.send_events, key=lambda e: (e["ts"], e["send"]["send_id"], order_pri[e["type"]]))
        T["send_events"] = [dict(event_id=pid("EVT-2026-", i), send_id=e["send"]["send_id"], event_type=e["type"], event_ts=ts(e["ts"])) for i, e in enumerate(se, 1)]
        T["orders"] = [dict(order_id=o["order_id"], customer_id=o["customer_id"], cart_id=o["cart"]["cart_id"], session_id=o["session"]["session_id"],
                            order_ts=ts(o["ts"]), subtotal=money(o["subtotal"]), discount_amount=money(o["discount"]), shipping_fee=money(o["shipping"]),
                            order_total=money(o["total"]), promo_code=o["promo"]) for o in self.orders]
        T["attributions"] = []
        for a in self.attrs:
            o, s = a["order"], a["send"]
            T["attributions"].append(dict(attribution_id=a["attribution_id"], order_id=o["order_id"], send_id=s["send_id"], message_id=s["msg"]["message_id"],
                                          campaign_id=s["msg"]["camp"]["campaign_id"], model="last_click", window_days=7, click_ts=ts(a["click"]),
                                          order_ts=ts(o["ts"]), lag_hours="%.2f" % ((o["ts"] - a["click"]).total_seconds() / 3600.0),
                                          attributed_revenue=money(o["total"])))
        for s in self.sends:
            if s["status"] != "sent" or s["inj"]:
                exp = s["inj"] or s["status"]
                self.labels.append(("send_attempt", s["send_id"], "expected_status", exp))
            else:
                self.labels.append(("send_attempt", s["send_id"], "expected_status", s["status"]))
        return T


def write_csv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for r in rows:
            w.writerow([r[c] for c in cols])


def sql_lit(v, typ):
    if v == "" or v is None:
        return "NULL"
    if typ in ("int", "decimal"):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def ddl():
    out = ["PRAGMA foreign_keys = ON;"]
    for t in TABLE_ORDER:
        d, lines = TABLES[t], []
        for f in d["fields"]:
            lines.append("  %s %s%s" % (f["name"], SQL_TYPES[f["type"]], " NOT NULL" if f["required"] else ""))
        lines.append("  PRIMARY KEY (%s)" % ", ".join(d["pk"]))
        for col, rt, rc in d["fks"]:
            lines.append("  FOREIGN KEY (%s) REFERENCES %s(%s)" % (col, rt, rc))
        out.append("CREATE TABLE %s (\n%s\n);" % (t, ",\n".join(lines)))
    return "\n\n".join(out) + "\n"


def data_dictionary_md():
    out = ["# Data dictionary\n", "Empty CSV cell = NULL (allowed only where Required = N). Timestamps are naive ISO-8601 (store-local), money is USD with 2 dp.\n"]
    for t in TABLE_ORDER:
        d = TABLES[t]
        out.append("\n## %s\n\n%s\n\n* **Primary key:** %s\n* **Foreign keys:** %s\n* **Cardinality:** %s\n" % (
            t, d["desc"], ", ".join(d["pk"]), "; ".join("%s -> %s.%s" % x for x in d["fks"]) or "none", d["cardinality"]))
        out.append("| Field | Type | Required | Allowed values | Unit | Unique | Validation rule |\n|---|---|---|---|---|---|---|")
        for f in d["fields"]:
            al = ", ".join(map(str, f["allowed"])) if isinstance(f["allowed"], list) else f["allowed"]
            out.append("| %s | %s | %s | %s | %s | %s | %s |" % (f["name"], f["type"], "Y" if f["required"] else "N", al, f["unit"], "Y" if f["unique"] else "", f["rule"]))
    return "\n".join(out) + "\n"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def readme(a, counts, cmd):
    rows = "\n".join("| %s | %d |" % (t, counts[t]) for t in TABLE_ORDER)
    return f"""# Cart-abandonment recovery dataset

Synthetic, fully reproducible data for: identify abandoned carts -> respect consent -> run personalised recovery
campaigns -> attribute conversions. **No external/public data is used** (see `source_manifest.json`); all names,
e-mails (`@example.test`) and phones are fabricated.

* Generator command: `{cmd}`
* Fixed seed: `{a.seed}` (carts={a.carts}, abandoned={a.abandoned}, sends={a.sends}, customers={a.customers})
* Validate: `python validate_data.py --data <dir>`; reproducibility: `python repro_check.py --out <dir>`

## Files
`*.csv` one per entity (see `data_dictionary.md` / `data_dictionary.json`), `schema.sql` (DDL with PK/FK),
`seed.sql` (INSERTs), `ground_truth/` (**labels only - never use as model/analysis input**), `source_manifest.json`
(row counts + SHA-256), `validation_summary.json`, `reproducibility_report.json`.

| table | rows |
|---|---|
{rows}

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
* Timestamps are naive local time; data cut-off is {AS_OF.date()} (later orders are censored).
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/full")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--scale", choices=list(SCALES), default="full")
    ap.add_argument("--carts", type=int)
    ap.add_argument("--abandoned", type=int)
    ap.add_argument("--sends", type=int)
    ap.add_argument("--customers", type=int)
    ap.add_argument("--no-sql", action="store_true", help="skip seed.sql")
    a = ap.parse_args()
    c, ab, s = SCALES[a.scale]
    a.carts, a.abandoned, a.sends = a.carts or c, a.abandoned or ab, a.sends or s
    a.customers = a.customers or int(a.carts * 0.4)
    if a.abandoned > a.carts:
        sys.exit("--abandoned cannot exceed --carts")
    cmd = "python generate_data.py --out <dir> --seed %d --carts %d --abandoned %d --sends %d --customers %d" % (
        a.seed, a.carts, a.abandoned, a.sends, a.customers)

    g = Gen(a)
    g.customers_and_consent()
    g.carts_build()
    g.decisions_and_plan()
    g.send_engine()
    g.finalize_carts_orders()
    g.inject()
    T = g.build_tables()

    os.makedirs(os.path.join(a.out, "ground_truth"), exist_ok=True)
    for t in TABLE_ORDER:
        write_csv(os.path.join(a.out, t + ".csv"), columns(t), T[t])
    gtc = ["gt_id", "issue_type", "entity_type", "entity_id", "related_entity_id", "expected_value", "observed_value", "description"]
    gt = sorted(g.gt, key=lambda x: (x["issue_type"], x["entity_id"]))
    for i, x in enumerate(gt, 1):
        x["gt_id"] = pid("GT-", i)
    write_csv(os.path.join(a.out, "ground_truth", "ground_truth.csv"), gtc, gt)
    with open(os.path.join(a.out, "ground_truth", "ground_truth.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(gt, f, indent=1)
    lab = [dict(entity_type=x[0], entity_id=x[1], label_name=x[2], expected_value=x[3]) for x in g.labels]
    write_csv(os.path.join(a.out, "ground_truth", "expected_labels.csv"), ["entity_type", "entity_id", "label_name", "expected_value"], lab)

    with open(os.path.join(a.out, "schema.sql"), "w", newline="\n") as f:
        f.write(ddl())
    if not a.no_sql:
        with open(os.path.join(a.out, "seed.sql"), "w", newline="\n", encoding="utf-8") as f:
            f.write("PRAGMA foreign_keys = ON;\nBEGIN;\n")
            for t in TABLE_ORDER:
                fl = TABLES[t]["fields"]
                for i in range(0, len(T[t]), 500):
                    vals = ",\n".join("(" + ",".join(sql_lit(r[x["name"]], x["type"]) for x in fl) + ")" for r in T[t][i:i + 500])
                    f.write("INSERT INTO %s (%s) VALUES\n%s;\n" % (t, ",".join(columns(t)), vals))
            f.write("COMMIT;\n")
    with open(os.path.join(a.out, "data_dictionary.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(data_dictionary_md())
    with open(os.path.join(a.out, "data_dictionary.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({t: dict(TABLES[t]) for t in TABLE_ORDER}, f, indent=1)
    counts = {t: len(T[t]) for t in TABLE_ORDER}
    with open(os.path.join(a.out, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(readme(a, counts, cmd))
    files = sorted(x for x in (os.path.join(dp, fn) for dp, _, fns in os.walk(a.out) for fn in fns)
                   if os.path.basename(x) not in ("source_manifest.json", "validation_summary.json", "validation_summary.md", "reproducibility_report.json"))
    manifest = dict(generator="generate_data.py", generator_version=GENERATOR_VERSION, command=cmd, seed=a.seed,
                    parameters=dict(carts=a.carts, abandoned_carts=a.abandoned, sends=a.sends, customers=a.customers, as_of=ts(AS_OF)),
                    external_data_used=False,
                    provenance="All data synthetic, generated by generate_data.py; no public datasets, no personal data. Reserved example.test domain.",
                    row_counts=counts,
                    files={os.path.relpath(p, a.out).replace("\\", "/"): sha256(p) for p in files})
    with open(os.path.join(a.out, "source_manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=1)
    print("wrote", a.out, json.dumps(counts))
    print("anomalies:", {k: sum(1 for x in gt if x["issue_type"] == k) for k in sorted(set(x["issue_type"] for x in gt))})


if __name__ == "__main__":
    main()
