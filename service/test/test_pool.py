"""Unit tests for the core car pooling domain logic."""
import pytest

from car_pooling.pool import CarPool, CarPoolError


@pytest.fixture
def pool():
    p = CarPool()
    p.reset([(1, 4), (2, 5), (3, 6)])
    return p


# ------------------------------------------------------------------ reset

def test_reset_replaces_fleet_and_journeys(pool):
    assert pool.journey(1, 4) == 1
    pool.reset([(7, 6)])
    # previous group is gone, old cars are gone
    with pytest.raises(KeyError):
        pool.locate(1)
    assert pool.journey(2, 6) == 7


def test_reset_validates_atomically(pool):
    with pytest.raises(CarPoolError):
        pool.reset([(1, 4), (2, 7)])  # 7 seats: invalid
    assert pool.journey(1, 4) == 1  # old state untouched


@pytest.mark.parametrize("cars", [
    [(1, 0)],            # too few seats
    [(1, 7)],            # too many seats
    [(1, 4.5)],          # non-integer seats
    [("a", 4)],          # non-integer id
    [(1, 4), (1, 5)],    # duplicate car id
    [(1, True)],         # bool is not a valid seat count
])
def test_reset_rejects_bad_cars(cars):
    with pytest.raises(CarPoolError):
        CarPool().reset(cars)


def test_reset_accepts_empty_fleet():
    pool = CarPool()
    pool.reset([])
    assert pool.journey(1, 2) is None  # waits forever, but registers


# ----------------------------------------------------------------- journey

def test_journey_best_fit(pool):
    # fewest free seats that still fits -> car 1 (4 seats), not car 2 or 3
    assert pool.journey(1, 4) == 1
    # car 1 is now full; next best fit for 2 is car 2 (5 seats)
    assert pool.journey(2, 2) == 2
    car = pool.locate(2)
    assert car.id == 2 and car.seats == 5


def test_journey_queues_when_nothing_fits(pool):
    assert pool.journey(1, 6) == 3
    assert pool.journey(2, 6) is None  # no car left with 6 free seats
    assert pool.locate(2) is None      # waiting


def test_journey_rejects_duplicates_and_bad_sizes(pool):
    pool.journey(1, 2)
    with pytest.raises(CarPoolError):
        pool.journey(1, 3)  # same id again
    with pytest.raises(CarPoolError):
        pool.journey(2, 0)
    with pytest.raises(CarPoolError):
        pool.journey(3, 7)


def test_groups_share_cars(pool):
    pool.reset([(1, 6)])
    assert pool.journey(1, 2) == 1
    assert pool.journey(2, 4) == 1   # 2 + 4 = 6: exactly full
    assert pool.journey(3, 1) is None  # no seats left


# ----------------------------------------------------------------- dropoff

def test_dropoff_unknown_group(pool):
    assert pool.dropoff(999) is False


def test_dropoff_waiting_group(pool):
    pool.reset([(1, 4)])
    pool.journey(1, 4)
    assert pool.journey(2, 2) is None
    assert pool.dropoff(2) is True   # waiting groups can cancel
    with pytest.raises(KeyError):
        pool.locate(2)


def test_dropoff_frees_seats_and_serves_queue_fifo(pool):
    pool.reset([(1, 6)])
    pool.journey(1, 6)                 # fills the only car
    assert pool.journey(2, 4) is None  # waits
    assert pool.journey(3, 2) is None  # waits
    assert pool.dropoff(1) is True
    # FIFO: group 2 gets the car first, group 3 shares the leftovers
    assert pool.locate(2).id == 1
    assert pool.locate(3).id == 1


def test_queue_skips_groups_that_still_do_not_fit(pool):
    pool.reset([(1, 6), (2, 4)])
    pool.journey(1, 6)
    pool.journey(2, 4)                 # both cars full
    assert pool.journey(3, 5) is None  # waits (needs 5)
    assert pool.journey(4, 3) is None  # waits (needs 3)
    pool.dropoff(2)                    # frees 4 seats
    assert pool.locate(3) is None      # 5 still does not fit
    assert pool.locate(4).id == 2      # but 3 rides opportunistically


def test_waiting_groups_do_not_block_new_arrivals(pool):
    # Spec example: a waiting group of 6 must not block a group of 2
    # when the 2 fits somewhere the 6 never could.
    pool.reset([(1, 4), (2, 6)])
    pool.journey(1, 4)
    pool.journey(2, 2)
    assert pool.journey(3, 6) is None  # only 4 free seats left -> waits
    assert pool.journey(4, 2) == 2     # newcomer still rides


def test_group_id_is_reusable_after_dropoff(pool):
    pool.journey(1, 4)
    assert pool.dropoff(1) is True
    assert pool.journey(1, 4) is not None  # same id again: fine


# ------------------------------------------------------------------ locate

def test_locate_unknown_group_raises(pool):
    with pytest.raises(KeyError):
        pool.locate(42)


# ------------------------------------------------------------- performance

def test_allocation_scales_with_fleet_size():
    pool = CarPool()
    pool.reset([(i, 4 + i % 3) for i in range(1, 10001)])
    for group in range(1, 5001):
        pool.journey(group, 4)
    # 10000 cars, 5000 groups: must complete fast; no assertion on time,
    # the test simply would time out with the old O(fleet) scan per request.
    assert sum(1 for g in range(1, 5001) if pool.locate(g) is not None) > 0
