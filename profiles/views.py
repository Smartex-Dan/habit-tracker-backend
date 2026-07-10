"""
Profile picture upload endpoint.

Reuses the same auth/client machinery as the habits app (SupabaseJWTAuthentication,
get_supabase_client_for_request) so uploads are scoped to the requesting user's
own JWT — Supabase Storage policies enforce that a user can only write to
their own path, the same way Postgres RLS does for habits/check_ins.
"""

import uuid

from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from habits.supabase_client import get_supabase_client_for_request

AVATAR_BUCKET = "avatars"
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_AVATAR_SIZE_BYTES = 7 * 1024 * 1024  # MB


class AvatarUploadView(APIView):
    """
    POST /api/profile/avatar

    Accepts a single multipart file field named "file", uploads it to the
    "avatars" Supabase Storage bucket under a path scoped to the user's id
    (so two users can never collide or overwrite each other's file), and
    returns the public URL.

    REQUIRES ONE-TIME SUPABASE SETUP (dashboard, not code):
      1. Storage -> New bucket -> name it "avatars" -> make it public
         (or private + use signed URLs, if you'd rather not have public
         avatar URLs — public is simpler for an MVP).
      2. Storage -> avatars bucket -> Policies -> add a policy allowing
         authenticated users to INSERT/UPDATE objects where the path
         starts with their own auth.uid() — mirrors the RLS pattern
         already used on the habits/check_ins tables.
    """

    parser_classes = [MultiPartParser]

    def post(self, request):
        file_obj = request.FILES.get("file")

        if not file_obj:
            return Response(
                {"detail": "No file provided. Expected multipart field 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if file_obj.content_type not in ALLOWED_CONTENT_TYPES:
            return Response(
                {"detail": "Only JPEG, PNG, or WEBP images are allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if file_obj.size > MAX_AVATAR_SIZE_BYTES:
            return Response(
                {"detail": "File too large. Max size is 7MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )