def check_threshold(change_pct: float, levels: list[dict]) -> dict | None:
    """Return the most severe triggered level, or None if nothing triggered.

    A level is triggered when change_pct <= level["threshold"].
    Among all triggered levels, the one with the smallest (most negative)
    threshold is considered the most severe.

    Example levels:
        [
            {"name": "提醒", "threshold": -1.0},
            {"name": "警告", "threshold": -2.0},
            {"name": "紧急", "threshold": -3.0},
        ]

    -3.2% triggers all three; the most severe is "紧急" (threshold -3.0).
    """
    if not levels:
        return None

    triggered = [lv for lv in levels if change_pct <= lv["threshold"]]
    if not triggered:
        return None

    return min(triggered, key=lambda lv: lv["threshold"])
