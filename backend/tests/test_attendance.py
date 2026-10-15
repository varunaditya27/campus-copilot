from app.tools.attendance import calculate_attendance


def test_exact_percentage():
    assert calculate_attendance(45, 60) == {"percentage": 75.0}


def test_rounds_to_two_decimals():
    assert calculate_attendance(1, 3) == {"percentage": 33.33}


def test_zero_total_is_an_error():
    assert "error" in calculate_attendance(0, 0)


def test_negative_total_is_an_error():
    assert "error" in calculate_attendance(5, -10)
