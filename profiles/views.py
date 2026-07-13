"""
Replace BACKEND/profiles/views.py entirely with this — removes the
temporary debug try/except now that the bucket-name + auth-propagation
bugs are confirmed fixed.
"""

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
    "avatar" Supabase Storage bucket under a path scoped to the user's id,
    and returns the public URL.
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

        supabase = get_supabase_client_for_request(request)

        file_ext = file_obj.name.rsplit(".", 1)[-1] if "." in file_obj.name else "jpg"
        storage_path = f"{request.user.id}/{uuid.uuid4()}.{file_ext}"

        file_bytes = file_obj.read()

        supabase.storage.from_(AVATAR_BUCKET).upload(
            storage_path,
            file_bytes,
            {"content-type": file_obj.content_type, "upsert": "true"},
        )

        public_url = supabase.storage.from_(AVATAR_BUCKET).get_public_url(storage_path)

        return Response({"avatar_url": public_url}, status=status.HTTP_200_OK)