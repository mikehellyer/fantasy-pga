"""Where online leagues are kept: a free Supabase project (see supabase/schema.sql).

The key here is Supabase's *publishable* (anon) key. It's meant to be shipped inside
apps, so it's fine in a public repo: it can only call the game's league functions,
and those check each manager's secret token.
"""

SUPABASE_URL = "https://tujdslymjyqczdbhrzqm.supabase.co"
SUPABASE_KEY = "sb_publishable_sae9vwe4QAr7rDzj7-8PBw_zbtwuwhf"
