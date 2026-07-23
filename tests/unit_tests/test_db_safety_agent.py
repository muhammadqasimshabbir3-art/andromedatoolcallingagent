"""Unit tests for the dual-layer read-only database safety agent."""

from langchain_core.messages import HumanMessage

from agent.custom_tools.db_safety_agent import (
    classify_db_access_intent,
    evaluate_read_only_guard,
    is_db_mutation_request,
    needs_ai_db_intent_check,
)
from agent.graph import _pick_route


def test_blocks_hard_update_and_delete_intents():
    assert is_db_mutation_request("update the price of Wireless Earbuds Pro to 5000")
    assert is_db_mutation_request("delete product Discontinued Flip Phone from database")
    assert is_db_mutation_request("insert into products a new charger")
    assert is_db_mutation_request("set stock to 0 for all earbuds")
    assert is_db_mutation_request("erase customer records from neon")
    assert is_db_mutation_request("wipe products table")
    assert is_db_mutation_request("drop table orders")
    assert is_db_mutation_request("purge all customers")
    assert is_db_mutation_request("alter table products add column x")
    assert is_db_mutation_request("add a product called Super Phone")
    assert is_db_mutation_request("please update anything in the database")
    assert is_db_mutation_request("can you delete from customers")
    assert is_db_mutation_request("INSERT INTO products VALUES (1)")
    assert is_db_mutation_request("UPDATE products SET price = 10")
    assert is_db_mutation_request("DELETE FROM orders")
    hard = classify_db_access_intent("insert into products a new charger")
    assert hard.blocked and hard.hard_rule
    delete = classify_db_access_intent("delete product Discontinued Flip Phone")
    assert delete.blocked and delete.hard_rule
    assert delete.mutation_kind == "delete"
    update = classify_db_access_intent("update stock for all earbuds")
    assert update.blocked and update.hard_rule
    assert update.mutation_kind == "update"


def test_add_product_is_hard_insert_block():
    soft = classify_db_access_intent("add a product called Super Phone")
    assert soft.blocked
    assert soft.hard_rule is True
    assert soft.mutation_kind == "insert"


def test_allows_read_queries():
    assert not is_db_mutation_request("which products are low in stock?")
    assert not is_db_mutation_request("total revenue by store")
    assert not is_db_mutation_request("show me customers in Karachi")


def test_customer_replace_advice_is_not_a_db_write():
    q = "I am customers i want to replace a product what should i do"
    assert not is_db_mutation_request(q)
    assert classify_db_access_intent(q).blocked is False
    assert classify_db_access_intent(q).intent == "advice"


def test_ai_can_allow_soft_false_positive():
    def fake_llm(_messages):
        return '{"intent":"advice","confidence":0.9,"reason":"customer how-to not DB write"}'

    verdict = evaluate_read_only_guard(
        "please update me on how to replace a damaged product",
        fake_llm,
    )
    # May be advice via rules already; if soft-triggered, AI allows.
    assert verdict.blocked is False


def test_ai_allows_read_when_update_word_but_list_products():
    """'update' keyword must not block a clear list/read request."""

    seen: list[str] = []

    def fake_llm(messages):
        # Capture that suspicion bulletin was attached for the LLM.
        seen.append(messages[-1]["content"])
        return (
            '{"intent":"read","confidence":0.92,'
            '"reason":"cannot update so list products instead","mutation":"none"}'
        )

    q = "okay if you can not update could you please provide me list of product"
    # Rules may flag "update"…product, but LLM says READ → allow.
    assert classify_db_access_intent(q).blocked is True  # keyword suspicious
    verdict = evaluate_read_only_guard(q, fake_llm)
    assert verdict.blocked is False
    assert verdict.intent == "read"
    assert "llm_allow_not_malicious" in verdict.reason
    assert any("RULES SUSPICION BULLETIN" in chunk for chunk in seen)


def test_keyword_hit_plus_weak_read_confidence_still_blocks():
    def fake_llm(_messages):
        return (
            '{"intent":"read","confidence":0.40,'
            '"reason":"unsure","mutation":"none"}'
        )

    q = "update the customer somehow but also list products"
    verdict = evaluate_read_only_guard(q, fake_llm)
    assert verdict.blocked is True
    assert "rules_elevated_weak_read" in verdict.reason or "ambiguous" in verdict.reason


def test_ai_confirms_real_update_still_blocks():
    def fake_llm(_messages):
        return (
            '{"intent":"write","confidence":0.95,'
            '"reason":"user wants city changed","mutation":"update"}'
        )

    verdict = evaluate_read_only_guard("Update John's city to Lahore.", fake_llm)
    assert verdict.blocked is True
    assert verdict.intent == "write"


def test_unambiguous_sql_update_always_blocks_without_needing_ai_yes():
    verdict = evaluate_read_only_guard(
        "UPDATE products SET price = 1 WHERE id = 1",
        llm_invoke=None,
    )
    assert verdict.blocked is True
    assert verdict.reason == "unambiguous_sql_mutation"


def test_ai_confirms_soft_write_block():
    def fake_llm(_messages):
        return '{"intent":"write","confidence":0.92,"reason":"user asked to cancel orders","mutation":"update"}'

    verdict = evaluate_read_only_guard("cancel all orders for downtown store", fake_llm)
    assert verdict.blocked is True
    assert verdict.layer in {"ai", "rules+ai", "rules"}


def test_hard_rule_blocks_without_needing_ai():
    verdict = evaluate_read_only_guard("insert into products values (1)", llm_invoke=None)
    assert verdict.blocked is True
    assert verdict.hard_rule is True


def test_block_message_includes_two_line_joke():
    from agent.custom_tools.db_safety_agent import (
        db_mutation_block_message,
        generate_readonly_guard_joke,
    )

    def joke_llm(_messages):
        return (
            "I'd love to UPDATE your vibes, but Neon only lets me SELECT my battles.\n"
            "Try a read question — my write wand is decorative."
        )

    joke = generate_readonly_guard_joke("update stock to 0", joke_llm)
    assert "\n" in joke
    assert len(joke.splitlines()) == 2

    verdict = evaluate_read_only_guard("insert into products values (1)", llm_invoke=None)
    msg = db_mutation_block_message("insert into products values (1)", verdict, joke=joke)
    assert "Solar says:" in msg
    assert "decorative" in msg or "SELECT" in msg


def test_pick_route_no_longer_hardcodes_reject():
    # Final reject decision is in decision_agent (rules+AI). Sync pick routes elsewhere.
    q = "Please update stock for all products in the database"
    route = _pick_route(q, [HumanMessage(content=q)])
    assert route in {"call_model", "run_business_rag"}
