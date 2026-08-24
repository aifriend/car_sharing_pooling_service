"""Core car pooling domain logic.

Framework-independent so it can be unit tested without the HTTP layer.

Model:
- Cars have a fixed number of seats and can be shared by several groups,
  as long as the sum of their sizes does not exceed the seat count.
- Groups that fit nowhere wait in a FIFO queue. Invariant: a queued group
  never fits in any currently available capacity, so new arrivals may be
  allocated directly without starving earlier waiters (they "ride
  opportunistically", per the challenge spec). The invariant is restored
  every time capacity is freed by draining the queue in arrival order.
- Allocation is best-fit: the car with the fewest free seats that still
  fits the group is chosen, which minimises fragmentation.

Optional policies (both disabled by default, preserving the challenge
contract exactly):
- ``queue_ttl_seconds``: waiting groups older than this give up and leave
  (enforced lazily on the next pool operation — no background threads).
- ``priority_after_seconds``: once the oldest waiting group has waited
  longer than this, the pool switches to strict FIFO — new arrivals queue
  behind it instead of being seated directly — until the queue drains.
  This bounds starvation of large groups under a stream of small ones.

Performance: cars are indexed in buckets by their free seat count, so
finding the best-fit car is O(MAX_SEATS) instead of a full fleet scan.
"""
import time

MIN_SEATS = 1
MAX_SEATS = 6


class CarPoolError(ValueError):
    """Raised on invalid input or an already registered group/car."""


class Car:
    __slots__ = ("id", "seats", "available")

    def __init__(self, car_id: int, seats: int):
        self.id = car_id
        self.seats = seats
        self.available = seats

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"Car(id={self.id}, seats={self.seats}, available={self.available})"


class CarPool:
    """Tracks cars, traveling groups and the FIFO waiting queue."""

    def __init__(self, queue_ttl_seconds=None, priority_after_seconds=None,
                 clock=time.monotonic):
        self._queue_ttl = queue_ttl_seconds
        self._priority_after = priority_after_seconds
        self._clock = clock
        self._cars = {}         # car_id -> Car
        # free seats -> {car_id: None}; dicts keep insertion order so ties
        # resolve FIFO and picking one is O(1)
        self._buckets = [{} for _ in range(MAX_SEATS + 1)]
        self._people = {}       # group_id -> group size (waiting + traveling)
        self._waiting = {}      # group_id -> (group size, enqueued at), FIFO
        self._assignments = {}  # group_id -> car_id

    # --------------------------------------------------------------- metrics

    @property
    def cars_total(self) -> int:
        return len(self._cars)

    @property
    def seats_total(self) -> int:
        return sum(car.seats for car in self._cars.values())

    @property
    def seats_free(self) -> int:
        return sum(car.available for car in self._cars.values())

    @property
    def groups_traveling(self) -> int:
        return len(self._assignments)

    @property
    def groups_waiting(self) -> int:
        return len(self._waiting)

    # ------------------------------------------------------------------ cars

    def reset(self, cars):
        """Replace the whole fleet and drop every journey (PUT /cars).

        :param cars: iterable of ``(car_id, seats)`` pairs.
        :raises CarPoolError: on malformed entries or duplicate car ids;
            the previous state is left untouched.
        """
        new_cars = {}
        for car_id, seats in cars:
            if not isinstance(car_id, int) or isinstance(car_id, bool):
                raise CarPoolError(f"invalid car id: {car_id!r}")
            if not isinstance(seats, int) or isinstance(seats, bool) \
                    or not MIN_SEATS <= seats <= MAX_SEATS:
                raise CarPoolError(f"invalid seat count: {seats!r}")
            if car_id in new_cars:
                raise CarPoolError(f"duplicate car id: {car_id!r}")
            new_cars[car_id] = Car(car_id, seats)

        self._cars = new_cars
        self._buckets = [{} for _ in range(MAX_SEATS + 1)]
        for car in new_cars.values():
            self._buckets[car.available][car.id] = None
        self._people = {}
        self._waiting = {}
        self._assignments = {}

    # --------------------------------------------------------------- journey

    def journey(self, group_id: int, people: int):
        """Register a group of ``people`` for a journey.

        Returns the allocated car id, or ``None`` if the group was queued.
        :raises CarPoolError: invalid size or group id already registered.
        """
        if not isinstance(people, int) or isinstance(people, bool) \
                or not MIN_SEATS <= people <= MAX_SEATS:
            raise CarPoolError(f"invalid group size: {people!r}")
        self._purge_expired()
        if group_id in self._people:
            raise CarPoolError(f"duplicate group id: {group_id!r}")

        self._people[group_id] = people
        # strict FIFO while an aged waiter exists: no jumping the queue
        if not self._priority_active():
            car = self._find_car(people)
            if car is not None:
                self._allocate(car, group_id, people)
                return car.id
        self._waiting[group_id] = (people, self._clock())
        return None

    def dropoff(self, group_id: int) -> bool:
        """Unregister a group, whether traveling or waiting.

        Frees the seats and drains the waiting queue in arrival order.
        Returns ``False`` when the group is unknown.
        """
        self._purge_expired()
        if group_id not in self._people:
            return False
        people = self._people.pop(group_id)

        if group_id in self._waiting:
            del self._waiting[group_id]
        else:
            car = self._cars[self._assignments.pop(group_id)]
            self._unbucket(car)
            car.available += people
            self._bucket(car)
            self._process_queue()
        return True

    def locate(self, group_id: int):
        """Return the ``Car`` a group travels with, ``None`` if it waits.

        :raises KeyError: when the group is not registered at all.
        """
        self._purge_expired()
        if group_id not in self._people:
            raise KeyError(group_id)
        car_id = self._assignments.get(group_id)
        return self._cars[car_id] if car_id is not None else None

    def expire_waiting(self):
        """Drop over-age waiting groups now (used before reading metrics)."""
        self._purge_expired()

    # -------------------------------------------------------------- internal

    def _purge_expired(self):
        if self._queue_ttl is None or not self._waiting:
            return
        now = self._clock()
        # timestamps are monotonic and the queue is insertion ordered,
        # so expired entries always form a prefix of the queue
        for group_id, (_, enqueued_at) in list(self._waiting.items()):
            if now - enqueued_at <= self._queue_ttl:
                break
            del self._waiting[group_id]
            del self._people[group_id]

    def _priority_active(self) -> bool:
        if self._priority_after is None or not self._waiting:
            return False
        _, oldest_enqueued_at = next(iter(self._waiting.values()))
        return self._clock() - oldest_enqueued_at > self._priority_after

    def _find_car(self, people: int):
        """Best-fit car: fewest free seats that still fit the group."""
        for free in range(people, MAX_SEATS + 1):
            bucket = self._buckets[free]
            if bucket:
                return self._cars[next(iter(bucket))]
        return None

    def _allocate(self, car: Car, group_id: int, people: int):
        self._unbucket(car)
        car.available -= people
        self._bucket(car)
        self._assignments[group_id] = car.id

    def _process_queue(self):
        """Serve waiting groups in arrival order while capacity allows."""
        for group_id, (people, _) in list(self._waiting.items()):
            car = self._find_car(people)
            if car is None:
                continue  # still fits nowhere; later groups may ride
            del self._waiting[group_id]
            self._allocate(car, group_id, people)

    def _bucket(self, car: Car):
        if car.available > 0:
            self._buckets[car.available][car.id] = None

    def _unbucket(self, car: Car):
        if car.available > 0:
            self._buckets[car.available].pop(car.id, None)
