# Why Our Agent Only Reads the Database

Even if our database connection *could* run updates or deletes, **this chat agent is built so users cannot change store data.** They can only look things up — like a clerk who may read the inventory book, not rewrite it.

---

## What users can and cannot do

**Allowed:** ask about stock, revenue, orders, customers; get policy answers from documents.

**Not allowed:** update, delete, or insert rows; change prices, stock, addresses, or order status; drop tables; “fix / sync / import” data through chat.

A change request gets a clear (friendly) refusal — never a successful write.

---

## Layers in order (how a request is handled)

### Layer 1 — Keyword scan (raise suspicion)

We first scan the user’s words for mutation language: update, delete, insert, drop, sync, import, and similar.

When those keywords match:

- Suspicion is **raised**
- The next step gets a warning: “this may be a forbidden change”
- The system looks more carefully before allowing anything

Keywords are a **heads-up**, not a blunt auto-block for every use of “update.”  
Obvious raw change SQL (`UPDATE … SET`, `DELETE FROM …`) is blocked right here.

### Layer 2 — Intent check (read vs write)

Next we decide what the user **means**:

**Write (blocked):** “Correct the customer’s address”, “Mark order #10 as paid”, “Delete all products”, “Import this CSV”.

**Read (allowed):** “Which products are low in stock?”, “Show orders for Ayesha”, or “If you cannot update, just list the products” — the word “update” may appear, but the real ask is to **list**.

If intent is write → we **refuse** (joke + clear message). No SQL is written. Stop.

If intent is read → continue to Layer 3.

### Layer 3 — Query agent writes only read queries

Only after a read is allowed does the query agent run. Its instructions are:

- Invent **only** read queries (show / list / total / find)
- Never invent update, delete, insert, or table-change SQL
- If the ask somehow looks like a change → refuse; do not produce a write query

### Layer 4 — Extra checks before / at the database

Even with a read-looking query, we still:

| Step | In plain words |
|------|----------------|
| SQL structure check | Anything that isn’t a true read is rejected before it runs |
| Honest tool results | We answer from real query data — we don’t fake a write |
| Audit log | We record what was asked and what happened |

---

## Full path (same order)

```text
User question
  → 1) Keyword scan → raise suspicion if mutation words match
  → 2) Intent check → write? refuse / read? continue
  → 3) Query agent → write only a read query
  → 4) Extra checks → structure check, honest results, audit
  → Answer from real read results
```

A powerful password **outside** the agent (admin tools, seeds) might still change data. That is separate from chat.  
**Inside chat:** what the URL can do ≠ what the agent is allowed to do — our layers stop writes even when the connection could technically allow them.

---

## Bottom line

1. Mutation keywords **raise suspicion**.  
2. We check **intent** — writes are refused before SQL.  
3. The query agent is taught to write **only read queries**.  
4. **More checks** stop anything that still looks unsafe.  

That keeps Solar useful for looking up the store — without letting chat rewrite the database.
