"""
Builds a Supabase client scoped to the requesting user's access token.

We always use the SUPABASE_ANON_KEY (never the service role key) here, and
then attach the user's own JWT as the Postgrest auth token. This means every
query made through this client is subject to Row Level Security exactly as
if the frontend had called Supabase directly — Django never gets a
"god mode" bypass on the database.
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

    return client
