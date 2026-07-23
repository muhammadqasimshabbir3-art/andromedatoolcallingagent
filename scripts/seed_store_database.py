#!/usr/bin/env python3
"""Create and seed the Solar Store mock business database on Neon.

Usage (from repo root):
    python scripts/seed_store_database.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from agent.custom_tools.database_tools import (  # noqa: E402
    _build_database_url,
    test_connection,
)

SCHEMA_SQL = """
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS stores CASCADE;

CREATE TABLE stores (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    city        TEXT NOT NULL,
    address     TEXT NOT NULL,
    phone       TEXT
);

CREATE TABLE categories (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE products (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    sku         TEXT NOT NULL UNIQUE,
    price       NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    cost        NUMERIC(10, 2) NOT NULL CHECK (cost >= 0),
    stock_qty   INTEGER NOT NULL DEFAULT 0 CHECK (stock_qty >= 0),
    unit        TEXT NOT NULL DEFAULT 'each',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    description TEXT
);

CREATE TABLE customers (
    id          SERIAL PRIMARY KEY,
    full_name   TEXT NOT NULL,
    email       TEXT UNIQUE,
    phone       TEXT,
    city        TEXT,
    joined_at   DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE employees (
    id          SERIAL PRIMARY KEY,
    full_name   TEXT NOT NULL,
    role        TEXT NOT NULL,
    store_id    INTEGER NOT NULL REFERENCES stores(id),
    email       TEXT UNIQUE,
    hired_at    DATE NOT NULL,
    salary      NUMERIC(10, 2) NOT NULL CHECK (salary >= 0)
);

CREATE TABLE orders (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    store_id        INTEGER NOT NULL REFERENCES stores(id),
    employee_id     INTEGER REFERENCES employees(id),
    order_date      TIMESTAMP NOT NULL DEFAULT NOW(),
    status          TEXT NOT NULL CHECK (status IN
                        ('pending', 'paid', 'shipped', 'delivered', 'cancelled')),
    payment_method  TEXT NOT NULL,
    total_amount    NUMERIC(12, 2) NOT NULL DEFAULT 0
);

CREATE TABLE order_items (
    id          SERIAL PRIMARY KEY,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(id),
    quantity    INTEGER NOT NULL CHECK (quantity > 0),
    unit_price  NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),
    line_total  NUMERIC(12, 2) NOT NULL CHECK (line_total >= 0)
);
"""

SEED_SQL = """
INSERT INTO stores (id, name, city, address, phone) VALUES
(1, 'Solar Store Downtown', 'Karachi', '12 Clifton Block 5', '+92-21-111-1001'),
(2, 'Solar Store Gulshan', 'Karachi', '88 Gulshan-e-Iqbal', '+92-21-111-1002'),
(3, 'Solar Store Lahore', 'Lahore', '45 MM Alam Road', '+92-42-111-2001');

INSERT INTO categories (id, name, description) VALUES
(1, 'Electronics', 'Phones, laptops, accessories'),
(2, 'Groceries', 'Food and household staples'),
(3, 'Apparel', 'Clothing and footwear'),
(4, 'Home & Kitchen', 'Appliances and kitchenware'),
(5, 'Health & Beauty', 'Personal care and wellness');

INSERT INTO products (id, name, category_id, sku, price, cost, stock_qty, unit, is_active, description) VALUES
(1,  'Wireless Earbuds Pro',     1, 'EL-EAR-001',  7999.00,  4500.00, 120, 'each', TRUE,  'Bluetooth 5.3 earbuds with ANC'),
(2,  'USB-C Fast Charger 65W',   1, 'EL-CHG-065',  3499.00,  1800.00, 200, 'each', TRUE,  'GaN wall charger'),
(3,  '14-inch Laptop Sleeve',    1, 'EL-SLV-014',  1999.00,   900.00,  80, 'each', TRUE,  'Water-resistant neoprene sleeve'),
(4,  'Organic Basmati Rice 5kg', 2, 'GR-RIC-5KG',  2450.00,  1600.00, 300, 'bag',  TRUE,  'Premium aged basmati'),
(5,  'Extra Virgin Olive Oil 1L',2, 'GR-OIL-1L',   1899.00,  1100.00, 150, 'bottle', TRUE, 'Cold-pressed olive oil'),
(6,  'Instant Coffee 200g',      2, 'GR-COF-200',   999.00,   550.00, 220, 'jar',  TRUE,  'Medium roast instant coffee'),
(7,  'Cotton Crew T-Shirt',      3, 'AP-TSH-001',  1299.00,   500.00, 400, 'each', TRUE,  'Unisex soft cotton tee'),
(8,  'Running Shoes Pulse',      3, 'AP-SHO-100',  6499.00,  3200.00,  12, 'pair', TRUE,  'Lightweight road runners'),
(9,  'Denim Jacket Classic',     3, 'AP-JKT-010',  4599.00,  2100.00,   8, 'each', TRUE,  'Mid-wash denim jacket'),
(10, 'Nonstick Frying Pan 28cm', 4, 'HK-PAN-28',   2799.00,  1400.00, 110, 'each', TRUE,  'PFOA-free nonstick pan'),
(11, 'Electric Kettle 1.7L',     4, 'HK-KTL-17',   3299.00,  1700.00,  15, 'each', TRUE,  'Stainless steel kettle'),
(12, 'Vitamin C Serum 30ml',     5, 'HB-VIT-030',  2199.00,   950.00, 140, 'bottle', TRUE, 'Brightening face serum'),
(13, 'Herbal Shampoo 400ml',     5, 'HB-SHP-400',   899.00,   420.00, 180, 'bottle', TRUE, 'Sulfate-free shampoo'),
(14, 'Smart LED Bulb 9W',        1, 'EL-LED-009',   749.00,   320.00, 500, 'each', TRUE,  'Wi-Fi RGB bulb'),
(15, 'Discontinued Flip Phone',  1, 'EL-FLP-OLD',  4999.00,  2500.00,   5, 'each', FALSE, 'Legacy SKU kept for history');

INSERT INTO customers (id, full_name, email, phone, city, joined_at) VALUES
(1, 'Ayesha Khan',    'ayesha.khan@example.com',    '+92-300-1110001', 'Karachi', '2024-01-12'),
(2, 'Bilal Ahmed',    'bilal.ahmed@example.com',    '+92-300-1110002', 'Karachi', '2024-02-03'),
(3, 'Sara Malik',     'sara.malik@example.com',     '+92-300-1110003', 'Lahore',  '2024-03-18'),
(4, 'Omar Farooq',    'omar.farooq@example.com',    '+92-300-1110004', 'Lahore',  '2024-04-22'),
(5, 'Hina Raza',      'hina.raza@example.com',      '+92-300-1110005', 'Karachi', '2024-05-09'),
(6, 'Usman Sheikh',   'usman.sheikh@example.com',   '+92-300-1110006', 'Islamabad', '2024-06-01'),
(7, 'Fatima Noor',    'fatima.noor@example.com',    '+92-300-1110007', 'Karachi', '2024-07-15'),
(8, 'Hamza Ali',      'hamza.ali@example.com',      '+92-300-1110008', 'Lahore',  '2024-08-20');

INSERT INTO employees (id, full_name, role, store_id, email, hired_at, salary) VALUES
(1, 'Nadia Hussain',  'Store Manager', 1, 'nadia@solarstore.example',  '2022-03-01', 120000.00),
(2, 'Imran Qureshi',  'Cashier',       1, 'imran@solarstore.example',  '2023-01-15',  55000.00),
(3, 'Zara Siddiqui',  'Sales Associate',1,'zara@solarstore.example',   '2023-06-10',  60000.00),
(4, 'Ali Raza',       'Store Manager', 2, 'ali@solarstore.example',    '2021-11-20', 115000.00),
(5, 'Mehwish Tariq',  'Cashier',       2, 'mehwish@solarstore.example','2024-02-01',  52000.00),
(6, 'Kamran Iqbal',   'Store Manager', 3, 'kamran@solarstore.example', '2022-08-12', 118000.00),
(7, 'Sana Javed',     'Sales Associate',3,'sana@solarstore.example',   '2023-09-05',  58000.00);

INSERT INTO orders (id, customer_id, store_id, employee_id, order_date, status, payment_method, total_amount) VALUES
(1, 1, 1, 2, '2025-11-02 10:15:00', 'delivered', 'card',      11498.00),
(2, 2, 1, 3, '2025-11-05 14:40:00', 'delivered', 'cash',       3449.00),
(3, 3, 3, 7, '2025-11-10 11:05:00', 'shipped',   'card',      10998.00),
(4, 4, 3, 6, '2025-11-12 16:20:00', 'paid',      'jazzcash',   4599.00),
(5, 5, 2, 5, '2025-12-01 09:50:00', 'delivered', 'card',       5297.00),
(6, 6, 1, 2, '2025-12-08 13:10:00', 'delivered', 'easypaisa',  7999.00),
(7, 7, 2, 4, '2026-01-04 15:30:00', 'paid',      'card',       6098.00),
(8, 8, 3, 7, '2026-01-18 12:00:00', 'pending',   'cash',       2799.00),
(9, 1, 1, 3, '2026-02-02 17:45:00', 'delivered', 'card',       2948.00),
(10,2, 2, 5, '2026-03-11 10:25:00', 'cancelled', 'card',       6499.00),
(11,3, 3, 6, '2026-04-05 11:55:00', 'delivered', 'jazzcash',   4198.00),
(12,5, 1, 2, '2026-05-20 14:05:00', 'shipped',   'card',       9997.00);

INSERT INTO order_items (order_id, product_id, quantity, unit_price, line_total) VALUES
(1, 1, 1, 7999.00, 7999.00),
(1, 2, 1, 3499.00, 3499.00),
(2, 4, 1, 2450.00, 2450.00),
(2, 6, 1,  999.00,  999.00),
(3, 8, 1, 6499.00, 6499.00),
(3, 9, 1, 4599.00, 4599.00),
(4, 9, 1, 4599.00, 4599.00),
(5, 10,1, 2799.00, 2799.00),
(5, 5, 1, 1899.00, 1899.00),
(5, 13,1,  899.00,  899.00),
(6, 1, 1, 7999.00, 7999.00),
(7, 11,1, 3299.00, 3299.00),
(7, 10,1, 2799.00, 2799.00),
(8, 10,1, 2799.00, 2799.00),
(9, 12,1, 2199.00, 2199.00),
(9, 14,1,  749.00,  749.00),
(10,8, 1, 6499.00, 6499.00),
(11,7, 2, 1299.00, 2598.00),
(11,6, 1,  999.00,  999.00),
(11,13,1,  899.00,  899.00),
(12,1, 1, 7999.00, 7999.00),
(12,3, 1, 1999.00, 1999.00);

SELECT setval(pg_get_serial_sequence('stores', 'id'), (SELECT MAX(id) FROM stores));
SELECT setval(pg_get_serial_sequence('categories', 'id'), (SELECT MAX(id) FROM categories));
SELECT setval(pg_get_serial_sequence('products', 'id'), (SELECT MAX(id) FROM products));
SELECT setval(pg_get_serial_sequence('customers', 'id'), (SELECT MAX(id) FROM customers));
SELECT setval(pg_get_serial_sequence('employees', 'id'), (SELECT MAX(id) FROM employees));
SELECT setval(pg_get_serial_sequence('orders', 'id'), (SELECT MAX(id) FROM orders));
SELECT setval(pg_get_serial_sequence('order_items', 'id'), (SELECT MAX(id) FROM order_items));
"""


def main() -> int:
    status = test_connection()
    print(status)
    if status.startswith("Connection failed"):
        print(
            "\nSet PGPASSWORD in .env to your Neon password, then re-run:\n"
            "  python scripts/seed_store_database.py"
        )
        return 1

    import psycopg

    # Unpooled host is more reliable for DDL / long seed scripts.
    url = _build_database_url(prefer_unpooled=True)
    print(f"\nSeeding via: {url.split('@')[-1]}")

    with psycopg.connect(url, connect_timeout=30, autocommit=True) as conn:
        # psycopg3 Connection.execute supports multi-statement scripts.
        conn.execute(SCHEMA_SQL)
        conn.execute(SEED_SQL)
        rows = conn.execute(
            """
            SELECT 'stores' AS table_name, COUNT(*)::int FROM stores
            UNION ALL SELECT 'categories', COUNT(*)::int FROM categories
            UNION ALL SELECT 'products', COUNT(*)::int FROM products
            UNION ALL SELECT 'customers', COUNT(*)::int FROM customers
            UNION ALL SELECT 'employees', COUNT(*)::int FROM employees
            UNION ALL SELECT 'orders', COUNT(*)::int FROM orders
            UNION ALL SELECT 'order_items', COUNT(*)::int FROM order_items
            ORDER BY 1
            """
        ).fetchall()

    print("\nSolar Store mock database seeded successfully:")
    for table_name, count in rows:
        print(f"  {table_name}: {count} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
