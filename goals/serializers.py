"""
Plain DRF serializers (not ModelSerializers — Supabase owns this data, not
Django). These validate incoming request bodies and shape responses to
match the TypeScript types on the frontend.
"""

from rest_framework import serializers


# ---------------------------------------------------------------------------
# Daily Goals
# ---------------------------------------------------------------------------

class DailyGoalCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)


class DailyGoalSerializer(serializers.Serializer):
    """Matches the frontend's `DailyGoal` interface."""

    id = serializers.UUIDField()
    title = serializers.CharField()
    created_at = serializers.CharField()
    completed_today = serializers.BooleanField()


# ---------------------------------------------------------------------------
# To-Do List
# ---------------------------------------------------------------------------

class TodoCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(
        max_length=1000, required=False, allow_blank=True, allow_null=True
    )


class TodoUpdateSerializer(serializers.Serializer):
    """Used for PATCH — every field optional since it's a partial update."""

    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(
        max_length=1000, required=False, allow_blank=True, allow_null=True
    )
    is_completed = serializers.BooleanField(required=False)


class TodoSerializer(serializers.Serializer):
    """Matches the frontend's `Todo` interface."""

    id = serializers.UUIDField()
    title = serializers.CharField()
    description = serializers.CharField(allow_null=True, required=False)
    is_completed = serializers.BooleanField()
    created_at = serializers.CharField()
    completed_at = serializers.CharField(allow_null=True)


# ---------------------------------------------------------------------------
# Long Term Goals
# ---------------------------------------------------------------------------

class LongTermGoalCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    target_date = serializers.DateField(required=False, allow_null=True)
    progress_percent = serializers.IntegerField(
        required=False, min_value=0, max_value=100, default=0
    )


class LongTermGoalUpdateSerializer(serializers.Serializer):
    """Used for PATCH — every field optional since it's a partial update."""

    title = serializers.CharField(max_length=255, required=False)
    target_date = serializers.DateField(required=False, allow_null=True)
    progress_percent = serializers.IntegerField(
        required=False, min_value=0, max_value=100
    )


class LongTermGoalSerializer(serializers.Serializer):
    """Matches the frontend's `LongTermGoal` interface."""

    id = serializers.UUIDField()
    title = serializers.CharField()
    target_date = serializers.CharField(allow_null=True)
    progress_percent = serializers.IntegerField()
    created_at = serializers.CharField()