"""Unit tests for the opt-in queue policies (TTL and priority-after)."""
import pytest

from car_pooling.pool import CarPool


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


# ---------------------------------------------------------------------- TTL

def test_ttl_expires_waiting_group(clock):
    pool = CarPool(queue_ttl_seconds=10, clock=clock)
    pool.reset([(1, 4)])
    pool.journey(1, 4)                    # fills the only car
    assert pool.journey(2, 2) is None     # waits
    clock.advance(11)
    with pytest.raises(KeyError):         # gave up and left
        pool.locate(2)
    assert pool.groups_waiting == 0


def test_ttl_keeps_fresh_groups(clock):
    pool = CarPool(queue_ttl_seconds=10, clock=clock)
    pool.reset([(1, 4)])
    pool.journey(1, 4)
    pool.journey(2, 2)
    clock.advance(5)
    assert pool.locate(2) is None         # still waiting
    assert pool.groups_waiting == 1


def test_ttl_purges_only_the_expired_prefix(clock):
    pool = CarPool(queue_ttl_seconds=10, clock=clock)
    pool.reset([(1, 4)])
    pool.journey(1, 4)
    pool.journey(2, 2)                    # enqueued at t=0
    clock.advance(8)
    pool.journey(3, 2)                    # enqueued at t=8
    clock.advance(5)                      # t=13: group 2 stale, group 3 fresh
    with pytest.raises(KeyError):
        pool.locate(2)
    assert pool.locate(3) is None         # still waiting


def test_ttl_disabled_by_default(clock):
    pool = CarPool(clock=clock)
    pool.reset([(1, 4)])
    pool.journey(1, 4)
    pool.journey(2, 2)
    clock.advance(10_000)
    assert pool.locate(2) is None         # waits forever
    assert pool.dropoff(2) is True


# --------------------------------------------------------------- priority

def test_priority_after_queues_new_arrivals(clock):
    pool = CarPool(priority_after_seconds=10, clock=clock)
    pool.reset([(1, 4), (2, 6)])
    pool.journey(1, 4)                    # fills car 1
    pool.journey(2, 2)                    # car 2, 4 seats free
    assert pool.journey(3, 6) is None     # fits nowhere -> waits
    clock.advance(11)                     # group 3 is now "aged"
    # a newcomer would fit in car 2, but strict FIFO is in effect
    assert pool.journey(4, 2) is None
    assert pool.locate(4) is None
    # freeing car 2 drains the queue in arrival order: 3 rides, 4 waits on
    pool.dropoff(2)
    assert pool.locate(3).id == 2
    assert pool.locate(4) is None


def test_priority_releases_when_queue_drains(clock):
    pool = CarPool(priority_after_seconds=10, clock=clock)
    pool.reset([(1, 6)])
    pool.journey(1, 6)
    pool.journey(2, 4)                    # waits
    clock.advance(11)
    pool.journey(3, 1)                    # queued behind aged group 2
    pool.dropoff(1)                       # drains: 2 and 3 both fit now
    assert pool.locate(2).id == 1
    assert pool.locate(3).id == 1
    clock.advance(11)                     # queue empty: back to normal
    assert pool.journey(4, 1) == 1        # seated directly again


def test_priority_disabled_by_default(clock):
    pool = CarPool(clock=clock)
    pool.reset([(1, 4), (2, 6)])
    pool.journey(1, 4)
    pool.journey(2, 2)
    pool.journey(3, 6)                    # waits
    clock.advance(10_000)
    assert pool.journey(4, 2) == 2        # newcomers still ride
