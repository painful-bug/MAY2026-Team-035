-- ---------------------------------------------------------------------------
-- 20260830093000_invoice_total_amount_generated.sql
--
-- Restore `public.invoice_line_items.total_amount` to the GENERATED column
-- `0021_money_on_baseline.sql` declares. Issue #54, second half. Runbook
-- section 36. Hand-applied by the owner in the Supabase SQL editor, like every
-- file here.
--
-- **What is wrong on hosted.** `0021` declares the column as
--
--   total_amount numeric(12, 2)
--     generated always as (round(quantity * unit_amount, 2)) stored
--
-- and the hosted database instead carries it as a PLAIN `not null` column --
-- `pg_attribute.attgenerated = ''` rather than `'s'`. `0021` was written with
-- that older shape in mind and `issue_invoice` still carries the defence
-- (lines 466-476: "the older hosted schema has a stored total rather than the
-- baseline's generated column; populate it only in that shape"), but the
-- defence is an `update` that runs AFTER the inserts. The insert at 0021:450
-- lists `description, quantity, unit_amount, amount, sort_order` and does not
-- list `total_amount`, so on the drifted shape every line insert violates the
-- NOT NULL and the whole RPC rolls back before the repair statement is ever
-- reached. The drift-defence block cannot fire, because nothing survives to
-- reach it.
--
-- The other half of #54 -- `money_service.create_invoice` naming the payload
-- key `"lines"` where the RPC reads `p_payload -> 'line_items'` -- is a
-- backend-only fix in this same change and needs no SQL.
--
-- **What this file does.** One guarded, idempotent repair:
--
--   * `attgenerated = 's'` (the declared shape): raise a notice and do
--     nothing. Applying this file to a correct database is a no-op, so it is
--     safe to re-run and safe on a database that has never drifted -- which
--     includes every fresh replay of this directory, where `0021` created the
--     generated column a few files earlier.
--   * `attgenerated = ''` (the drifted shape): drop the column and re-add it
--     with `0021`'s expression, verbatim.
--   * Column absent, or any other `attgenerated` value: raise, rather than
--     guess at a third shape nobody has seen.
--
-- **NO CASCADE, by census and by probe.** A `drop column` is refused by
-- Postgres when a view, materialized view, or index depends on the column, and
-- `cascade` would silently delete whatever that is. The repository was
-- enumerated first: `invoice_overview` (0021:216) and `resident_invoice_
-- overview` (0033:211) both read `invoices.total_amount` -- the invoice's own
-- column, a different table -- and NEITHER selects from `invoice_line_items`
-- at all. The one index on the table is
-- `invoice_line_items_invoice_idx (invoice_id, sort_order)` (0021:151), which
-- does not name this column. No materialized view, generated column, or column
-- default anywhere in `backend/supabase/migrations/` reads it either. Nothing
-- in this tree depends on it, so a plain `drop column` is correct.
--
-- (`issue_invoice`, `dashboard_repository` and `money_repository` all read
-- `total_amount`, and none of those is a DDL dependency: a plpgsql function
-- body is not parsed until it runs, and a PostgREST select is a query. Neither
-- blocks a `drop column`, and neither would be dropped by one.)
--
-- Because hosted has already proved it carries objects this tree never
-- declared, the census is not trusted alone: the block below PROBES
-- `pg_depend` for any view, materialized view, rule or index attached to this
-- exact column and REFUSES the repair by name if it finds one. A hosted-only
-- dependent stops the apply with a message saying what it is; it is never
-- dropped behind the owner's back.
--
-- **Data safety -- read this before applying.** Re-adding the column as
-- generated RECOMPUTES it for every existing row as
-- `round(quantity * unit_amount, 2)`. Any row whose stored `total_amount`
-- currently disagrees with its own quantity and unit amount will change value.
-- The block counts those rows and reports the count as a notice before it
-- touches anything, so the owner sees the size of the change; runbook section
-- 36's pre-check lists them individually, before the apply. The sibling
-- `amount` column is NOT touched by this file -- it keeps whatever it holds,
-- and `issue_invoice` goes on writing it. Nothing else on the table changes:
-- no row is inserted or deleted, and `quantity`, `unit_amount`, `description`,
-- `sort_order`, `invoice_id` and `community_id` are untouched.
--
-- ROLLBACK: re-declare the plain column, which is the drifted shape this file
-- repairs and not a state worth returning to:
--
--   alter table public.invoice_line_items drop column total_amount;
--   alter table public.invoice_line_items
--     add column total_amount numeric(12, 2);
--   update public.invoice_line_items
--      set total_amount = round(quantity * unit_amount, 2);
--   alter table public.invoice_line_items
--     alter column total_amount set not null;
--
-- The values are recoverable because they are computable; the rollback is
-- listed for completeness, and needing it means `issue_invoice` is broken
-- again.
-- ---------------------------------------------------------------------------

do $$
declare
  v_generated  text;
  v_attnum     smallint;
  v_dependents text;
  v_drifted    bigint;
begin
  select a.attgenerated::text, a.attnum
    into v_generated, v_attnum
    from pg_attribute a
   where a.attrelid = 'public.invoice_line_items'::regclass
     and a.attname  = 'total_amount'
     and a.attnum > 0
     and not a.attisdropped;

  if v_generated is null then
    raise exception
      'public.invoice_line_items.total_amount does not exist; 0021 has not been applied to this database';
  end if;

  if v_generated = 's' then
    raise notice
      'invoice_total_amount_generated: total_amount is already GENERATED ALWAYS AS STORED; nothing to repair.';
    return;
  end if;

  if v_generated <> '' then
    raise exception
      'public.invoice_line_items.total_amount has attgenerated = %, which is neither the declared ''s'' nor the drifted ''''; stopping rather than guessing',
      v_generated;
  end if;

  -- No blind CASCADE. Anything that would be destroyed by the drop is named
  -- and the apply stops; the repository census found none, and this is the
  -- half of the check that speaks for the hosted database.
  select coalesce(string_agg(distinct dependent.name, ', '), '')
    into v_dependents
    from (
      -- Views, materialized views and rules, via their rewrite rules.
      select c.relname::text as name
        from pg_depend d
        join pg_rewrite r on r.oid = d.objid
        join pg_class   c on c.oid = r.ev_class
       where d.classid     = 'pg_rewrite'::regclass
         and d.refclassid  = 'pg_class'::regclass
         and d.refobjid    = 'public.invoice_line_items'::regclass
         and d.refobjsubid = v_attnum
         and c.oid <> 'public.invoice_line_items'::regclass
      union
      -- Indexes, including expression indexes over this column.
      select c.relname::text
        from pg_depend d
        join pg_class c on c.oid = d.objid
       where d.classid     = 'pg_class'::regclass
         and d.refclassid  = 'pg_class'::regclass
         and d.refobjid    = 'public.invoice_line_items'::regclass
         and d.refobjsubid = v_attnum
         and c.relkind = 'i'
    ) dependent;

  if v_dependents <> '' then
    raise exception
      'invoice_line_items.total_amount is depended on by: %. Re-issue those definitions around the swap by hand; this file will not cascade them away',
      v_dependents;
  end if;

  -- What the recomputation will change, counted before it happens.
  select count(*) into v_drifted
    from public.invoice_line_items
   where total_amount is distinct from round(quantity * unit_amount, 2);

  raise notice
    'invoice_total_amount_generated: repairing the drifted plain column; % row(s) will be recomputed to round(quantity * unit_amount, 2).',
    v_drifted;

  alter table public.invoice_line_items drop column total_amount;

  alter table public.invoice_line_items
    add column total_amount numeric(12, 2)
    generated always as (round(quantity * unit_amount, 2)) stored;
end $$;


comment on column public.invoice_line_items.total_amount is
  'Generated, never written: round(quantity * unit_amount, 2). Declared by '
  '0021_money_on_baseline.sql and restored by 20260830093000 after the hosted '
  'database lost the GENERATED modifier -- issue #54, runbook section 36.';


-- ---------------------------------------------------------------------------
-- Proof, in the same transaction
--
-- The failure with no symptom here is a paste that runs the no-op branch
-- against a database that is in fact drifted -- or a drop that succeeds and an
-- add that does not. Read back rather than assumed: after this file, the
-- column exists, is generated and stored, and carries `0021`'s expression.
-- ---------------------------------------------------------------------------

do $$
declare
  v_generated  text;
  v_expression text;
begin
  select a.attgenerated::text,
         pg_get_expr(d.adbin, d.adrelid)
    into v_generated, v_expression
    from pg_attribute a
    left join pg_attrdef d
      on d.adrelid = a.attrelid and d.adnum = a.attnum
   where a.attrelid = 'public.invoice_line_items'::regclass
     and a.attname  = 'total_amount'
     and a.attnum > 0
     and not a.attisdropped;

  if v_generated is null then
    raise exception 'total_amount is gone -- the drop ran and the add did not';
  end if;

  if v_generated <> 's' then
    raise exception
      'total_amount is still not a stored generated column (attgenerated = %)',
      v_generated;
  end if;

  if position('unit_amount' in coalesce(v_expression, '')) = 0
     or position('quantity' in coalesce(v_expression, '')) = 0
     or position('round' in coalesce(v_expression, '')) = 0 then
    raise exception
      'total_amount is generated from an unexpected expression: %', v_expression;
  end if;

  raise notice
    'invoice_total_amount_generated: total_amount is generated always as % stored.',
    v_expression;
end $$;


-- Dropping and re-adding a column IS a catalogue change: without the reload
-- PostgREST keeps answering with its old picture of `invoice_line_items`.
notify pgrst, 'reload schema';
