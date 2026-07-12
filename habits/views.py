"""
API views for the Habit Tracker.

Every view here:
  1. Requires a valid Supabase JWT (enforced globally via DRF settings).
  2. Builds a Supabase client scoped to that user's token, so Postgres RLS
     policies do the authorization work - a view never has to remember to
     filter WHERE user_id = ... by hand, because the database refuses to
     return/accept rows that don't belong to the caller.

This is the full, consolidated file — replace habits/views.py with this
entirely rather than patching pieces in, to avoid losing classes again.

NOTE: CheckInCreateView below is temporarily wrapped in a try/except for
debugging the 500 error — revert to the plain version once diagnosed
(see the comment on that class).
"""

import traceback
from datetime import datetime, date as date_cls

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    HabitCreateSerializer,
    CheckInCreateSerializer,
)
from .services import calculate_streaks, build_heatmap
from .consistency import calculate_consistency_score
from .dashboard_charts import build_aggregate_heatmap, build_weekly_progress
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
        habit_ids = [h["id"] for h in habits]

        check_ins_by_habit: dict[str, list[date_cls]] = {hid: [] for hid in habit_ids}
        today_check_in_id_by_habit: dict[str, str | None] = {hid: None for hid in habit_ids}
        today = date_cls.today()

        if habit_ids:
            check_ins_res = (
                supabase.table("check_ins")
                .select("id, habit_id, completed_at")
                .in_("habit_id", habit_ids)
                .execute()
            )
            for row in check_ins_res.data or []:
                d = datetime.strptime(row["completed_at"], "%Y-%m-%d").date()
                check_ins_by_habit.setdefault(row["habit_id"], []).append(d)
                if d == today:
                    today_check_in_id_by_habit[row["habit_id"]] = row["id"]

        enriched = []
        for h in habits:
            dates = check_ins_by_habit.get(h["id"], [])
            streaks = calculate_streaks(dates)
            enriched.append(
                {
                    "id": h["id"],
                    "title": h["title"],
                    "description": h.get("description"),
                    "color": h["color"],
                    "created_at": h["created_at"],
                    "reminder_time": h.get("reminder_time"),
                    "current_streak": streaks["current_streak"],
                    "longest_streak": streaks["longest_streak"],
                    "checked_in_today": today_check_in_id_by_habit.get(h["id"]) is not None,
                    "today_check_in_id": today_check_in_id_by_habit.get(h["id"]),
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
        reminder_time = serializer.validated_data.get("reminder_time")
        if reminder_time is not None:
            payload["reminder_time"] = reminder_time.isoformat()

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
                "reminder_time": created.get("reminder_time"),
                "current_streak": 0,
                "longest_streak": 0,
                "checked_in_today": False,
                "today_check_in_id": None,
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

    TEMPORARY DEBUG VERSION — wrapped in try/except to surface the real
    exception in the API response instead of a bare 500. Revert to a
    plain (no try/except) version once the bug is found — don't leave
    raw exception text exposed to the client long-term.
    """

    def post(self, request):
        try:
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
                return Response(
                    {"detail": "Could not log check-in. It may already exist for this date."},
                    status=status.HTTP_409_CONFLICT,
                )

            return Response(result.data[0], status=status.HTTP_201_CREATED)

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


class ConsistencyScoreView(APIView):
    """
    GET /api/consistency-score -> composite 0-100 score for the current user
    """

    def get(self, request):
        supabase = get_supabase_client_for_request(request)

        habits_res = supabase.table("habits").select("id, created_at").execute()
        habits_raw = habits_res.data or []

        habits = [
            {
                "id": h["id"],
                "created_at": datetime.strptime(h["created_at"][:10], "%Y-%m-%d").date(),
            }
            for h in habits_raw
        ]

        if not habits:
            return Response(
                {
                    "score": 0,
                    "label": "Just Getting Started",
                    "completion_rate": 0,
                    "eligible_habit_count": 0,
                    "summary": "Add your first habit to start building your score.",
                },
                status=status.HTTP_200_OK,
            )

        today = date_cls.today()
        month_start = today.replace(day=1).isoformat()
        habit_ids = [h["id"] for h in habits]

        check_ins_res = (
            supabase.table("check_ins")
            .select("habit_id, completed_at")
            .in_("habit_id", habit_ids)
            .gte("completed_at", month_start)
            .execute()
        )

        check_ins_by_habit: dict[str, list[date_cls]] = {hid: [] for hid in habit_ids}
        for row in check_ins_res.data or []:
            d = datetime.strptime(row["completed_at"], "%Y-%m-%d").date()
            check_ins_by_habit.setdefault(row["habit_id"], []).append(d)

        all_check_ins_res = (
            supabase.table("check_ins")
            .select("habit_id, completed_at")
            .in_("habit_id", habit_ids)
            .execute()
        )
        all_dates_by_habit: dict[str, list[date_cls]] = {hid: [] for hid in habit_ids}
        for row in all_check_ins_res.data or []:
            d = datetime.strptime(row["completed_at"], "%Y-%m-%d").date()
            all_dates_by_habit.setdefault(row["habit_id"], []).append(d)

        for h in habits:
            streaks = calculate_streaks(all_dates_by_habit.get(h["id"], []))
            h["current_streak"] = streaks["current_streak"]
            h["longest_streak"] = streaks["longest_streak"]

        result = calculate_consistency_score(habits, check_ins_by_habit, today)

        return Response(result, status=status.HTTP_200_OK)


class DashboardChartsView(APIView):
    """
    GET /api/dashboard/charts -> weekly bar chart + calendar heatmap data,
    aggregated across all of the user's habits.
    """

    def get(self, request):
        supabase = get_supabase_client_for_request(request)

        habits_res = supabase.table("habits").select("id").execute()
        habit_ids = [h["id"] for h in (habits_res.data or [])]
        total_habits = len(habit_ids)

        all_dates = []
        if habit_ids:
            check_ins_res = (
                supabase.table("check_ins")
                .select("completed_at")
                .in_("habit_id", habit_ids)
                .execute()
            )
            all_dates = [
                datetime.strptime(row["completed_at"], "%Y-%m-%d").date()
                for row in (check_ins_res.data or [])
            ]

        return Response(
            {
                "heatmap": build_aggregate_heatmap(all_dates),
                "weekly": build_weekly_progress(all_dates, total_habits),
            }
        )