from fantasy_pga.__main__ import self_test


def test_self_test_passes(tmp_path):
    report = tmp_path / "selftest.txt"
    assert self_test(str(report)) == 0
    text = report.read_text()
    assert "SELF-TEST PASSED" in text
    assert "played the Sony Open in Hawaii" in text
