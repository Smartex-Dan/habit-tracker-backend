"""
DRF authentication using Supabase's JWKS endpoint.

Supports modern Supabase projects using asymmetric signing keys (ES256 / RS256).
"""

import jwt

from django.conf import settings
from rest_framework import authentication, exceptions


class SupabaseUser:
    def __init__(self, user_id: str, email: str | None = None):
        self.id = user_id
        self.email = email
        self.is_authenticated = True

    def __str__(self):
        return self.email or self.id


class SupabaseJWTAuthentication(authentication.BaseAuthentication):
    _jwks_client = None

    @classmethod
    def jwks_client(cls):
        if cls._jwks_client is None:
            cls._jwks_client = jwt.PyJWKClient(
                f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
            )
        return cls._jwks_client

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ", 1)[1].strip()

        try:
            header = jwt.get_unverified_header(token)

            signing_key = self.jwks_client().get_signing_key_from_jwt(token)

            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[header["alg"]],
                audience="authenticated",
            )

            user_id = payload.get("sub")
            email = payload.get("email")

            if not user_id:
                raise exceptions.AuthenticationFailed("Token missing 'sub' claim.")

            request.supabase_access_token = token

            return (
                SupabaseUser(
                    user_id=user_id,
                    email=email,
                ),
                token,
            )

        except Exception as e:
            raise exceptions.AuthenticationFailed(str(e))
    
        