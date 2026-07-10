"""
Plain DRF serializers (not ModelSerializers, since Django doesn't own this
data — Supabase does). These exist to validate incoming request bodies and
shape outgoing responses so they line up exactly with the TypeScript
interfaces used on the frontend:

    Habit, CheckIn, StreakSummary, HeatmapEntry
"""

from rest_framework import serializers


class HabitCreateSerializer(serializers.Serializer):
    """Validates the body of POST /api/habits."""

    title = serializers.CharField(max_length=255)
    description = serializers.CharField(
        max_length=1000, required=False, allow_blank=True, allow_null=True
    )
    color = serializers.RegexField(
        regex=r"^#(?:[0-9a-fA-F]{3}){1,2}$",
        error_messages={"invalid": "color must be a valid hex code, e.g. #8B6F4E"},
    )


class HabitSerializer(serializers.Serializer):
    """Matches the frontend's `Habit` interface."""

    id = serializers.UUIDField()
    title = serializers.CharField()
    description = serializers.CharField(allow_null=True, required=False)
    color = serializers.CharField()
    created_at = serializers.CharField()
    current_streak = serializers.IntegerField()
    longest_streak = serializers.IntegerField()


class CheckInCreateSerializer(serializers.Serializer):
    """Validates the body of POST /api/check-ins."""

    habit_id = serializers.UUIDField()
    date = serializers.DateField()


class CheckInSerializer(serializers.Serializer):
    """Matches the frontend's `CheckIn` interface."""

    id = serializers.UUIDField()
    habit_id = serializers.UUIDField()
    completed_at = serializers.CharField()


class StreakSummarySerializer(serializers.Serializer):
    """Matches the frontend's `StreakSummary` interface."""

    habit_id = serializers.UUIDField()
    current_streak = serializers.IntegerField()
    longest_streak = serializers.IntegerField()
    last_completed_at = serializers.CharField(allow_null=True)


class HeatmapEntrySerializer(serializers.Serializer):
    """Matches the frontend's `HeatmapEntry` interface."""

    date = serializers.CharField()
    count = serializers.IntegerField()
