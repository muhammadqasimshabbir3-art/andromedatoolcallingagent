"""Unit tests for store database tools (no live Neon required)."""

import pytest

from agent.custom_tools.database_tools import _validate_readonly_sql


def test_allows_select():
    assert _validate_readonly_sql("SELECT * FROM products") == "SELECT * FROM products"


def test_allows_with_cte():
    sql = "WITH x AS (SELECT 1 AS n) SELECT n FROM x"
    assert _validate_readonly_sql(sql) == sql


def test_strips_trailing_semicolon():
    assert _validate_readonly_sql("SELECT 1;") == "SELECT 1"


def test_rejects_insert():
    with pytest.raises(ValueError, match="Only SELECT"):
        _validate_readonly_sql("INSERT INTO products VALUES (1)")


def test_rejects_drop_in_select_disguise():
    with pytest.raises(ValueError, match="single SQL statement"):
        _validate_readonly_sql("SELECT 1; DROP TABLE products")


def test_rejects_update_keyword():
    with pytest.raises(ValueError, match="Only SELECT"):
        _validate_readonly_sql("UPDATE products SET price = 1 WHERE id = 1")


def test_allows_update_inside_string_literal():
    sql = "SELECT * FROM products WHERE description ILIKE '%update firmware%'"
    assert _validate_readonly_sql(sql) == sql


def test_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        _validate_readonly_sql("   ")
