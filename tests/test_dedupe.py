from bot.dedupe import UpdateGuard


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_the_first_visit_is_new_and_the_second_is_a_repeat():
    guard = UpdateGuard()
    assert guard.seen(1) is False
    assert guard.seen(1) is True


def test_an_entry_expires_after_its_ttl():
    clock = FakeClock()
    guard = UpdateGuard(ttl_seconds=60, clock=clock)
    assert guard.seen(5) is False
    clock.now += 61
    assert guard.seen(5) is False, "after the TTL the same id is treated as new again"


def test_the_cache_is_bounded():
    guard = UpdateGuard(max_entries=3)
    for update_id in range(5):
        guard.seen(update_id)
    assert len(guard) == 3
    assert guard.seen(0) is False, "the oldest id was evicted, so it looks new"
