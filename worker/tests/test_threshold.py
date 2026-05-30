import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from threshold import check_threshold

LEVELS = [
    {"name": "提醒", "threshold": -1.0, "color": "yellow"},
    {"name": "警告", "threshold": -2.0, "color": "orange"},
    {"name": "紧急", "threshold": -3.0, "color": "red"},
]


def test_no_trigger_small_drop():
    assert check_threshold(-0.5, LEVELS) is None


def test_trigger_remind_at_boundary():
    result = check_threshold(-1.0, LEVELS)
    assert result is not None
    assert result["name"] == "提醒"


def test_trigger_warn_level():
    result = check_threshold(-2.5, LEVELS)
    assert result is not None
    assert result["name"] == "警告"


def test_trigger_urgent_level():
    result = check_threshold(-3.2, LEVELS)
    assert result is not None
    assert result["name"] == "紧急"


def test_no_trigger_positive_change():
    assert check_threshold(2.0, LEVELS) is None


def test_no_trigger_empty_levels():
    assert check_threshold(-5.0, []) is None


def test_exact_urgent_boundary():
    result = check_threshold(-3.0, LEVELS)
    assert result is not None
    assert result["name"] == "紧急"


def test_trigger_remind_only():
    result = check_threshold(-1.5, LEVELS)
    assert result is not None
    assert result["name"] == "提醒"


def test_zero_change():
    assert check_threshold(0.0, LEVELS) is None
