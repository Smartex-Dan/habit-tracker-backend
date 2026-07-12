from django.urls import path

from .views import (
    HabitListCreateView,
    HabitHistoryView,
    CheckInCreateView,
    CheckInDeleteView,
    ConsistencyScoreView,
    DashboardChartsView,
)

urlpatterns = [
    path("habits", HabitListCreateView.as_view(), name="habit-list-create"),
    path("habits/<uuid:habit_id>/history", HabitHistoryView.as_view(), name="habit-history"),
    path("check-ins", CheckInCreateView.as_view(), name="check-in-create"),
    path("check-ins/<uuid:check_in_id>", CheckInDeleteView.as_view(), name="check-in-delete"),
    path("consistency-score", ConsistencyScoreView.as_view(), name="consistency-score"),
    path("dashboard/charts", DashboardChartsView.as_view(), name="dashboard-charts"),
]
