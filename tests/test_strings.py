from istek_geri_cek import strings

REASONS = ["rate_limited", "login", "network", "user", "trial_failed"]


def test_all_stop_reasons_have_messages():
    for r in REASONS:
        assert strings.STOP_MESSAGES[r].strip()


def test_export_errors_have_messages():
    for k in ["not_zip", "no_requests", "empty"]:
        assert strings.EXPORT_ERRORS[k].strip()


def test_new_messages_exist():
    assert strings.STOP_MESSAGES["unexpected"].strip()
    assert strings.BROWSER_CLOSED.strip() and strings.ALREADY_RUNNING.strip()
    assert strings.CONFIRM_FAILED.format(failed=2).strip()
