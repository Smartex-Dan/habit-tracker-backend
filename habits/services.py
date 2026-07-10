"""
Streak calculation logic.

This is deliberately isolated from the views/API layer so it's a pure,
easily testable function: given a sorted list of completion dates, compute
the current streak and longest streak. Keeping it pure also means the
correctness of streak math never depends on how the dates were fetched.

Design decisions (worth remembering for the case study / interview):

1. Dates are stored and compared as plain `date` objects (no datetimes),
   because Postgres stores `completed_at` as a DATE column. This sidesteps
   an entire class of timezone bugs — the frontend is responsible for
   converting "the user's local today" into a YYYY-MM-DD string before
   sending it, so the backend never has to guess a timezone.

2. "Current streak" tolerates the user not having checked in *today yet* —
   a streak that ended yesterday is still "current" until today ends.
   Without this, every streak would show as broken every morning before
   the user has had a chance to check in, which is punishing and wrong.

3. Missing a day resets the streak to whatever the count is from the next
   unbroken run — i.e. one missed day fully breaks the chain. Grace
   periods / "skip a day" allowances are a deliberate v2 feature, not
   implemented here, so this stays predictable for the MVP.
"""

from datetime import date, timedelta


def calculate_streaks(completed_dates: list[date], today: date | None = None) -> dict:
    """
    Given a list of dates (not necessarily sorted, may contain duplicates),
    return the current streak and longest streak.

    Returns:
        {
            "current_streak": int,
            "longest_streak": int,
            "last_completed_at": date | None,
        }
    """
    if today is None:
        today = date.today()

    if not completed_dates:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "last_completed_at": None,
        }

    unique_sorted_dates = sorted(set(completed_dates), reverse=True)
    last_completed_at = unique_sorted_dates[0]

    # --- Current streak ---
    current_streak = 0
    cursor = today

    # Allow "today" to be unfilled — start counting from today if present,
    # otherwise from yesterday, so an in-progress streak isn't shown as 0
    # before the user has checked in today.
    date_set = set(unique_sorted_dates)

    if today not in date_set:
        cursor = today - timedelta(days=1)

    while cursor in date_set:
        current_streak += 1
        cursor -= timedelta(days=1)

    # --- Longest streak ---
    longest_streak = 0
    run = 0
    previous_date = None

    # Walk oldest -> newest to build consecutive runs.
    for d in sorted(unique_sorted_dates):
        if previous_date is not None and d == previous_date + timedelta(days=1):
            run += 1
        else:
            run = 1
        longest_streak = max(longest_streak, run)
        previous_date = d

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "last_completed_at": last_completed_at,
    }


def build_heatmap(completed_dates: list[date]) -> list[dict]:
    """
    Turns a list of completion dates into heatmap entries of
    {"date": "YYYY-MM-DD", "count": 1} — count is per-habit here (always 0
    or 1 per day since a habit can only be checked in once per day, per the
    unique constraint on (habit_id, completed_at) in Postgres).

    When aggregating across multiple habits for a combined heatmap, the
    caller sums counts per date after calling this per habit.
    """
    counts: dict[str, int] = {}
    for d in completed_dates:
        key = d.isoformat()
        counts[key] = counts.get(key, 0) + 1

    return [{"date": k, "count": v} for k, v in sorted(counts.items())]
