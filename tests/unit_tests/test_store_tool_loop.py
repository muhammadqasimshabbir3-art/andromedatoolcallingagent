"""Unit tests for store-tool loop guards in the agent graph."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.custom_tools.database_tools import needs_store_database
from agent.graph import (
    _has_successful_store_query,
    _should_force_final_answer,
    _tool_rounds_this_turn,
)
from agent.routing import pick_tool_choice


def test_needs_store_database_for_stock_question():
    assert needs_store_database("which products are low in stock?")
    assert needs_store_database("total revenue by store")
    assert needs_store_database(
        "could you analysis the profit for me for this month or what data "
        "avaible statics which help me analyze bussines profit and Decision making"
    )
    assert not needs_store_database("nearest store near me")


def test_pick_route_uses_call_model_for_store():
    from agent.graph import _pick_route

    route = _pick_route(
        "which products are low in stock?",
        [HumanMessage(content="which products are low in stock?")],
    )
    assert route == "call_model"

    profit_q = (
        "could you analysis the profit for me for this month or what data "
        "avaible statics which help me analyze bussines profit and Decision making"
    )
    assert _pick_route(profit_q, [HumanMessage(content=profit_q)]) == "call_model"


def test_pick_tool_choice_forces_store_query():
    choice = pick_tool_choice("list products low in stock")
    assert choice == {
        "type": "function",
        "function": {"name": "query_store_database"},
    }


def test_no_force_on_fresh_user_turn():
    messages = [HumanMessage(content="how many products?")]
    assert _tool_rounds_this_turn(messages) == 0
    assert _should_force_final_answer(messages) is False
    assert _has_successful_store_query(messages) is False


def test_force_after_successful_store_query():
    messages = [
        HumanMessage(content="low stock products?"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "query_store_database",
                    "args": {"sql": "SELECT 1"},
                    "id": "1",
                }
            ],
        ),
        ToolMessage(
            content="SQL:\nSELECT 1\n\nRows: 1\n\nn\n-\n1",
            tool_call_id="1",
            name="query_store_database",
        ),
    ]
    assert _has_successful_store_query(messages) is True
    assert _should_force_final_answer(messages) is True


def test_allow_retry_after_failed_store_query():
    messages = [
        HumanMessage(content="low stock products?"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "query_store_database",
                    "args": {"sql": "SELECT bad"},
                    "id": "1",
                }
            ],
        ),
        ToolMessage(
            content="Database query error: syntax error",
            tool_call_id="1",
            name="query_store_database",
        ),
    ]
    assert _should_force_final_answer(messages) is False


def test_extract_sql_from_markdown_fence():
    from agent.custom_tools.database_tools import extract_sql_from_text

    raw = "```sql\nSELECT name, stock_qty FROM products ORDER BY stock_qty ASC LIMIT 5\n```"
    assert extract_sql_from_text(raw).lower().startswith("select")


def test_answer_store_question_uses_query_rows_only():
    from agent.custom_tools.database_tools import answer_store_question_sync

    calls = {"n": 0}

    def fake_llm(messages):
        calls["n"] += 1
        content = messages[0]["content"]
        if "Write the final answer" in messages[-1]["content"] or "final answer" in content.lower():
            # Should see real product names from DB in the system prompt
            assert "Discontinued Flip Phone" in content or "stock_qty" in content
            return "Lowest stock: Discontinued Flip Phone (5)."
        return "SELECT name, stock_qty FROM products ORDER BY stock_qty ASC LIMIT 5"

    # Skip live DB if unavailable — this test needs Neon.
    try:
        text = answer_store_question_sync("which products are low in stock?", fake_llm)
    except Exception as exc:  # noqa: BLE001
        if "PGPASSWORD" in str(exc) or "Connection failed" in str(exc):
            return
        raise
    assert "Discontinued Flip Phone" in text
    assert "Broken Headphones" not in text
    assert "Sources:" in text
    assert "products" in text.lower()
    assert calls["n"] >= 2


def test_format_store_sources_includes_sql_and_tables():
    from agent.custom_tools.database_tools import (
        ensure_store_sources_footer,
        format_store_sources,
    )

    tool = (
        "SQL:\nSELECT name, stock_qty FROM products ORDER BY stock_qty ASC LIMIT 5\n\n"
        "Rows: 5\n\nname | stock_qty\n----|----\nA | 1"
    )
    footer = format_store_sources(tool_content=tool)
    assert footer.startswith("Sources:")
    assert "products" in footer
    assert "Rows returned: 5" in footer
    assert "SELECT name, stock_qty FROM products" in footer

    answer = ensure_store_sources_footer("Low stock: A (1).", tool)
    assert answer.startswith("Low stock: A (1).")
    assert "Sources:" in answer
    assert answer.count("Sources:") == 1


def test_readonly_sql_allows_replace_function_but_blocks_replace_into():
    from agent.custom_tools.database_tools import _validate_readonly_sql

    ok = _validate_readonly_sql(
        "SELECT replace(name, 'old', 'new') AS cleaned FROM products LIMIT 5"
    )
    assert ok.lower().startswith("select")
    try:
        _validate_readonly_sql("WITH x AS (SELECT 1) REPLACE INTO y VALUES (1)")
        raise AssertionError("REPLACE INTO should be rejected")
    except ValueError as exc:
        assert "rejected" in str(exc).lower() or "select" in str(exc).lower()
