from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from gym_workouts.models import WorkoutSession, WorkoutSet

RANGES = {
    30: "Last 30 days",
    90: "Last 90 days",
    180: "Last 6 months",
    365: "Last year",
    0: "All time",
}
METRICS = {
    "weight": {"label": "Top-set weight", "unit": "lb"},
    "reps": {"label": "Total reps", "unit": "reps"},
    "volume": {"label": "Load volume", "unit": "lb × reps"},
}


def number(value):
    return format(value, ",.4f").rstrip("0").rstrip(".")


def axis_label(value):
    value = Decimal(str(value))
    if 0 < value < 1:
        return format(value.normalize(), "g")
    scale, suffix = (
        (Decimal(1000000), "m")
        if value >= 1000000
        else (Decimal(1000), "k")
        if value >= 1000
        else (Decimal(1), "")
    )
    return format(value / scale, ".1f").rstrip("0").rstrip(".") + suffix


def exercise_chart(points, metric):
    if not points:
        return None
    first = date.fromisoformat(points[0]["date"])
    span = (date.fromisoformat(points[-1]["date"]) - first).days
    maximum = max(point[metric] for point in points) or Decimal(1)
    plotted = []
    for point in points:
        offset = (date.fromisoformat(point["date"]) - first).days
        x = round(72 + offset / span * 448, 2) if span else 296
        y = round(226 - float(point[metric] / maximum) * 206, 2)
        plotted.append(point | {"x": x, "y": y, "display": number(point[metric])})
    path = " ".join(
        f"{'M' if index == 0 else 'L'} {p['x']} {p['y']}" for index, p in enumerate(plotted)
    )
    return {
        "points": plotted,
        "path": path,
        "area": f"{path} L {plotted[-1]['x']} 226 L {plotted[0]['x']} 226 Z",
        "ticks": [
            {"y": 20 + index * 103, "label": axis_label(maximum * (2 - index) / 2)}
            for index in range(3)
        ],
        "first_date": first.strftime("%b %d, %Y"),
        "last_date": date.fromisoformat(points[-1]["date"]).strftime("%b %d, %Y"),
    }


def dashboard_data(factory, today, *, days=90, exercise_id="", metric="weight"):
    if days not in RANGES or metric not in METRICS:
        raise ValueError("Choose a dashboard date range and metric from the available options")
    end = date.fromisoformat(today)
    start = end - timedelta(days=days - 1) if days else None
    with factory() as db:
        records = list(
            db.scalars(
                select(WorkoutSession)
                .where(
                    WorkoutSession.status.in_(["completed", "review"]),
                    WorkoutSession.session_date <= today,
                )
                .options(selectinload(WorkoutSession.rows).selectinload(WorkoutSet.exercise))
                .order_by(WorkoutSession.session_date, WorkoutSession.created_at, WorkoutSession.id)
            )
        )
        available = {}
        for workout in records:
            if workout.status == "completed":
                for row in workout.rows:
                    if row.state == "performed" and row.exercise.measurement_type == "weight_reps":
                        available[row.exercise_id] = row.exercise.name.title()
        options = [
            {"id": key, "name": value}
            for key, value in sorted(available.items(), key=lambda item: item[1])
        ]
        if exercise_id and exercise_id not in available:
            raise ValueError("Choose an exercise with completed recorded sets")
        in_range = [
            workout
            for workout in records
            if start is None or workout.session_date >= start.isoformat()
        ]
        completed = [workout for workout in in_range if workout.status == "completed"]
        review_count = sum(workout.status == "review" for workout in in_range)
        series = defaultdict(list)
        total_sets = 0
        total_volume = Decimal(0)
        for workout in completed:
            by_exercise = defaultdict(list)
            for row in workout.rows:
                if (
                    row.state == "performed"
                    and row.exercise.measurement_type == "weight_reps"
                    and row.weight is not None
                    and row.reps is not None
                ):
                    by_exercise[row.exercise_id].append(row)
            for key, rows in by_exercise.items():
                top = max(rows, key=lambda row: (row.weight, row.reps))
                volume = sum((row.weight * row.reps for row in rows), Decimal(0))
                series[key].append(
                    {
                        "session_id": workout.id,
                        "date": workout.session_date,
                        "routine": workout.routine,
                        "weight": top.weight,
                        "top_reps": top.reps,
                        "reps": sum(row.reps for row in rows),
                        "volume": volume,
                        "sets": len(rows),
                        "top_display": f"{number(top.weight)} lb × {top.reps}",
                    }
                )
                total_sets += len(rows)
                total_volume += volume

        selected_id = exercise_id or next(
            (option["id"] for option in options if series.get(option["id"])),
            options[0]["id"] if options else "",
        )
        monday = end - timedelta(days=end.weekday())
        first_week = monday - timedelta(weeks=11)
        if start:
            first_week = max(first_week, start - timedelta(days=start.weekday()))
        weeks = []
        while first_week <= monday:
            count = sum(
                first_week <= date.fromisoformat(w.session_date) < first_week + timedelta(days=7)
                for w in completed
            )
            weeks.append(
                {
                    "date": first_week.isoformat(),
                    "label": first_week.strftime("%b %d"),
                    "count": count,
                }
            )
            first_week += timedelta(days=7)
        peak = max((week["count"] for week in weeks), default=0) or 1
        width = 360 / len(weeks)
        for index, week in enumerate(weeks):
            height = week["count"] / peak * 130
            week.update(
                {
                    "x": round(index * width + width * 0.22, 2),
                    "width": round(width * 0.56, 2),
                    "y": round(150 - height, 2),
                    "height": round(height, 2),
                    "center": round((index + 0.5) * width, 2),
                }
            )

        summaries = []
        for option in options:
            points = series[option["id"]]
            if points:
                difference = points[-1]["weight"] - points[0]["weight"] if len(points) > 1 else None
                summaries.append(
                    option
                    | {
                        "sessions": len(points),
                        "sets": sum(point["sets"] for point in points),
                        "latest": points[-1]["top_display"],
                        "date": points[-1]["date"],
                        "change": f"{'+' if difference > 0 else ''}{number(difference)} lb"
                        if difference is not None
                        else "—",
                    }
                )
        selected_points = series[selected_id]
        change = (
            selected_points[-1][metric] - selected_points[0][metric]
            if len(selected_points) > 1
            else None
        )
        return {
            "days": days,
            "ranges": RANGES,
            "range_label": RANGES[days],
            "metric": metric,
            "metrics": METRICS,
            "metric_label": METRICS[metric]["label"],
            "unit": METRICS[metric]["unit"],
            "exercises": options,
            "selected_id": selected_id,
            "selected_name": available.get(selected_id, "Your exercise"),
            "session_count": len(completed),
            "routine_a": sum(w.routine == "A" for w in completed),
            "routine_b": sum(w.routine == "B" for w in completed),
            "training_days": len({w.session_date for w in completed}),
            "set_count": total_sets,
            "volume_display": number(total_volume),
            "review_count": review_count,
            "weeks": weeks,
            "summaries": summaries,
            "chart": exercise_chart(selected_points, metric),
            "latest": number(selected_points[-1][metric]) if selected_points else None,
            "best": number(max(point[metric] for point in selected_points))
            if selected_points
            else None,
            "change": f"{'+' if change > 0 else ''}{number(change)}"
            if change is not None
            else None,
        }
