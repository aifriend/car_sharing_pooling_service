from car_pooling.CarPooling import CarPooling


def test_pooling_load_first():
    service = CarPooling([])
    assert len(service.car_pooling) == 0
    service.cars([(1, 2), (2, 3), (3, 0)])
    assert service.car_pooling is not None


def test_pooling_load_second():
    service = CarPooling([(1, -2), (-2, 3), (3, 0), (0, 4), (2, 3), (6, 7)])
    assert len(service.car_pooling) == 1
    assert service.car_pooling.get(2)
    assert service.car_pooling.get(1) is None  # outbound minus seats
    assert service.car_pooling.get(-2) is None  # outbound minus index
    assert service.car_pooling.get(3) is None  # outbound cero seats
    assert service.car_pooling.get(0) is None  # outbound cero index
    assert service.car_pooling.get(6) is None  # outbound seats


def test_pooling_load_third():
    service = CarPooling([])
    assert len(service.car_pooling) == 0


def test_journey_fist():
    service = CarPooling([(1, 3), (2, 4), (3, 6)])
    assert service.journey(1, 5) == 3


def test_journey_second():
    service = CarPooling([(1, 2), (2, 3)])
    assert service.journey(1, 5) == 0


def test_journey_third():
    service = CarPooling([])
    assert service.journey(1, 5) == 0


def test_journey_fourth():
    service = CarPooling([(1, 2), (2, 3)])
    assert service.journey(1, 7) == -1


def test_journey_fifth():
    service = CarPooling([(1, 3), (4, 4), (7, 6)])
    assert service.journey(1, 1) == 1


def test_journey_sixth():
    service = CarPooling([(1, 4), (1, 3), (1, 1), (1, 7)])  # (1, 7) bad request
    assert service.journey(1, 4) == 0  # dictionary integrity


def test_journey_dropoff():
    service = CarPooling([(1, 3), (2, 2), (3, 1), (4, 3)])
    assert service.journey(1, 6) == 0
    assert service.drop_off(1) == 1
    assert service.drop_off(1) is None


def test_journey_waiting_first():
    service = CarPooling([(1, 3), (2, 2), (3, 1), (4, 3)])
    assert service.journey(1, 6) == 0  # waiting list
    assert service.journey(2, 6) == 0  # waiting list
    assert service.journey(3, 1) == 3  # allocated (*)
    assert service.journey(4, 6) == 0  # waiting list
    assert service.drop_off(1) == 1  # drop-off
    assert service.drop_off(4) == 4
    assert service.drop_off(5) is None  # drop-off not found
    service.cars([(1, 5), (2, 2), (3, 1), (4, 3), (5, 6), (6, 4)])  # new car list
    assert service.journey(5, 6) == 0  # waiting list first -> new one go to waiting list
    assert service.journey(6, 4) == 6  # new journey request
    assert service.journey(7, 6) == 0
    assert len(service.journey_request.waiting) == 2  # waiting list not empty
    assert service.journey_location.is_allocated(6) == 6  # check car allocation
    assert service.journey_location.is_allocated(3) == 3  # allocated from previous car list (*)
    assert service.journey(8, 3)
    assert service.journey_location.is_allocated(8) == 4  # allocated from new car list