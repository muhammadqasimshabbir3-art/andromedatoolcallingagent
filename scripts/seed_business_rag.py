#!/usr/bin/env python3
"""Create and seed semi-structured business documents for Neon RAG.

Usage (from repo root):
    python scripts/seed_business_rag.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from agent.custom_tools.business_rag_tools import _split_text  # noqa: E402
from agent.custom_tools.database_tools import (  # noqa: E402
    _build_database_url,
    test_connection,
)
from agent.embeddings import embed_documents  # noqa: E402

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS business_documents (
    id          SERIAL PRIMARY KEY,
    doc_type    TEXT NOT NULL,
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    tags        TEXT[] NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS business_chunks (
    id            SERIAL PRIMARY KEY,
    document_id   INTEGER NOT NULL REFERENCES business_documents(id) ON DELETE CASCADE,
    chunk_index   INTEGER NOT NULL,
    content       TEXT NOT NULL,
    embedding     JSONB NOT NULL,
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_business_documents_doc_type
    ON business_documents (doc_type);
CREATE INDEX IF NOT EXISTS idx_business_documents_metadata
    ON business_documents USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_business_chunks_document_id
    ON business_chunks (document_id);
"""

DOCUMENTS: list[dict] = [
    {
        "doc_type": "policy",
        "title": "Solar Store Return & Refund Policy",
        "tags": ["returns", "refunds", "customers"],
        "metadata": {
            "department": "customer_success",
            "effective_date": "2025-01-01",
            "region": "Pakistan",
            "version": "2.1",
        },
        "content": """
Solar Store Return & Refund Policy (v2.1)

Eligibility:
- Unopened electronics may be returned within 14 days of purchase with original receipt.
- Apparel and home goods may be returned within 30 days if unused and with tags attached.
- Grocery and personal-care consumables are non-returnable once opened.
- Gift purchases require the original gift receipt; refunds are issued as store credit only.

Refunds:
- Card payments are refunded to the original card within 5–7 business days.
- Cash purchases are refunded in store as store credit or cash at manager discretion.
- JazzCash / EasyPaisa refunds are issued to the same wallet within 3 business days.
- Partial refunds apply when only one item in a multi-item order is returned.

Exceptions:
- Damaged-on-arrival items: photo evidence within 48 hours qualifies for free replacement.
- Clearance / discontinued SKUs (is_active=false style items) are final sale.
- Opened software, headphones used outdoors, and hygiene-sealed beauty kits cannot be returned.
- Bulk B2B invoices follow the B2B Returns Addendum instead of this retail policy.
""".strip(),
    },
    {
        "doc_type": "policy",
        "title": "Warranty Coverage Guide",
        "tags": ["warranty", "electronics"],
        "metadata": {
            "department": "after_sales",
            "effective_date": "2025-03-15",
            "coverage_months_default": 12,
            "version": "1.4",
        },
        "content": """
Warranty Coverage Guide

Standard coverage:
- Electronics accessories (chargers, earbuds, bulbs): 6 months manufacturer warranty.
- Appliances (kettle, pans branded lines): 12 months against manufacturing defects.
- Apparel: 30-day stitching defect coverage only.
- Smart home hubs: 18 months if registered online within 14 days of purchase.

Not covered:
- Water damage, drops, unauthorized repairs, or normal wear.
- Software/firmware issues on smart bulbs after user reset misuse.
- Cosmetic scratches that do not affect function.
- Third-party accessories plugged into Solar Store devices.

Claim process:
1. Bring invoice + product to the purchase store.
2. Technician inspects within 2 business days.
3. Repair, replace, or store credit is offered based on stock availability.
4. If repair exceeds 14 days, a temporary loaner may be offered for premium SKUs.
""".strip(),
    },
    {
        "doc_type": "sop",
        "title": "In-Store Opening & Closing SOP",
        "tags": ["operations", "sop", "hours"],
        "metadata": {
            "department": "operations",
            "stores": ["Downtown", "Gulshan", "Lahore"],
            "weekday_hours": "10:00-22:00",
            "friday_hours": "14:00-22:00",
            "version": "3.0",
        },
        "content": """
In-Store Opening & Closing SOP

Opening (every day):
- Manager arrives 30 minutes before public hours.
- Weekday public hours: 10:00–22:00. Friday public hours: 14:00–22:00.
- Check cash drawer float (PKR 10,000), POS online status, and fridge temperatures.
- Verify overnight delivery crates against the packing slip before floor open.
- Confirm security cameras and panic button are online.

Closing:
- Last customer checkout by 21:50.
- Reconcile POS vs cash/card/wallet totals.
- Arm security system and log closing notes in the ops checklist app.
- Leave a one-line handoff note for the next morning shift (stockouts, VIP holds).
""".strip(),
    },
    {
        "doc_type": "faq",
        "title": "Customer Support FAQ",
        "tags": ["faq", "support", "shipping"],
        "metadata": {
            "department": "customer_success",
            "channels": ["phone", "whatsapp", "email"],
            "sla_hours": 24,
            "version": "1.8",
        },
        "content": """
Customer Support FAQ

Q: How long does delivery take in Karachi?
A: Same-city orders placed before 15:00 usually arrive next day. Outer areas: 2–3 days.

Q: Do you deliver to Lahore suburbs?
A: Yes, within 2–4 days depending on courier zones.

Q: How do I track an order?
A: Use the order ID from SMS/email on the Solar Store tracking page, or WhatsApp support.

Q: Support hours?
A: Phone/WhatsApp 10:00–20:00 daily. Email replies within 24 hours.

Q: Can I change my delivery address after placing an order?
A: Yes, within 2 hours of payment if the order status is still pending or paid (not shipped).
""".strip(),
    },
    {
        "doc_type": "product_guide",
        "title": "Electronics Product Care Guide",
        "tags": ["electronics", "care", "earbuds", "chargers"],
        "metadata": {
            "department": "merchandising",
            "category": "Electronics",
            "version": "1.2",
        },
        "content": """
Electronics Product Care Guide

Wireless Earbuds Pro:
- Charge case weekly even if unused.
- Avoid exposing buds to sweat for long workouts without drying.
- ANC mode drains battery faster; expect ~5 hours with ANC on.

USB-C Fast Charger 65W:
- Use a certified USB-C cable rated 5A for laptop charging.
- Do not cover the charger while charging phones or laptops.

Smart LED Bulb 9W:
- Requires 2.4 GHz Wi-Fi (not 5 GHz).
- Reset: power cycle 5 times to enter pairing mode.

Power Bank 20,000 mAh:
- Store at 40–60% charge if unused for more than a month.
- Do not leave in a parked car above 45°C.
""".strip(),
    },
    {
        "doc_type": "sales_brief",
        "title": "Q1 2026 Merchandising & Promo Brief",
        "tags": ["sales", "promo", "q1"],
        "metadata": {
            "department": "sales",
            "period": "2026-Q1",
            "focus_categories": ["Electronics", "Apparel"],
            "target_growth_pct": 12,
            "version": "1.0",
        },
        "content": """
Q1 2026 Merchandising & Promo Brief

Goals:
- Grow Electronics contribution margin by 12% vs Q4.
- Clear slow apparel (denim jackets, running shoes) with weekend promos.

Active promos:
- Buy earbuds + charger: 10% off the charger.
- Apparel weekend: 15% off denim jackets when stock_qty < 20.

Staff talking points:
- Prefer recommending active SKUs over discontinued flip phones.
- Upsell Vitamin C Serum with shampoo for Health & Beauty baskets.
- Mention free shipping threshold of PKR 5,000 for city deliveries.
""".strip(),
    },
    {
        "doc_type": "handbook",
        "title": "Employee Code of Conduct (Excerpt)",
        "tags": ["hr", "handbook", "conduct"],
        "metadata": {
            "department": "hr",
            "audience": "all_employees",
            "version": "4.0",
        },
        "content": """
Employee Code of Conduct (Excerpt)

Customer interactions:
- Greet within 30 seconds. Never share customer phone numbers outside the POS system.
- Discounts above 10% require store manager approval.

Workplace:
- Uniform or branded badge required on floor.
- Personal phone use on floor limited to emergencies.

Data:
- Do not export customer emails. Order data stays in Neon / POS only.
- Screenshotting customer screens or invoices for personal use is prohibited.
""".strip(),
    },
    {
        "doc_type": "policy",
        "title": "Shipping & Fulfillment Policy",
        "tags": ["shipping", "fulfillment", "courier"],
        "metadata": {
            "department": "logistics",
            "free_shipping_min_pkr": 5000,
            "version": "2.0",
        },
        "content": """
Shipping & Fulfillment Policy

Fees:
- Orders PKR 5,000+ ship free inside Karachi and Lahore city limits.
- Below PKR 5,000: flat PKR 250 courier fee.
- Islamabad / other cities: PKR 350 flat.

Fulfillment:
- Downtown and Gulshan fulfill Karachi online orders.
- Lahore store fulfills Punjab online orders.
- Out-of-stock lines may substitute only with customer consent via SMS.
- Fragile electronics ship in double-wall cartons with foam inserts.
""".strip(),
    },
    {
        "doc_type": "policy",
        "title": "Price Match & Discount Policy",
        "tags": ["pricing", "discounts", "price-match"],
        "metadata": {
            "department": "sales",
            "effective_date": "2025-06-01",
            "version": "1.1",
        },
        "content": """
Price Match & Discount Policy

Price match:
- We match identical in-stock SKUs from authorized retailers within Karachi and Lahore.
- Customer must show a live product page or dated flyer within 7 days of purchase.
- Clearance, marketplace third-party listings, and bundle deals are excluded.

Staff discounts:
- Employees receive 15% off apparel and home goods; 8% off electronics.
- Employee discounts cannot stack with weekend promos.
- Friends-and-family codes are issued by HR quarterly and expire in 30 days.

Manager overrides:
- Discounts between 10% and 20% need store manager PIN.
- Above 20% requires regional ops approval logged in the POS notes field.
""".strip(),
    },
    {
        "doc_type": "policy",
        "title": "Privacy & Customer Data Policy",
        "tags": ["privacy", "gdpr-like", "data"],
        "metadata": {
            "department": "compliance",
            "effective_date": "2025-02-01",
            "version": "1.3",
        },
        "content": """
Privacy & Customer Data Policy

What we collect:
- Name, phone, email, city, and order history required for fulfillment and support.
- WhatsApp chat logs are retained for 90 days for quality review.

What we do not do:
- We do not sell customer lists to third parties.
- We do not use customer numbers for marketing SMS without explicit opt-in.

Access & deletion:
- Customers may request a data export or deletion via support@solarstore.example.
- Deletion requests are completed within 30 days except where invoice retention law requires longer storage.
- Staff may only look up a customer when assisting that customer or investigating fraud.
""".strip(),
    },
    {
        "doc_type": "sop",
        "title": "Inventory Receiving & Cycle Count SOP",
        "tags": ["inventory", "receiving", "cycle-count"],
        "metadata": {
            "department": "operations",
            "version": "2.2",
        },
        "content": """
Inventory Receiving & Cycle Count SOP

Receiving:
1. Scan ASN barcode before opening cartons.
2. Quarantine damaged units and photograph before accepting the rest.
3. Put-away electronics in locked cages; apparel on floor racks within 4 hours.
4. Update stock_qty in POS only after put-away confirmation.

Cycle counts:
- High-velocity SKUs (earbuds, chargers, shampoo) counted weekly.
- Full category counts monthly on the first Monday.
- Variance above 2% triggers a recount and manager investigation.
- Never adjust stock to match POS without a signed variance form.
""".strip(),
    },
    {
        "doc_type": "sop",
        "title": "Cash Handling & POS Reconciliation SOP",
        "tags": ["cash", "pos", "finance"],
        "metadata": {
            "department": "finance",
            "version": "1.9",
        },
        "content": """
Cash Handling & POS Reconciliation SOP

Float:
- Opening float is PKR 10,000 split across till and safe.
- Mid-shift drops above PKR 25,000 go into the timed safe with dual signatures.

Reconciliation:
- End-of-day: match cash, card batch, JazzCash, and EasyPaisa to POS tender report.
- Shortages under PKR 500: note in ops log; shortages above PKR 500: notify regional finance same night.
- Never leave uncounted drawers overnight.

Refunds at till:
- Cash refunds require manager override and customer CNIC note (last 4 digits only).
""".strip(),
    },
    {
        "doc_type": "faq",
        "title": "Payments & Installments FAQ",
        "tags": ["faq", "payments", "installments"],
        "metadata": {
            "department": "customer_success",
            "version": "1.5",
        },
        "content": """
Payments & Installments FAQ

Q: Which payment methods do you accept?
A: Cash, Visa/Mastercard, JazzCash, EasyPaisa, and bank transfer for B2B invoices.

Q: Do you offer installments?
A: Yes on electronics above PKR 15,000 via partner BNPL for 3 or 6 months. Approval is instant in-store.

Q: Can I pay part cash and part card?
A: Yes for in-store purchases. Online checkout supports a single tender only.

Q: Why was my card declined then charged later?
A: Temporary authorization holds may appear for 1–3 days; contact your bank if the hold does not clear.
""".strip(),
    },
    {
        "doc_type": "faq",
        "title": "Loyalty Program FAQ",
        "tags": ["faq", "loyalty", "points"],
        "metadata": {
            "department": "marketing",
            "version": "1.0",
        },
        "content": """
Loyalty Program FAQ

Q: How do I earn points?
A: Earn 1 point per PKR 100 spent on active SKUs. Clearance items earn half points.

Q: How do I redeem?
A: 100 points = PKR 50 store credit. Minimum redemption is 200 points.

Q: Do points expire?
A: Points expire 12 months after the earning transaction if unused.

Q: Can I transfer points?
A: No. Points are tied to the registered phone number and cannot be merged across accounts.
""".strip(),
    },
    {
        "doc_type": "product_guide",
        "title": "Home & Kitchen Care Guide",
        "tags": ["home", "kitchen", "care"],
        "metadata": {
            "department": "merchandising",
            "category": "Home",
            "version": "1.1",
        },
        "content": """
Home & Kitchen Care Guide

Stainless kettle:
- Descale monthly with vinegar solution; rinse thoroughly.
- Do not immerse the base in water.

Non-stick pans:
- Use wooden or silicone utensils only.
- Avoid dishwasher cycles above 60°C for premium lines.

Bedding sets:
- Wash cold on gentle cycle; tumble dry low.
- Do not bleach colored duvet covers.

Fragrance diffusers:
- Place away from direct sunlight; refill when oil is below the wick mark.
""".strip(),
    },
    {
        "doc_type": "product_guide",
        "title": "Health & Beauty Product Guide",
        "tags": ["beauty", "skincare", "care"],
        "metadata": {
            "department": "merchandising",
            "category": "Health & Beauty",
            "version": "1.3",
        },
        "content": """
Health & Beauty Product Guide

Vitamin C Serum:
- Apply after cleansing, before moisturizer. Use sunscreen during the day.
- Store below 25°C; discard 3 months after opening (PAO 3M).

Herbal shampoo:
- Patch test behind the ear if you have sensitive scalp.
- Not a medical treatment for hair loss.

Sunscreen SPF 50:
- Reapply every 2 hours outdoors.
- Shake well; apply generously to face and neck.

Return note:
- Opened beauty and personal-care items are non-returnable for hygiene reasons.
""".strip(),
    },
    {
        "doc_type": "sales_brief",
        "title": "Q2 2026 Seasonal Campaign Brief",
        "tags": ["sales", "campaign", "q2", "ramadan"],
        "metadata": {
            "department": "sales",
            "period": "2026-Q2",
            "version": "1.0",
        },
        "content": """
Q2 2026 Seasonal Campaign Brief

Theme: Home refresh + electronics gifting around Eid.

Hero SKUs:
- Smart LED Bulb 9W multipacks.
- Wireless Earbuds Pro gift sets.
- Bedding bundles for Gulshan and Lahore stores.

Tactics:
- Bundle discount: bulb 3-pack at 12% off list.
- Gift-wrap free for orders above PKR 8,000 in April.
- Staff contest: top earbud attach rate wins a weekend bonus.

Avoid:
- Deep discounts on already low-margin chargers.
- Promoting discontinued flip phones in campaign creatives.
""".strip(),
    },
    {
        "doc_type": "handbook",
        "title": "Store Manager Escalation Handbook",
        "tags": ["hr", "escalation", "managers"],
        "metadata": {
            "department": "operations",
            "audience": "managers",
            "version": "2.0",
        },
        "content": """
Store Manager Escalation Handbook

Escalate immediately to regional ops when:
- Suspected fraud or card skimming.
- Workplace injury requiring medical care.
- Media or influencer requesting on-camera interviews.
- Inventory variance above 5% on a cycle count.

Customer complaints:
- Level 1: floor staff resolve within 15 minutes.
- Level 2: manager offers goodwill credit up to PKR 2,000.
- Level 3: regional customer success owns cases involving legal threats.

Documentation:
- Log every Level 2+ case in the incident tracker with order ID and outcome.
""".strip(),
    },
    {
        "doc_type": "policy",
        "title": "B2B Wholesale Terms",
        "tags": ["b2b", "wholesale", "terms"],
        "metadata": {
            "department": "sales",
            "effective_date": "2025-09-01",
            "version": "1.0",
        },
        "content": """
B2B Wholesale Terms

Eligibility:
- Registered businesses with NTN; minimum first order PKR 50,000.
- Net-15 payment terms after credit approval; otherwise prepaid.

Pricing:
- Standard wholesale is 12–18% below retail list depending on category.
- Electronics accessories: 12% off. Apparel: up to 18% off for carton quantities.

Returns:
- Defective units only within 7 days of delivery with photo evidence.
- No returns on opened consumables or custom-printed apparel.

Fulfillment:
- B2B orders ship from Downtown warehouse within 3 business days of payment clearance.
""".strip(),
    },
    {
        "doc_type": "sop",
        "title": "Online Order Fulfillment SOP",
        "tags": ["ecommerce", "fulfillment", "sop"],
        "metadata": {
            "department": "logistics",
            "version": "1.6",
        },
        "content": """
Online Order Fulfillment SOP

SLA:
- Orders paid before 15:00 same-city: pick/pack same day.
- Cross-city: pick within 24 hours; hand to courier within 36 hours.

Pick & pack:
1. Print pick list sorted by aisle.
2. Scan each unit; never substitute without SMS consent.
3. Include invoice copy and return QR card.
4. Photograph sealed parcel before handover.

Exceptions:
- Hold orders tagged VIP Gift until gift message is confirmed.
- Cancel and refund automatically if any line is OOS for more than 48 hours without customer reply.
""".strip(),
    },
    {
        "doc_type": "faq",
        "title": "Store Locations & Hours FAQ",
        "tags": ["faq", "hours", "locations"],
        "metadata": {
            "department": "customer_success",
            "version": "2.0",
        },
        "content": """
Store Locations & Hours FAQ

Q: Where are your stores?
A: Downtown Karachi, Gulshan Karachi, and Lahore Canal Road.

Q: What are weekday hours?
A: 10:00–22:00 Monday–Thursday and Saturday–Sunday.

Q: What about Friday?
A: Public hours 14:00–22:00. Staff may be on site earlier for receiving.

Q: Is parking available?
A: Downtown has paid street parking. Gulshan and Lahore have free shared lots for customers.

Q: Do all stores carry the same stock?
A: Core electronics yes; apparel assortments differ by city demand.
""".strip(),
    },
    {
        "doc_type": "policy",
        "title": "Gift Cards & Store Credit Policy",
        "tags": ["gift-cards", "store-credit"],
        "metadata": {
            "department": "finance",
            "version": "1.2",
        },
        "content": """
Gift Cards & Store Credit Policy

Gift cards:
- Sold in denominations from PKR 1,000 to PKR 25,000.
- Valid for 24 months from purchase date.
- Not redeemable for cash except where required by law.

Store credit:
- Issued for approved returns of cash purchases and goodwill gestures.
- Store credit never expires but is non-transferable.
- Combining gift card + store credit in one checkout is allowed in-store only.
""".strip(),
    },
    {
        "doc_type": "handbook",
        "title": "New Hire Onboarding Checklist",
        "tags": ["hr", "onboarding"],
        "metadata": {
            "department": "hr",
            "audience": "new_hires",
            "version": "3.1",
        },
        "content": """
New Hire Onboarding Checklist

Day 1:
- Complete HR paperwork and collect uniform/badge.
- Shadow a floor associate for greeting and POS basics.
- Read Return & Refund Policy and Code of Conduct excerpts.

Week 1:
- Complete product care modules for Electronics and Beauty.
- Practice one supervised return and one warranty intake.
- Meet the store manager for escalation paths.

Week 2:
- Solo checkout shifts with manager spot-checks.
- Enroll in loyalty pitch training; target 30% attach rate by day 14.
""".strip(),
    },
    {
        "doc_type": "sales_brief",
        "title": "Low Stock Action Playbook",
        "tags": ["sales", "inventory", "stockouts"],
        "metadata": {
            "department": "merchandising",
            "version": "1.0",
        },
        "content": """
Low Stock Action Playbook

Triggers:
- stock_qty < 10 for electronics accessories.
- stock_qty < 20 for apparel bestsellers.

Actions:
1. Hide OOS SKUs from homepage merchandising within 1 hour.
2. Offer nearest substitute with customer consent.
3. Create transfer request from sister store if they have surplus > 30 units.
4. If vendor lead time > 14 days, mark as discontinued in campaign briefs.

Customer messaging:
- Never promise restock dates unless confirmed by purchasing.
- Offer notify-me SMS when ETA is known.
""".strip(),
    },
    {
        "doc_type": "sop",
        "title": "After-Sales Warranty Desk SOP",
        "tags": ["warranty", "after-sales", "sop"],
        "metadata": {
            "department": "after_sales",
            "version": "1.4",
        },
        "content": """
After-Sales Warranty Desk SOP

Intake:
1. Verify purchase store, invoice date, and warranty window.
2. Tag the unit with a case ID and photograph serial/IMEI if present.
3. Inform customer of 2-business-day inspection SLA.

Disposition:
- Repair if parts available within 7 days.
- Replace with same SKU if stock allows.
- Issue store credit at current sell price if neither repair nor replace is possible.

Customer updates:
- WhatsApp status on day 1 and day of release.
- Never hand back a unit without a completed bench test checklist.
""".strip(),
    },
    {
        "doc_type": "policy",
        "title": "Health & Safety Store Policy",
        "tags": ["safety", "hs", "compliance"],
        "metadata": {
            "department": "operations",
            "version": "2.1",
        },
        "content": """
Health & Safety Store Policy

Fire & evacuation:
- Exits must remain unblocked; monthly fire drill logged by manager.
- Know extinguisher locations near electronics cage and kitchen demo area.

Electrical:
- Do not daisy-chain power strips for demo chargers.
- Report hot outlets or frayed demo cables immediately.

Injury response:
- First-aid kit at customer service desk.
- Serious injury: call emergency services, then regional ops.
- Complete incident form within 24 hours.
""".strip(),
    },
    {
        "doc_type": "faq",
        "title": "Corporate Gifting FAQ",
        "tags": ["faq", "gifting", "b2b"],
        "metadata": {
            "department": "sales",
            "version": "1.1",
        },
        "content": """
Corporate Gifting FAQ

Q: Can companies order bulk gift sets?
A: Yes. Minimum 20 units for curated electronics or beauty kits. Lead time 5–7 business days.

Q: Do you include branded cards?
A: Yes, one custom message card per unit at no charge for orders above PKR 100,000.

Q: Can we invoice Net-15?
A: After credit approval under B2B Wholesale Terms.

Q: Returns on gift sets?
A: Unopened sets within 7 days; opened hygiene products are final sale.
""".strip(),
    },
    {
        "doc_type": "product_guide",
        "title": "Apparel Fit & Care Guide",
        "tags": ["apparel", "fit", "care"],
        "metadata": {
            "department": "merchandising",
            "category": "Apparel",
            "version": "1.0",
        },
        "content": """
Apparel Fit & Care Guide

Denim jackets:
- Size chart uses chest measurement; when between sizes, size up for layering.
- Wash inside-out cold; hang dry to reduce fade.

Running shoes:
- True to size for most customers; wide-foot option marked on the box.
- Air dry only; do not machine wash mesh uppers.

Returns reminder:
- Apparel returns within 30 days if unused with tags attached.
- Worn-in shoes are non-returnable unless defective stitching within 30 days.
""".strip(),
    },
]


