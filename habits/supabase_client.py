"""
Builds a Supabase client scoped to the requesting user's access token.

We always use the SUPABASE_ANON_KEY (never the service role key) here, and
then attach the user's own JWT so requests through BOTH sub-clients Django
actually uses are properly authenticated:

  - postgrest (database queries — habits, check_ins, etc.)
  - storage   (Storage bucket uploads — avatars)

This was verified against the actual installed supabase-py==2.31.0 source
(_sync/client.py), not guessed:

  - `client.postgrest` and `client.storage` are BOTH lazily built on first
    access, and BOTH read from `self.options.headers` at that moment.
  - `client.postgrest.auth(token)` is a method on the already-constructed
    postgrest sub-client that patches its own session directly — this is
    why postgrest already worked without touching `options.headers`.
  - `storage` has no equivalent `.auth()` method. It only ever picks up
    whatever is in `client.options.headers["Authorization"]` at the moment
    it's first accessed. Since a fresh client is built per-request here
    and `.storage` hasn't been touched yet, setting `options.headers`
    below is picked up correctly the first time any view accesses
    `client.storage`.

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
        # Postgrest: unchanged, already-working path.
        client.postgrest.auth(access_token)

        # Storage: must be set on options.headers BEFORE `.storage` is
        # first accessed anywhere in the request, since that's when it
        # lazily builds its client and reads this dict.
        client.options.headers["Authorization"] = f"Bearer {access_token}"

    return client