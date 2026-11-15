"""Geliştirme için sahte Instagram (ISTEK_FAKE=1). Gerçek hesaba dokunmaz."""
from .instagram_api import Status


class FakeClient:
    def __init__(self):
        self.state = {"ali.veli": Status.PENDING, "zeynep_99": Status.PENDING, "can_01": Status.FOLLOWING,
                      "silinmis.hesap": Status.NOT_FOUND, "ayse.y": Status.PENDING}

    def current_username(self):
        return "deneme_hesabi"

    def lookup(self, u):
        s = self.state.get(u, Status.PENDING)
        return s, (None if s is Status.NOT_FOUND else u)

    def cancel(self, uid):
        self.state[uid] = Status.NONE
