"""
Consistency Score calculation.

Kept isolated from views/services the same way streak math is — a pure
function, easy to test, that doesn't care how the dates got fetched.

Design decisions (worth remembering for the case study / interview):

1. Habits younger than GRACE_PERIOD_DAYS are excluded from the score
   entirely (not scored as 0, not skipped silently) — a brand new habit
   with zero check-ins shouldn't tank a user's score on day one, and it
   shouldn't inflate it either. It just doesn't count yet.

2. "Expected check-ins" for a habit is calculated from whichever is later:
   the start of the current month, or the habit's own created_at date.
   A habit created mid-month is graded on the days it could have been
   checked in, not the full month.

3. If a user has zero eligible habits (all too new, or none created yet),
   the score is 0 with a "Just Getting Started" label rather than raising
   an error or returning None — the dashboard always has something to show.
"""

from datetime import date, timedelta

GRACE_PERIOD_DAYS = 3


def calculate_consistency_score(
    habits: list[dict],
    check_ins_by_habit: dict[str, list[date]],
    today: date | None = None,
) -> dict:
    """
    Args:
        habits: list of dicts, each with at least "id" and "created_at"
                 (created_at as a date object).
        check_ins_by_habit: {habit_id: [completed dates this month]}.
        today: injectable for testing, defaults to date.today().

    Returns:
        {
            "score": int,               # 0-100
            "label": str,                # "Excellent" | "Good" | "Fair" |
                                          # "Needs Work" | "Just Getting Started"
            "completion_rate": int,      # 0-100
            "eligible_habit_count": int,
            "summary": str,
        }
    """
    if today is None:
        today = date.today()

    eligible = [
        h for h in habits
        if (today - h["created_at"]).days >= GRACE_PERIOD_DAYS
    ]

    if not eligible:
        return {
            "score": 0,
            "label": "Just Getting Started",
            "completion_rate": 0,
            "eligible_habit_count": 0,
            "summary": "Keep checking in — your score unlocks once a habit has 3+ days of history.",
        }

    month_start = today.replace(day=1)

    total_expected = 0
    total_completed = 0
    streak_strengths = []
    all_eligible_dates: list[date] = []

    for h in eligible:
        effective_start = max(h["created_at"], month_start)
        expected_days = max((today - effective_start).days + 1, 1)
        total_expected += expected_days

        dates = check_ins_by_habit.get(h["id"], [])
        total_completed += len(dates)
        all_eligible_dates.extend(dates)

        current = h.get("current_streak", 0)
        longest = h.get("longest_streak", 0)
        if longest > 0:
            streak_strengths.append(_clamp((current / longest) * 100))
        else:
            streak_strengths.append(_clamp(current * 10))

    completion_rate = _clamp((total_completed / max(total_expected, 1)) * 100)
    streak_strength = sum(streak_strengths) / len(streak_strengths)

    missed = max(total_expected - total_completed, 0)
    missed_rate = _clamp((missed / max(total_expected, 1)) * 100)
    missed_score = 100 - missed_rate

    weekly_consistency = _weekly_evenness(all_eligible_dates, len(eligible), today)

    score = round(
        completion_rate * 0.4
        + streak_strength * 0.25
        + missed_score * 0.2
        + weekly_consistency * 0.15
    )
    score = int(_clamp(score))

    return {
        "score": score,
        "label": _label(score),
        "completion_rate": round(completion_rate),
        "eligible_habit_count": len(eligible),
        "summary": f"You've completed {round(completion_rate)}% of your habits this month.",
    }


def _clamp(n: float, lo: float = 0, hi: float = 100) -> float:
    return min(hi, max(lo, n))


def _label(score: int) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Good"
    if score >= 55:
        return "Fair"
    if score >= 30:
        return "Needs Work"
    return "Just Getting Started"


def _weekly_evenness(dates: list[date], eligible_habit_count: int, today: date) -> float:
    """
    Buckets check-ins into calendar weeks of the current month (week 0 =
    days 1-7, week 1 = days 8-14, etc.) and scores how even completion was
    across weeks. Low variance (steady weeks) scores higher than high
    variance (binge-then-drop), even at the same total completion rate.
    """
    if eligible_habit_count == 0:
        return 50.0

    week_counts: dict[int, int] = {}
    for d in dates:
        week_num = (d.day - 1) // 7
        week_counts[week_num] = week_counts.get(week_num, 0) + 1

    current_week_index = (today.day - 1) // 7
    rates = []
    for w in range(current_week_index + 1):
        days_in_week = ((today.day - 1) % 7 + 1) if w == current_week_index else 7
        expected = eligible_habit_count * days_in_week
        actual = week_counts.get(w, 0)
        rates.append(_clamp((actual / expected) * 100) if expected > 0 else 0)

    if not rates:
        return 0.0

    avg = sum(rates) / len(rates)
    variance = sum((r - avg) ** 2 for r in rates) / len(rates)
    std_dev = variance ** 0.5

    return _clamp(100 - std_dev)