PRAGMA foreign_keys = ON;

CREATE TABLE customers (
  customer_id TEXT NOT NULL,
  email TEXT NOT NULL,
  phone TEXT,
  first_name TEXT NOT NULL,
  region TEXT NOT NULL,
  signup_source TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (customer_id)
);

CREATE TABLE consents (
  consent_id TEXT NOT NULL,
  customer_id TEXT NOT NULL,
  channel TEXT NOT NULL,
  status TEXT NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  source TEXT NOT NULL,
  PRIMARY KEY (consent_id),
  FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE products (
  sku TEXT NOT NULL,
  product_name TEXT NOT NULL,
  category TEXT NOT NULL,
  unit_price NUMERIC(12,2) NOT NULL,
  PRIMARY KEY (sku)
);

CREATE TABLE sessions (
  session_id TEXT NOT NULL,
  customer_id TEXT,
  device_id TEXT NOT NULL,
  device_type TEXT NOT NULL,
  purpose TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT NOT NULL,
  PRIMARY KEY (session_id),
  FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE carts (
  cart_id TEXT NOT NULL,
  customer_id TEXT,
  created_at TEXT NOT NULL,
  last_activity_at TEXT NOT NULL,
  currency TEXT NOT NULL,
  item_count INTEGER NOT NULL,
  cart_total NUMERIC(12,2) NOT NULL,
  status TEXT NOT NULL,
  abandoned_at TEXT,
  PRIMARY KEY (cart_id),
  FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE cart_sessions (
  cart_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  PRIMARY KEY (cart_id, session_id),
  FOREIGN KEY (cart_id) REFERENCES carts(cart_id),
  FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE TABLE cart_lines (
  cart_line_id TEXT NOT NULL,
  cart_id TEXT NOT NULL,
  line_no INTEGER NOT NULL,
  sku TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  unit_price NUMERIC(12,2) NOT NULL,
  line_total NUMERIC(12,2) NOT NULL,
  added_at TEXT NOT NULL,
  PRIMARY KEY (cart_line_id),
  FOREIGN KEY (cart_id) REFERENCES carts(cart_id),
  FOREIGN KEY (sku) REFERENCES products(sku)
);

CREATE TABLE cart_events (
  cart_event_id TEXT NOT NULL,
  cart_id TEXT NOT NULL,
  session_id TEXT,
  event_type TEXT NOT NULL,
  event_ts TEXT NOT NULL,
  cart_line_id TEXT,
  old_quantity INTEGER,
  new_quantity INTEGER,
  PRIMARY KEY (cart_event_id),
  FOREIGN KEY (cart_id) REFERENCES carts(cart_id),
  FOREIGN KEY (session_id) REFERENCES sessions(session_id),
  FOREIGN KEY (cart_line_id) REFERENCES cart_lines(cart_line_id)
);

CREATE TABLE abandonment_decisions (
  decision_id TEXT NOT NULL,
  cart_id TEXT NOT NULL,
  abandoned_at TEXT NOT NULL,
  recovery_decision TEXT NOT NULL,
  reason TEXT NOT NULL,
  PRIMARY KEY (decision_id),
  FOREIGN KEY (cart_id) REFERENCES carts(cart_id)
);

CREATE TABLE campaigns (
  campaign_id TEXT NOT NULL,
  name TEXT NOT NULL,
  variant TEXT NOT NULL,
  channel TEXT NOT NULL,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  delay_minutes INTEGER NOT NULL,
  attribution_window_days INTEGER NOT NULL,
  status TEXT NOT NULL,
  PRIMARY KEY (campaign_id)
);

CREATE TABLE message_templates (
  template_id TEXT NOT NULL,
  variant TEXT NOT NULL,
  channel TEXT NOT NULL,
  step INTEGER NOT NULL,
  subject TEXT,
  discount_pct INTEGER NOT NULL,
  version INTEGER NOT NULL,
  effective_from TEXT NOT NULL,
  PRIMARY KEY (template_id)
);

CREATE TABLE campaign_templates (
  campaign_id TEXT NOT NULL,
  template_id TEXT NOT NULL,
  PRIMARY KEY (campaign_id, template_id),
  FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id),
  FOREIGN KEY (template_id) REFERENCES message_templates(template_id)
);

CREATE TABLE scheduled_messages (
  message_id TEXT NOT NULL,
  cart_id TEXT NOT NULL,
  customer_id TEXT NOT NULL,
  campaign_id TEXT NOT NULL,
  template_id TEXT NOT NULL,
  step INTEGER NOT NULL,
  channel TEXT NOT NULL,
  planned_ts TEXT NOT NULL,
  scheduled_ts TEXT NOT NULL,
  PRIMARY KEY (message_id),
  FOREIGN KEY (cart_id) REFERENCES carts(cart_id),
  FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
  FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id),
  FOREIGN KEY (template_id) REFERENCES message_templates(template_id)
);

CREATE TABLE send_attempts (
  send_id TEXT NOT NULL,
  message_id TEXT NOT NULL,
  customer_id TEXT NOT NULL,
  channel TEXT NOT NULL,
  attempt_ts TEXT NOT NULL,
  status TEXT NOT NULL,
  consent_id TEXT,
  sends_last_24h INTEGER NOT NULL,
  sends_last_7d INTEGER NOT NULL,
  delivery_status TEXT,
  PRIMARY KEY (send_id),
  FOREIGN KEY (message_id) REFERENCES scheduled_messages(message_id),
  FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
  FOREIGN KEY (consent_id) REFERENCES consents(consent_id)
);

CREATE TABLE send_events (
  event_id TEXT NOT NULL,
  send_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  event_ts TEXT NOT NULL,
  PRIMARY KEY (event_id),
  FOREIGN KEY (send_id) REFERENCES send_attempts(send_id)
);

CREATE TABLE orders (
  order_id TEXT NOT NULL,
  customer_id TEXT,
  cart_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  order_ts TEXT NOT NULL,
  subtotal NUMERIC(12,2) NOT NULL,
  discount_amount NUMERIC(12,2) NOT NULL,
  shipping_fee NUMERIC(12,2) NOT NULL,
  order_total NUMERIC(12,2) NOT NULL,
  promo_code TEXT,
  PRIMARY KEY (order_id),
  FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
  FOREIGN KEY (cart_id) REFERENCES carts(cart_id),
  FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE TABLE attributions (
  attribution_id TEXT NOT NULL,
  order_id TEXT NOT NULL,
  send_id TEXT NOT NULL,
  message_id TEXT NOT NULL,
  campaign_id TEXT NOT NULL,
  model TEXT NOT NULL,
  window_days INTEGER NOT NULL,
  click_ts TEXT NOT NULL,
  order_ts TEXT NOT NULL,
  lag_hours NUMERIC(12,2) NOT NULL,
  attributed_revenue NUMERIC(12,2) NOT NULL,
  PRIMARY KEY (attribution_id),
  FOREIGN KEY (order_id) REFERENCES orders(order_id),
  FOREIGN KEY (send_id) REFERENCES send_attempts(send_id),
  FOREIGN KEY (message_id) REFERENCES scheduled_messages(message_id),
  FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);
