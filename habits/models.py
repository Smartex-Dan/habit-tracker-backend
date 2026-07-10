# Intentionally empty.
#
# Habit and check-in data lives entirely in Supabase Postgres and is
# accessed via supabase-py (see supabase_client.py). Django does not own
# this data or manage migrations for it — Supabase's SQL Editor / dashboard
# is the source of truth for the `habits` and `check_ins` table schemas.
