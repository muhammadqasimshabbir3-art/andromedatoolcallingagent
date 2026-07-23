-- Solar Store schema exported from Neon (neondb / public)
-- Auto-refreshed before each store SQL generation.
-- Manual refresh: python scripts/export_store_schema.py

-- =============================================================================
-- AGENT QUERY GUIDE (read this first when writing SQL)
-- =============================================================================
-- Tables:
--   business_chunks(id, document_id, chunk_index, content, embedding, metadata)
--   business_documents(id, doc_type, title, content, metadata, tags, created_at)
--   categories(id, name, description)
--   customers(id, full_name, email, phone, city, joined_at)
--   employees(id, full_name, role, store_id, email, hired_at, salary)
--   order_items(id, order_id, product_id, quantity, unit_price, line_total)
--   orders(id, customer_id, store_id, employee_id, order_date, status, payment_method, total_amount)
--   products(id, name, category_id, sku, price, cost, stock_qty, unit, is_active, description)
--   stores(id, name, city, address, phone)
--
-- Joins:
--   business_chunks.document_id → business_documents.id
--   employees.store_id → stores.id
--   order_items.product_id → products.id
--   order_items.order_id → orders.id
--   orders.store_id → stores.id
--   orders.employee_id → employees.id
--   orders.customer_id → customers.id
--   products.category_id → categories.id
--
-- QUERY WRITER POLICY (mandatory):
--   You may write ONLY read SQL: a single SELECT or WITH ... SELECT.
--   FORBIDDEN: UPDATE, INSERT, DELETE, ALTER, DROP, CREATE, TRUNCATE,
--   MERGE, CALL, EXECUTE, COPY, GRANT, REVOKE, BEGIN, COMMIT, ROLLBACK.
--   If the user asks to change data → do not emit SQL (REFUSE_WRITE).
-- Tips:
--   Low stock  → ORDER BY products.stock_qty ASC
--   Revenue    → SUM(orders.total_amount) / SUM(order_items.line_total)
-- =============================================================================

-- TABLE: business_chunks (28 rows)
CREATE TABLE business_chunks (
    id integer NOT NULL DEFAULT nextval('business_chunks_id_seq'::regclass),
    document_id integer NOT NULL,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    embedding jsonb NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- TABLE: business_documents (28 rows)
CREATE TABLE business_documents (
    id integer NOT NULL DEFAULT nextval('business_documents_id_seq'::regclass),
    doc_type text NOT NULL,
    title text NOT NULL,
    content text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    tags ARRAY NOT NULL DEFAULT '{}'::text[],
    created_at timestamp with time zone NOT NULL DEFAULT now()
);

-- TABLE: categories (5 rows)
CREATE TABLE categories (
    id integer NOT NULL DEFAULT nextval('categories_id_seq'::regclass),
    name text NOT NULL,
    description text NULL
);

-- TABLE: customers (8 rows)
CREATE TABLE customers (
    id integer NOT NULL DEFAULT nextval('customers_id_seq'::regclass),
    full_name text NOT NULL,
    email text NULL,
    phone text NULL,
    city text NULL,
    joined_at date NOT NULL DEFAULT CURRENT_DATE
);

-- TABLE: employees (7 rows)
CREATE TABLE employees (
    id integer NOT NULL DEFAULT nextval('employees_id_seq'::regclass),
    full_name text NOT NULL,
    role text NOT NULL,
    store_id integer NOT NULL,
    email text NULL,
    hired_at date NOT NULL,
    salary numeric NOT NULL
);

-- TABLE: order_items (22 rows)
CREATE TABLE order_items (
    id integer NOT NULL DEFAULT nextval('order_items_id_seq'::regclass),
    order_id integer NOT NULL,
    product_id integer NOT NULL,
    quantity integer NOT NULL,
    unit_price numeric NOT NULL,
    line_total numeric NOT NULL
);

-- TABLE: orders (12 rows)
CREATE TABLE orders (
    id integer NOT NULL DEFAULT nextval('orders_id_seq'::regclass),
    customer_id integer NOT NULL,
    store_id integer NOT NULL,
    employee_id integer NULL,
    order_date timestamp without time zone NOT NULL DEFAULT now(),
    status text NOT NULL,
    payment_method text NOT NULL,
    total_amount numeric NOT NULL DEFAULT 0
);

-- TABLE: products (15 rows)
CREATE TABLE products (
    id integer NOT NULL DEFAULT nextval('products_id_seq'::regclass),
    name text NOT NULL,
    category_id integer NOT NULL,
    sku text NOT NULL,
    price numeric NOT NULL,
    cost numeric NOT NULL,
    stock_qty integer NOT NULL DEFAULT 0,
    unit text NOT NULL DEFAULT 'each'::text,
    is_active boolean NOT NULL DEFAULT true,
    description text NULL
);

-- TABLE: stores (3 rows)
CREATE TABLE stores (
    id integer NOT NULL DEFAULT nextval('stores_id_seq'::regclass),
    name text NOT NULL,
    city text NOT NULL,
    address text NOT NULL,
    phone text NULL
);

-- FOREIGN KEYS
-- business_chunks.document_id → business_documents.id
-- employees.store_id → stores.id
-- order_items.product_id → products.id
-- order_items.order_id → orders.id
-- orders.store_id → stores.id
-- orders.employee_id → employees.id
-- orders.customer_id → customers.id
-- products.category_id → categories.id

