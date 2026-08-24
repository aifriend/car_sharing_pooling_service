"""Property-based tests: random operation sequences must preserve invariants."""
from hypothesis import HealthCheck, given, settings, strategies as st

from car_pooling.pool import MAX_SEATS, CarPool, CarPoolError

car_lists = st.lists(
    st.tuples(st.integers(1, 100), st.integers(1, MAX_SEATS)),
    min_size=1, max_size=20, unique_by=lambda c: c[0],
)

operations = st.lists(
    st.one_of(
        st.tuples(st.just("journey"), st.integers(1, 50),
                  st.integers(1, MAX_SEATS)),
        st.tuples(st.just("dropoff"), st.integers(1, 50)),
        st.tuples(st.just("locate"), st.integers(1, 50)),
    ),
    max_size=300,
)


def check_invariants(pool):
    # seat accounting: every car between empty and full, nothing lost
    for car in pool._cars.values():
        assert 0 <= car.available <= car.seats
    allocated_seats = sum(pool._people[g] for g in pool._assignments)
    assert pool.seats_free + allocated_seats == pool.seats_total

    # every registered group is in exactly one state: waiting XOR traveling
    assert set(pool._people) == set(pool._waiting) | set(pool._assignments)

    # assignments point at real cars
    for group_id, car_id in pool._assignments.items():
        assert car_id in pool._cars

    # bucket index is consistent with actual availability
    indexed = set()
    for free in range(1, MAX_SEATS + 1):
        for car_id in pool._buckets[free]:
            assert pool._cars[car_id].available == free
            indexed.add(car_id)
    assert indexed == {c.id for c in pool._cars.values() if c.available > 0}

    # core invariant (policies disabled): no waiting group fits anywhere
    for people, _ in pool._waiting.values():
        assert pool._find_car(people) is None

    # queue is FIFO by enqueue time
    timestamps = [ts for _, ts in pool._waiting.values()]
    assert timestamps == sorted(timestamps)


@given(cars=car_lists, ops=operations)
@settings(max_examples=200, suppress_health_check=list(HealthCheck),
          deadline=None)
def test_pool_invariants(cars, ops):
    pool = CarPool()
    pool.reset(cars)
    for op, group_id, *rest in ops:
        try:
            if op == "journey":
                pool.journey(group_id, rest[0])
            elif op == "dropoff":
                pool.dropoff(group_id)
            else:
                pool.locate(group_id)
        except (CarPoolError, KeyError):
            pass  # expected domain rejections, not invariant violations
        check_invariants(pool)
