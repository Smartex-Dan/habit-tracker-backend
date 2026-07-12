"""
Builds a Supabase client scoped to the requesting user's access token.

We always use the SUPABASE_ANON_KEY (never the service role key) here.

Previous approach (client.postgrest.auth(token) + manually poking
client.storage._client.headers) only reliably authenticated the
postgrest sub-client — the private-attribute path for storage isn't a
stable public API and didn't propagate the token to actual outgoing
Storage requests, which is why avatar uploads kept failing RLS with a
403 even after "setting" the header.

Fixed approach: pass the Authorization header via ClientOptions at
client-CREATION time instead. supabase-py threads these global headers
into every sub-client it builds (postgrest, storage, auth) uniformly,
since they all share the same base request configuration — this is the
documented way to scope a whole client to a user's JWT, rather than
patching individual sub-clients after construction.

Every query/upload made through this client is subject to Row Level
Security exactly as if the frontend had called Supabase directly —
Django never gets a "god mode" bypass on the database or storage.
"""

from django.conf import settings
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions


def get_supabase_client_for_request(request) -> Client:
    """
    Returns a Supabase client authenticated as the current request's user.

    Requires `SupabaseJWTAuthentication` to have already run, which stashes
    the verified raw JWT on `request.supabase_access_token`.
    """
    access_token = getattr(request, "supabase_access_token", None)

    options = ClientOptions(
        headers={"Authorization": f"Bearer {access_token}"} if access_token else {}
    )

    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY, options=options)

    if access_token:
        # Kept alongside the ClientOptions header for postgrest specifically —
        # this call was already working correctly before, so it stays as a
        # belt-and-suspenders safeguard rather than being ripped out.
        client.postgrest.auth(access_token)

    return client