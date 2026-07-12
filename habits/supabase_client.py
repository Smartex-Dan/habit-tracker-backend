"""
Builds a Supabase client scoped to the requesting user's access token.

We always use the SUPABASE_ANON_KEY (never the service role key) here, and
then attach the user's own JWT to BOTH sub-clients Django actually uses:

  - postgrest (the Postgres/database queries — habits, check_ins, etc.)
  - storage   (Storage bucket uploads — avatars)

Each is a genuinely separate underlying HTTP client in supabase-py, so
authenticating one does NOT automatically authenticate the other — this
was the source of a 403 "row violates row-level security policy" on
avatar uploads even though database queries worked fine, since only
postgrest was being scoped to the user's JWT before.

Every query/upload made through this client is subject to Row Level
Security exactly as if the frontend had called Supabase directly —
Django never gets a "god mode" bypass on the database or storage.
"""

from django.conf import settings
from supabase import create_client, Client


def get_supabase_client_for_request(request) -> Client:
    """
    Returns a Supabase client authenticated as the current request's user.

    Requires `SupabaseJWTAuthentication` to have already run, which stashes
    the verified raw JWT on `request.supabase_access_token`.
    """
    access_token = getattr(request, "supabase_access_token", None)

    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)

    if access_token:
        # Scope PostgREST requests to this user so RLS policies
        # (auth.uid() = user_id, etc.) apply correctly.
        client.postgrest.auth(access_token)

        # Storage is a separate sub-client with its own HTTP session —
        # postgrest.auth() above does NOT cover it. Without this, every
        # Storage request goes out as the anon key with no user identity,
        # so any RLS policy checking auth.uid() on storage.objects fails.
        client.storage._client.headers["Authorization"] = f"Bearer {access_token}"

    return client