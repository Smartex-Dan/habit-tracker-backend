from django.urls import path

from .views import (
    DailyGoalListCreateView,
    DailyGoalCompletionView,
    DailyGoalDeleteView,
    TodoListCreateView,
    TodoDetailView,
    LongTermGoalListCreateView,
    LongTermGoalDetailView,
)

urlpatterns = [
    # Daily Goals
    path("daily-goals", DailyGoalListCreateView.as_view(), name="daily-goal-list-create"),
    path("daily-goals/<uuid:goal_id>/complete", DailyGoalCompletionView.as_view(), name="daily-goal-complete"),
    path("daily-goals/<uuid:goal_id>", DailyGoalDeleteView.as_view(), name="daily-goal-delete"),

    # To-Do List
    path("todos", TodoListCreateView.as_view(), name="todo-list-create"),
    path("todos/<uuid:todo_id>", TodoDetailView.as_view(), name="todo-detail"),

    # Long Term Goals
    path("long-term-goals", LongTermGoalListCreateView.as_view(), name="long-term-goal-list-create"),
    path("long-term-goals/<uuid:goal_id>", LongTermGoalDetailView.as_view(), name="long-term-goal-detail"),
]