def _index_document(cur, doc_id: int, title: str, doc_type: str, content: str, metadata: dict) -> int:
    chunks = _split_text(content)
    embeddings = embed_documents(chunks)
    for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
        chunk_meta = {
            "title": title,
            "doc_type": doc_type,
            "chunk_index": index,
            "embedder": "BAAI/bge-small-en-v1.5",
            **{k: metadata[k] for k in ("department", "version") if k in metadata},
        }
        cur.execute(
            """
            INSERT INTO business_chunks (document_id, chunk_index, content, embedding, metadata)
            VALUES (%s, %s, %s, %s::jsonb, %s::jsonb)
            """,
            (doc_id, index, chunk, json.dumps(embedding), json.dumps(chunk_meta)),
        )
    return len(chunks)


def main() -> int:
    status = test_connection()
    print(status)
    if status.startswith("Connection failed"):
        return 1

    import psycopg

    url = _build_database_url(prefer_unpooled=True)
    print(f"\nSeeding business RAG via: {url.split('@')[-1]}")

    with psycopg.connect(url, connect_timeout=30, autocommit=True) as conn:
        conn.execute(SCHEMA_SQL)
        conn.execute("TRUNCATE business_chunks, business_documents RESTART IDENTITY CASCADE")

        total_chunks = 0
        with conn.cursor() as cur:
            for doc in DOCUMENTS:
                cur.execute(
                    """
                    INSERT INTO business_documents (doc_type, title, content, metadata, tags)
                    VALUES (%s, %s, %s, %s::jsonb, %s)
                    RETURNING id
                    """,
                    (
                        doc["doc_type"],
                        doc["title"],
                        doc["content"],
                        json.dumps(doc["metadata"]),
                        doc["tags"],
                    ),
                )
                doc_id = cur.fetchone()[0]
                total_chunks += _index_document(
                    cur,
                    doc_id,
                    doc["title"],
                    doc["doc_type"],
                    doc["content"],
                    doc["metadata"],
                )

            cur.execute("SELECT COUNT(*) FROM business_documents")
            doc_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM business_chunks")
            chunk_count = cur.fetchone()[0]
            cur.execute(
                """
                SELECT doc_type, COUNT(*)::int AS n
                FROM business_documents
                GROUP BY doc_type
                ORDER BY doc_type
                """
            )
            by_type = cur.fetchall()

    print("\nBusiness RAG seeded successfully:")
    print(f"  business_documents: {doc_count}")
    print(f"  business_chunks: {chunk_count} (indexed {total_chunks})")
    print("  by doc_type:")
    for doc_type, n in by_type:
        print(f"    {doc_type}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
