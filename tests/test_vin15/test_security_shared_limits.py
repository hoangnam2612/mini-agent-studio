from src.config import Settings
from src.core.ratelimit import SharedSlidingWindow


class FakeRedis:
    def __init__(self):
        self.data = {}

    def ping(self):
        return True

    def zadd(self, key, values):
        self.data.setdefault(key, []).extend(values.values())

    def zremrangebyscore(self, key, low, high):
        self.data[key] = [value for value in self.data.get(key, []) if value > high]

    def zcard(self, key):
        return len(self.data.get(key, []))

    def zrange(self, key, start, stop, withscores=False):
        values = sorted(self.data.get(key, []))
        return [(str(value), value) for value in values[start:stop + 1]] if withscores else values[start:stop + 1]

    def expire(self, key, seconds):
        return True

    def delete(self, key):
        self.data.pop(key, None)


def test_shared_window_uses_redis_sorted_set():
    store = FakeRedis()
    window = SharedSlidingWindow(redis_client=store)
    window.add("assistant:7")
    assert window.count("assistant:7", 60) == 1
    assert window.retry_after("assistant:7", 60) >= 1
    window.clear("assistant:7")
    assert window.count("assistant:7", 60) == 0


def test_production_rejects_default_jwt_secret():
    try:
        Settings(_env_file=None, app_env="production")
    except ValueError as exc:
        assert "JWT_SECRET" in str(exc)
    else:
        raise AssertionError("production settings accepted the development JWT secret")
