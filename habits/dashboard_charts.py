"""
Weekly bar chart + aggregate calendar heatmap data, combined across all of
a user's habits (as opposed to services.py's build_heatmap, which is
per-habit and binary since one habit can only be checked in once/day).

Kept as pure functions, same reasoning as services.py and consistency.py —
easy to test, and correctness never depends on how the dates were fetched.
"""

from datetime import date, timedelta


def build_aggregate_heatmap(all_check_in_dates: list[date], weeks_to_show: int = 18) -> list[dict]:
    """
    Counts check-ins per day across ALL of a user's habits, for the last
    `weeks_to_show` weeks. Unlike the per-habit heatmap (always 0 or 1),
    this can be 2, 3, 4+ if multiple habits were completed the same day.

    Returns:
        [{"date": "YYYY-MM-DD", "count": int}, ...] — every day in range,
        including zero-count days, so the frontend doesn't have to fill gaps.
    """
    today = date.today()
    total_days = weeks_to_show * 7

    counts: dict[str, int] = {}
    for d in all_check_in_dates:
        key = d.isoformat()
        counts[key] = counts.get(key, 0) + 1

    result = []
    for i in range(total_days - 1, -1, -1):
        d = today - timedelta(days=i)
        key = d.isoformat()
        result.append({"date": key, "count": counts.get(key, 0)})

    return result


def build_weekly_progress(all_check_in_dates: list[date], total_habits: int) -> list[dict]:
    """
    Last 7 days (today inclusive), for a simple bar chart of daily
    completion — one bar per day, height = habits completed that day.

    `total_habits` is the user's current habit count, used as the bar's
    max/denominator. Simplification: doesn't account for habits that
    didn't exist yet on earlier days in the window — acceptable for a
    7-day window where that's a rare edge case, revisit if it matters.

    Returns:
        [{"date": "YYYY-MM-DD", "day_label": "Mon", "completed": int,
          "total": int}, ...] — oldest to newest, 7 entries.
    """
    today = date.today()

    counts: dict[str, int] = {}
    for d in all_check_in_dates:
        key = d.isoformat()
        counts[key] = counts.get(key, 0) + 1

    result = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        key = d.isoformat()
        result.append(
            {
                "date": key,
                "day_label": d.strftime("%a"),
                "completed": counts.get(key, 0),
                "total": total_habits,
            }
        )

    return result