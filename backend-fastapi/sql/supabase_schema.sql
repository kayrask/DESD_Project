-- Run in Supabase SQL Editor
create table if not exists public.users (
  id bigint generated always as identity primary key,
  email text unique not null,
  password_hash text not null,
  role text not null check (role in ('producer','admin','customer')),
  full_name text not null,
  status text not null default 'active'
);

create table if not exists public.products (
  id bigint generated always as identity primary key,
  name text not null,
  category text not null,
  price numeric(10,2) not null,
  stock integer not null default 0,
  status text not null default 'Available',
  producer_id bigint not null references public.users(id)
);

create table if not exists public.orders (
  id bigint generated always as identity primary key,
  order_id text unique not null,
  customer_name text not null,
  delivery_date date not null,
  status text not null default 'Pending',
  producer_id bigint not null references public.users(id)
);

-- Checkout orders table
create table if not exists public.checkout_orders (
  id bigint generated always as identity primary key,
  full_name text not null,
  email text not null,
  address text not null,
  city text not null,
  postal_code text not null,
  payment_method text not null,
  status text not null default 'pending',
  created_at timestamptz not null default now()
);

-- Future-ready tables (Sprint 2/3)
create table if not exists public.producer_settlements (
  id bigint generated always as identity primary key,
  producer_id bigint not null references public.users(id),
  week_start_date date not null,
  week_end_date date not null,
  gross_amount numeric(12,2) not null default 0,
  commission_amount numeric(12,2) not null default 0,
  net_amount numeric(12,2) not null default 0,
  status text not null default 'pending',
  created_at timestamptz not null default now()
);

create table if not exists public.commission_reports (
  id bigint generated always as identity primary key,
  report_date date not null,
  total_orders integer not null default 0,
  gross_amount numeric(12,2) not null default 0,
  commission_amount numeric(12,2) not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists public.customer_favorites (
  id bigint generated always as identity primary key,
  customer_id bigint not null references public.users(id),
  producer_id bigint not null references public.users(id),
  created_at timestamptz not null default now(),
  unique(customer_id, producer_id)
);

-- Optional demo seed rows
insert into public.users (email, password_hash, role, full_name, status)
values
  ('producer@desd.local', 'Password123', 'producer', 'Producer User', 'active'),
  ('admin@desd.local', 'Password123', 'admin', 'Admin User', 'active'),
  ('customer@desd.local', 'Password123', 'customer', 'Customer User', 'active'),
  ('suspended@desd.local', 'Password123', 'customer', 'Suspended User', 'suspended')
on conflict (email) do nothing;

insert into public.products (name, category, price, stock, status, producer_id)
select
  'Heirloom Tomatoes',
  'Vegetable',
  4.50,
  52,
  'Available',
  u.id
from public.users u
where u.email = 'producer@desd.local'
  and not exists (
    select 1 from public.products p
    where p.name = 'Heirloom Tomatoes' and p.producer_id = u.id
  );

insert into public.products (name, category, price, stock, status, producer_id)
select
  'Winter Kale',
  'Leafy Greens',
  3.20,
  0,
  'Out of Stock',
  u.id
from public.users u
where u.email = 'producer@desd.local'
  and not exists (
    select 1 from public.products p
    where p.name = 'Winter Kale' and p.producer_id = u.id
  );

insert into public.orders (order_id, customer_name, delivery_date, status, producer_id)
select
  'D-1023',
  'John Smith',
  '2026-03-06',
  'Pending',
  u.id
from public.users u
where u.email = 'producer@desd.local'
  and not exists (
    select 1 from public.orders o
    where o.order_id = 'D-1023'
  );

insert into public.orders (order_id, customer_name, delivery_date, status, producer_id)
select
  'D-1019',
  'Jane Doe',
  '2026-03-05',
  'Confirmed',
  u.id
from public.users u
where u.email = 'producer@desd.local'
  and not exists (
    select 1 from public.orders o
    where o.order_id = 'D-1019'
  );

insert into public.commission_reports (report_date, total_orders, gross_amount, commission_amount)
values
  ('2026-03-01', 24, 4820.00, 482.00),
  ('2026-02-28', 19, 3110.00, 311.00)
on conflict do nothing;
