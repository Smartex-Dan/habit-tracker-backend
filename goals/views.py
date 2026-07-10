"""
Views for Daily Goals, To-Do List, and Long Term Goals.

Same pattern as habits/views.py: every view builds a Supabase client
scoped to the requesting user's JWT, so Postgres RLS enforces "you can
only see/modify your own rows" — no manual user_id filtering needed on
most queries (Supabase rejects/filters automatically), except on INSERT
where we still explicitly set user_id since RLS's `with check` requires it
to be present and correct in the payload.
"""

from datetime import date

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from habits.supabase_client import get_supabase_client_for_request

from .serializers import (
    DailyGoalCreateSerializer,
    TodoCreateSerializer,
    TodoUpdateSerializer,
    LongTermGoalCreateSerializer,
    LongTermGoalUpdateSerializer,
)


def today_iso():
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Daily Goals
# ---------------------------------------------------------------------------

class DailyGoalListCreateView(APIView):
    """
    GET  /api/daily-goals  -> list active daily goals + today's completion status
    POST /api/daily-goals  -> create a new daily goal
    """

    def get(self, request):
        supabase = get_supabase_client_for_request(request)

        goals_res = (
            supabase.table("daily_goals")
            .select("*")
            .eq("is_active", True)
            .order("created_at", desc=False)
            .execute()
        )
        goals = goals_res.data or []
        goal_ids = [g["id"] for g in goals]

        completed_today_ids = set()
        if goal_ids:
            completions_res = (
                supabase.table("daily_goal_completions")
                .select("daily_goal_id")
                .in_("daily_goal_id", goal_ids)
                .eq("completed_at", today_iso())
                .execute()
            )
            completed_today_ids = {row["daily_goal_id"] for row in completions_res.data or []}

        enriched = [
            {
                "id": g["id"],
                "title": g["title"],
                "created_at": g["created_at"],
                "completed_today": g["id"] in completed_today_ids,
            }
            for g in goals
        ]

        return Response(enriched, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = DailyGoalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        supabase = get_supabase_client_for_request(request)
        payload = {
            "title": serializer.validated_data["title"],
            "user_id": request.user.id,
        }
        result = supabase.table("daily_goals").insert(payload).execute()

        if not result.data:
            return Response({"detail": "Failed to create daily goal."}, status=status.HTTP_400_BAD_REQUEST)

        created = result.data[0]
        return Response(
            {
                "id": created["id"],
                "title": created["title"],
                "created_at": created["created_at"],
                "completed_today": False,
            },
            status=status.HTTP_201_CREATED,
        )


class DailyGoalCompletionView(APIView):
    """
    POST   /api/daily-goals/<id>/complete -> mark today complete
    DELETE /api/daily-goals/<id>/complete -> undo today's completion
    """

    def post(self, request, goal_id):
        supabase = get_supabase_client_for_request(request)
        result = (
            supabase.table("daily_goal_completions")
            .insert({"daily_goal_id": str(goal_id), "completed_at": today_iso()})
            .execute()
        )
        if not result.data:
            return Response(
                {"detail": "Could not mark complete. It may already be marked for today."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(result.data[0], status=status.HTTP_201_CREATED)

    def delete(self, request, goal_id):
        supabase = get_supabase_client_for_request(request)
        result = (
            supabase.table("daily_goal_completions")
            .delete()
            .eq("daily_goal_id", str(goal_id))
            .eq("completed_at", today_iso())
            .execute()
        )
        if not result.data:
            return Response({"detail": "No completion found for today."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DailyGoalDeleteView(APIView):
    """DELETE /api/daily-goals/<id> -> soft-delete (is_active = false)"""

    def delete(self, request, goal_id):
        supabase = get_supabase_client_for_request(request)
        result = (
            supabase.table("daily_goals")
            .update({"is_active": False})
            .eq("id", str(goal_id))
            .execute()
        )
        if not result.data:
            return Response({"detail": "Daily goal not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# To-Do List
# ---------------------------------------------------------------------------

class TodoListCreateView(APIView):
    """
    GET  /api/todos -> list all todos, newest first
    POST /api/todos -> create a new todo
    """

    def get(self, request):
        supabase = get_supabase_client_for_request(request)
        result = (
            supabase.table("todos")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return Response(result.data or [], status=status.HTTP_200_OK)

    def post(self, request):
        serializer = TodoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        supabase = get_supabase_client_for_request(request)
        payload = {
            "title": serializer.validated_data["title"],
            "description": serializer.validated_data.get("description"),
            "user_id": request.user.id,
        }
        result = supabase.table("todos").insert(payload).execute()

        if not result.data:
            return Response({"detail": "Failed to create todo."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result.data[0], status=status.HTTP_201_CREATED)


class TodoDetailView(APIView):
    """
    PATCH  /api/todos/<id> -> update title/description/is_completed
    DELETE /api/todos/<id> -> delete
    """

    def patch(self, request, todo_id):
        serializer = TodoUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        update_payload = dict(serializer.validated_data)

        # If marking as completed, stamp completed_at; if un-completing,
        # clear it back to null.
        if "is_completed" in update_payload:
            update_payload["completed_at"] = (
                __import__("datetime").datetime.utcnow().isoformat() if update_payload["is_completed"] else None
            )

        supabase = get_supabase_client_for_request(request)
        result = (
            supabase.table("todos")
            .update(update_payload)
            .eq("id", str(todo_id))
            .execute()
        )
        if not result.data:
            return Response({"detail": "Todo not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(result.data[0], status=status.HTTP_200_OK)

    def delete(self, request, todo_id):
        supabase = get_supabase_client_for_request(request)
        result = supabase.table("todos").delete().eq("id", str(todo_id)).execute()
        if not result.data:
            return Response({"detail": "Todo not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Long Term Goals
# ---------------------------------------------------------------------------

class LongTermGoalListCreateView(APIView):
    """
    GET  /api/long-term-goals -> list all long term goals
    POST /api/long-term-goals -> create a new one
    """

    def get(self, request):
        supabase = get_supabase_client_for_request(request)
        result = (
            supabase.table("long_term_goals")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return Response(result.data or [], status=status.HTTP_200_OK)

    def post(self, request):
        serializer = LongTermGoalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        supabase = get_supabase_client_for_request(request)
        payload = {
            "title": serializer.validated_data["title"],
            "target_date": (
                serializer.validated_data["target_date"].isoformat()
                if serializer.validated_data.get("target_date")
                else None
            ),
            "progress_percent": serializer.validated_data.get("progress_percent", 0),
            "user_id": request.user.id,
        }
        result = supabase.table("long_term_goals").insert(payload).execute()

        if not result.data:
            return Response({"detail": "Failed to create long term goal."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result.data[0], status=status.HTTP_201_CREATED)


class LongTermGoalDetailView(APIView):
    """
    PATCH  /api/long-term-goals/<id> -> update title/target_date/progress_percent
    DELETE /api/long-term-goals/<id> -> delete
    """

    def patch(self, request, goal_id):
        serializer = LongTermGoalUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        update_payload = dict(serializer.validated_data)
        if "target_date" in update_payload and update_payload["target_date"] is not None:
            update_payload["target_date"] = update_payload["target_date"].isoformat()

        supabase = get_supabase_client_for_request(request)
        result = (
            supabase.table("long_term_goals")
            .update(update_payload)
            .eq("id", str(goal_id))
            .execute()
        )
        if not result.data:
            return Response({"detail": "Long term goal not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(result.data[0], status=status.HTTP_200_OK)

    def delete(self, request, goal_id):
        supabase = get_supabase_client_for_request(request)
        result = supabase.table("long_term_goals").delete().eq("id", str(goal_id)).execute()
        if not result.data:
            return Response({"detail": "Long term goal not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)