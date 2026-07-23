"""AST read-only SQL validator unit tests."""

import pytest

from agent.custom_tools.sql_readonly_validator import validate_readonly_sql_ast


def test_allows_simple_select():
    sql = validate_readonly_sql_ast("SELECT id, name FROM products WHERE stock_qty < 10")
    assert sql.lower().startswith("select")


def test_allows_with_select():
    sql = validate_readonly_sql_ast(
        "WITH low AS (SELECT * FROM products WHERE stock_qty < 5) "
        "SELECT * FROM low LIMIT 10"
    )
    assert "with" in sql.lower()


@pytest.mark.parametrize(
    "bad_sql",
    [
        "UPDATE customers SET city = 'Lahore' WHERE id = 1",
        "INSERT INTO customers (full_name) VALUES ('Ada')",
        "DELETE FROM orders WHERE id = 12",
        "ALTER TABLE products ADD COLUMN x INT",
        "DROP TABLE products",
        "TRUNCATE TABLE orders",
        "CREATE TABLE hack (id INT)",
        "MERGE INTO products t USING products s ON t.id = s.id WHEN MATCHED THEN UPDATE SET price = 1",
        "BEGIN; SELECT 1; COMMIT",
        "SELECT 1; DELETE FROM orders",
        "GRANT SELECT ON products TO public",
        "COPY products TO STDOUT",
    ],
)
def test_rejects_mutating_sql(bad_sql: str):
    with pytest.raises(ValueError):
        validate_readonly_sql_ast(bad_sql)


def test_rejects_empty_and_unparseable():
    with pytest.raises(ValueError):
        validate_readonly_sql_ast("")
    with pytest.raises(ValueError):
        validate_readonly_sql_ast("NOT VALID SQL ;;;@@@")
