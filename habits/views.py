"""
API views for the Habit Tracker.

Every view here:
  1. Requires a valid Supabase JWT (enforced globally via DRF settings).
  2. Builds a Supabase client scoped to that user's token, so Postgres RLS
     policies do the authorization work - a view never has to remember to
     filter WHERE user_id = ... by hand, because the database refuses to
     return/accept rows that don't belong to the caller.
"""

from datetime import datetime, date as date_cls

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    HabitCreateSerializer,
    CheckInCreateSerializer,
)
from .services import calculate_streaks, build_heatmap
from .supabase_client import get_supabase_client_for_request


class HabitListCreateView(APIView):
    """
    GET  /api/habits        -> list the user's habits with streak data
    POST /api/habits        -> create a new habit
    """

    def get(self, request):
        supabase = get_supabase_client_for_request(request)

        habits_res = (
            supabase.table("habits")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        habits = habits_res.data or []

        # Pull all check-ins for these habits in one query, then group
        # in Python - avoids N+1 queries against Supabase per habit.
        habit_ids = [h["id"] for h in habits]
        check_ins_by_habit: dict[str, list[date_cls]] = {hid: [] for hid in habit_ids}

        if habit_ids:
            check_ins_res = (
                supabase.table("check_ins")
                .select("habit_id, completed_at")
                .in_("habit_id", habit_ids)
                .execute()
            )
            for row in check_ins_res.data or []:
                d = datetime.strptime(row["completed_at"], "%Y-%m-%d").date()
                check_ins_by_habit.setdefault(row["habit_id"], []).append(d)

        enriched = []
        for h in habits:
            streaks = calculate_streaks(check_ins_by_habit.get(h["id"], []))
            enriched.append(
                {
                    "id": h["id"],
                    "title": h["title"],
                    "description": h.get("description"),
                    "color": h["color"],
                    "created_at": h["created_at"],
                    "current_streak": streaks["current_streak"],
                    "longest_streak": streaks["longest_streak"],
                }
            )

        return Response(enriched, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = HabitCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        supabase = get_supabase_client_for_request(request)

        payload = {
            "title": serializer.validated_data["title"],
            "description": serializer.validated_data.get("description"),
            "color": serializer.validated_data["color"],
            "user_id": request.user.id,
        }

        result = supabase.table("habits").insert(payload).execute()

        if not result.data:
            return Response(
                {"detail": "Failed to create habit."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = result.data[0]
        return Response(
            {
                "id": created["id"],
                "title": created["title"],
                "description": created.get("description"),
                "color": created["color"],
                "created_at": created["created_at"],
                "current_streak": 0,
                "longest_streak": 0,
            },
            status=status.HTTP_201_CREATED,
        )


class HabitHistoryView(APIView):
    """
    GET /api/habits/<id>/history -> check-in history + heatmap data for one habit
    """

    def get(self, request, habit_id):
        supabase = get_supabase_client_for_request(request)

        check_ins_res = (
            supabase.table("check_ins")
            .select("*")
            .eq("habit_id", habit_id)
            .order("completed_at", desc=True)
            .execute()
        )
        check_ins = check_ins_res.data or []

        dates = [
            datetime.strptime(row["completed_at"], "%Y-%m-%d").date()
            for row in check_ins
        ]

        streaks = calculate_streaks(dates)
        heatmap = build_heatmap(dates)

        return Response(
            {
                "habit_id": habit_id,
                "check_ins": check_ins,
                "current_streak": streaks["current_streak"],
                "longest_streak": streaks["longest_streak"],
                "last_completed_at": (
                    streaks["last_completed_at"].isoformat()
                    if streaks["last_completed_at"]
                    else None
                ),
                "heatmap": heatmap,
            },
            status=status.HTTP_200_OK,
        )


class CheckInCreateView(APIView):
    """
    POST /api/check-ins -> log a completion for a habit on a given date
    """

    def post(self, request):
        serializer = CheckInCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        supabase = get_supabase_client_for_request(request)

        habit_id = str(serializer.validated_data["habit_id"])
        check_date = serializer.validated_data["date"].isoformat()

        result = (
            supabase.table("check_ins")
            .insert({"habit_id": habit_id, "completed_at": check_date})
            .execute()
        )

        if not result.data:
            # Most likely cause: the unique (habit_id, completed_at)
            # constraint rejected a duplicate check-in for the same day,
            # or RLS blocked it because the habit doesn't belong to this user.
            return Response(
                {"detail": "Could not log check-in. It may already exist for this date."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(result.data[0], status=status.HTTP_201_CREATED)


class CheckInDeleteView(APIView):
    """
    DELETE /api/check-ins/<id> -> remove a completion (undo a check-in)
    """

    def delete(self, request, check_in_id):
        supabase = get_supabase_client_for_request(request)

        result = (
            supabase.table("check_ins")
            .delete()
            .eq("id", check_in_id)
            .execute()
        )

        if not result.data:
            return Response(
                {"detail": "Check-in not found or not owned by this user."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
