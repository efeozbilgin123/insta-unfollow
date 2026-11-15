import pytest

from istek_geri_cek.instagram_api import (
    ApiError, InstagramClient, LoginRequired, NetworkError, RateLimited, Status,
    classify_response, status_from_friendship,
)


class FakePage:
    """Scripted stand-in for a Playwright Page: routes by URL substring."""

    def __init__(self, routes=None, cookies=None):
        self.routes = routes or {}
        self.cookies = cookies or {}
        self.calls = []

    def evaluate(self, js, arg):
        if isinstance(arg, str):  # cookie read
            return self.cookies.get(arg)
        self.calls.append(arg)
        for key, resp in self.routes.items():
            if key in arg["url"]:
                return resp
        return {"status": 404, "body": None}


@pytest.mark.parametrize("status,body,exc", [
    (429, None, RateLimited),
    (400, {"message": "feedback_required"}, RateLimited),
    (400, {"message": "checkpoint_required"}, RateLimited),
    (401, {"message": "login_required"}, LoginRequired),
    (403, {"message": "login_required"}, LoginRequired),
    (0, None, NetworkError),
    (500, None, NetworkError),
    (400, {"message": "invalid target user"}, ApiError),
])
def test_classify_raises(status, body, exc):
    with pytest.raises(exc):
        classify_response(status, body)


def test_classify_ok():
    assert classify_response(200, {"status": "ok"}) is None


def test_status_from_friendship():
    assert status_from_friendship({"outgoing_request": True, "following": False}) is Status.PENDING
    assert status_from_friendship({"outgoing_request": False, "following": True}) is Status.FOLLOWING
    assert status_from_friendship({}) is Status.NONE


def test_lookup_not_found():
    assert InstagramClient(FakePage()).lookup("yok") == (Status.NOT_FOUND, None)


def test_lookup_null_user_is_not_found():
    page = FakePage({"web_profile_info": {"status": 200, "body": {"data": {"user": None}}}})
    assert InstagramClient(page).lookup("yok") == (Status.NOT_FOUND, None)


def test_lookup_pending():
    page = FakePage({
        "web_profile_info": {"status": 200, "body": {"data": {"user": {"id": "42"}}}},
        "friendships/show/42": {"status": 200, "body": {"outgoing_request": True, "following": False}},
    })
    assert InstagramClient(page).lookup("ali") == (Status.PENDING, "42")


def test_lookup_rate_limited_raises():
    page = FakePage({"web_profile_info": {"status": 429, "body": None}})
    with pytest.raises(RateLimited):
        InstagramClient(page).lookup("ali")


def test_cancel_posts_destroy():
    page = FakePage({"friendships/destroy/42": {"status": 200, "body": {"status": "ok"}}})
    InstagramClient(page).cancel("42")
    assert page.calls[-1]["url"].endswith("/api/v1/friendships/destroy/42/")
    assert page.calls[-1]["method"] == "POST"
    assert page.calls[-1]["body"] == "user_id=42"


def test_current_username_logged_out():
    assert InstagramClient(FakePage()).current_username() is None


def test_current_username_logged_in():
    page = FakePage({"users/7/info": {"status": 200, "body": {"user": {"username": "Efe"}}}},
                    cookies={"ds_user_id": "7"})
    assert InstagramClient(page).current_username() == "efe"
