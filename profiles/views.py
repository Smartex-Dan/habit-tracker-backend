"""
Profile picture upload endpoint.

Reuses the same auth/client machinery as the habits app (SupabaseJWTAuthentication,
get_supabase_client_for_request) so uploads are scoped to the requesting user's
own JWT — Supabase Storage policies enforce that a user can only write to
their own path, the same way Postgres RLS does for habits/check_ins.
"""

import traceback
import uuid

from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from habits.supabase_client import get_supabase_client_for_request

AVATAR_BUCKET = "avatar"
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_AVATAR_SIZE_BYTES = 7 * 1024 * 1024  # 7 MB


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

    TEMPORARY DEBUG WRAP: the upload step is wrapped in try/except so that
    if the bucket/policy setup above isn't done yet, you get the real
    Supabase error back in the response instead of a bare 500. Revert to
    letting it raise naturally once confirmed working.
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

        try:
            supabase = get_supabase_client_for_request(request)

            file_ext = file_obj.name.rsplit(".", 1)[-1] if "." in file_obj.name else "jpg"
            # Scoped under the user's own id so Storage RLS policies (path
            # starts with auth.uid()) can enforce ownership, same pattern
            # as habits/check_ins rows being scoped by user_id.
            storage_path = f"{request.user.id}/{uuid.uuid4()}.{file_ext}"

            file_bytes = file_obj.read()

            supabase.storage.from_(AVATAR_BUCKET).upload(
                storage_path,
                file_bytes,
                {"content-type": file_obj.content_type, "upsert": "true"},
            )

            public_url = supabase.storage.from_(AVATAR_BUCKET).get_public_url(storage_path)

            return Response({"avatar_url": public_url}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {
                    "detail": "DEBUG ERROR — remove this except block once fixed",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "traceback": traceback.format_exc(),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )