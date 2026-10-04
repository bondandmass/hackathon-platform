"""Weighted scoring and leaderboard ranking."""
from collections import defaultdict

WEIGHTS = {"innovation": 0.30, "technical": 0.30, "impact": 0.25, "presentation": 0.15}
CRITERIA = tuple(WEIGHTS)


def weighted_total(values: dict[str, int]) -> float:
    """Weighted score on a 1-10 scale."""
    return round(sum(values[c] * w for c, w in WEIGHTS.items()), 2)


def rank(scores) -> list[dict]:
    """Average each submission across judges, then rank by average total (ties: more judges first)."""
    grouped = defaultdict(list)
    for s in scores:
        grouped[s.submission_id].append(s)

    rows = []
    for submission_id, items in grouped.items():
        n = len(items)
        row = {
            "submission_id": submission_id,
            "team_id": items[0].team_id,
            "title": items[0].submission_title,
            "judges": n,
            "average_total": round(sum(i.total for i in items) / n, 2),
        }
        for c in CRITERIA:
            row[c] = round(sum(getattr(i, c) for i in items) / n, 2)
        rows.append(row)

    rows.sort(key=lambda r: (-r["average_total"], -r["judges"], r["submission_id"]))
    for position, row in enumerate(rows, start=1):
        row["rank"] = position
    return rows
