"""Security regression: WRITE intents must never reach SQL execution."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import HumanMessage

from agent.custom_tools.database_tools import (
    _run_query,
    _validate_readonly_sql,
    parse_store_query_tool_result,
)
from agent.custom_tools.db_safety_agent import (
    classify_db_access_intent,
    evaluate_read_only_guard,
    needs_semantic_db_intent_check,
)
from agent.graph import _pick_route, _synthesize_store_tool_call

WRITE_PROMPTS = [
    "Correct the customer's address.",
    "Fix the inventory.",
    "Synchronize the records.",
    "Mark order #10 as paid.",
    "Cancel order #12.",
    "Update John's city to Lahore.",
    "Deactivate discontinued products.",
    "Import this CSV into the database.",
    "Restore yesterday's backup.",
    "Apply these corrections.",
]


def _write_llm(_messages):
    return json.dumps(
        {
            "intent": "write",
            "confidence": 0.93,
            "reason": "user asked to change stored database state",
            "mutation": "update",
        }
    )


@pytest.mark.parametrize("prompt", WRITE_PROMPTS)
def test_write_prompts_need_semantic_check(prompt: str):
    assert needs_semantic_db_intent_check(prompt)


@pytest.mark.parametrize("prompt", WRITE_PROMPTS)
def test_write_prompts_classified_write_and_blocked(prompt: str):
    verdict = evaluate_read_only_guard(prompt, _write_llm)
    assert verdict.intent == "write"
    assert verdict.blocked is True
    assert verdict.confidence >= 0.4


@pytest.mark.parametrize("prompt", WRITE_PROMPTS)
def test_write_prompts_skip_sql_when_rules_or_semantic_block(prompt: str):
    """WRITE prompts must not produce a mutating tool call."""
    rules = classify_db_access_intent(prompt)
    if rules.blocked:
        message = _synthesize_store_tool_call(prompt)
        tool_calls = getattr(message, "tool_calls", None) or []
        assert tool_calls == []
        content = str(getattr(message, "content", "")).lower()
        assert (
            "read-only" in content
            or "cannot change" in content
            or "blocked" in content
            or "mutation" in content
        )
    else:
        # Paraphrases without hard keywords still blocked by semantic WRITE.
        verdict = evaluate_read_only_guard(prompt, _write_llm)
        assert verdict.blocked is True
        assert verdict.intent == "write"


def test_update_john_city_is_hard_or_soft_blocked_by_rules():
    rules = classify_db_access_intent("Update John's city to Lahore.")
    assert rules.blocked is True


def test_ast_validator_blocks_update_even_if_llm_emits_it():
    with pytest.raises(ValueError):
        _validate_readonly_sql(
            "UPDATE customers SET city = 'Lahore' WHERE full_name ILIKE '%John%'"
        )


def test_tool_returns_structured_failure_for_update():
    payload = json.loads(
        _run_query("UPDATE products SET price = 1 WHERE id = 1")
    )
    assert payload["success"] is False
    assert "select" in payload["error"].lower() or "allowed" in payload["error"].lower()
    parsed = parse_store_query_tool_result(json.dumps(payload))
    assert parsed["success"] is False


def test_read_route_still_available_for_stock_question():
    route = _pick_route(
        "which products are low in stock?",
        [HumanMessage(content="which products are low in stock?")],
    )
    assert route == "call_model"
