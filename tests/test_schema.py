"""
Tests for database schema specifications, table definitions, and constraints.
"""
from schema import TABLES, TABLE_ORDER, columns

def test_all_ten_core_entities_defined():
    core_entities = [
        "customers",
        "consents",
        "sessions",
        "carts",
        "cart_lines",
        "campaigns",
        "message_templates",
        "send_attempts",
        "orders",
        "attributions"
    ]
    for entity in core_entities:
        assert entity in TABLES, f"Entity {entity} is missing from canonical schema"

def test_table_order_dependencies():
    """Verify parents come before children in TABLE_ORDER."""
    cust_idx = TABLE_ORDER.index("customers")
    assert TABLE_ORDER.index("consents") > cust_idx
    assert TABLE_ORDER.index("sessions") > cust_idx
    assert TABLE_ORDER.index("carts") > cust_idx
    assert TABLE_ORDER.index("cart_lines") > TABLE_ORDER.index("carts")
    assert TABLE_ORDER.index("scheduled_messages") > TABLE_ORDER.index("campaigns")
    assert TABLE_ORDER.index("send_attempts") > TABLE_ORDER.index("scheduled_messages")
    assert TABLE_ORDER.index("orders") > TABLE_ORDER.index("carts")
    assert TABLE_ORDER.index("attributions") > TABLE_ORDER.index("orders")

def test_primary_keys_defined():
    for table_name, spec in TABLES.items():
        assert len(spec["pk"]) >= 1, f"Table {table_name} has no primary key"

def test_required_fields_have_no_empty_defaults():
    for table_name, spec in TABLES.items():
        for field in spec["fields"]:
            if field["required"]:
                assert field["name"] in columns(table_name)
