"""API contract tests — exercises every endpoint and status code."""
import pytest
from fastapi.testclient import TestClient

from manage import app, pool


@pytest.fixture
def client():
    pool.reset([])
    return TestClient(app)


def load_cars(client, cars=((1, 4), (2, 6))):
    return client.put("/cars", json=[{"id": i, "seats": s} for i, s in cars])


# ------------------------------------------------------------------ status

def test_status(client):
    assert client.get("/status").status_code == 200


# ------------------------------------------------------------------ metrics

def test_metrics_snapshot(client):
    load_cars(client, cars=[(1, 4)])
    client.post("/journey", json={"id": 1, "people": 4})   # seated
    client.post("/journey", json={"id": 2, "people": 2})   # queued
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.json() == {
        "cars_total": 1,
        "seats_total": 4,
        "seats_free": 0,
        "groups_traveling": 1,
        "groups_waiting": 1,
    }


def test_metrics_empty_pool(client):
    assert client.get("/metrics").json() == {
        "cars_total": 0,
        "seats_total": 0,
        "seats_free": 0,
        "groups_traveling": 0,
        "groups_waiting": 0,
    }


# -------------------------------------------------------------------- cars

def test_put_cars(client):
    assert load_cars(client).status_code == 200


def test_put_cars_empty_list(client):
    assert load_cars(client, cars=[]).status_code == 200


def test_put_cars_resets_state(client):
    load_cars(client)
    client.post("/journey", json={"id": 1, "people": 4})
    load_cars(client, cars=[(9, 6)])
    assert client.post("/locate", data={"ID": 1}).status_code == 404


@pytest.mark.parametrize("payload", [
    [{"id": 1}],                        # missing seats
    [{"seats": 4}],                     # missing id
    [{"id": 1, "seats": 7}],            # too many seats
    [{"id": 1, "seats": 0}],            # too few seats
    [{"id": 1, "seats": "four"}],       # wrong type
    [{"id": 1, "seats": 4.5}],          # non-integer
    {"id": 1, "seats": 4},              # not a list
    [{"id": 1, "seats": 4}, {"id": 1, "seats": 5}],  # duplicate id
])
def test_put_cars_bad_request(client, payload):
    assert client.put("/cars", json=payload).status_code == 400


def test_put_cars_wrong_content_type(client):
    response = client.put("/cars", content="ID=1",
                          headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert response.status_code == 400


# ------------------------------------------------------------------ journey

def test_journey_allocated(client):
    load_cars(client)
    assert client.post("/journey", json={"id": 1, "people": 4}).status_code == 200


def test_journey_queued(client):
    load_cars(client, cars=[(1, 4)])
    assert client.post("/journey", json={"id": 1, "people": 6}).status_code == 202


@pytest.mark.parametrize("body", [
    {"id": 1},                          # missing people
    {"people": 4},                      # missing id
    {"id": 1, "people": 0},
    {"id": 1, "people": 7},
    {"id": 1, "people": "four"},
    {},
])
def test_journey_bad_request(client, body):
    load_cars(client)
    assert client.post("/journey", json=body).status_code == 400


def test_journey_duplicate_group(client):
    load_cars(client)
    client.post("/journey", json={"id": 1, "people": 2})
    assert client.post("/journey", json={"id": 1, "people": 2}).status_code == 400


def test_journey_wrong_content_type(client):
    load_cars(client)
    response = client.post("/journey", content="ID=1",
                           headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert response.status_code == 400


# ------------------------------------------------------------------ dropoff

def test_dropoff_traveling_group(client):
    load_cars(client)
    client.post("/journey", json={"id": 1, "people": 4})
    assert client.post("/dropoff", data={"ID": 1}).status_code == 204
    assert client.post("/locate", data={"ID": 1}).status_code == 404


def test_dropoff_waiting_group(client):
    load_cars(client, cars=[(1, 4)])
    client.post("/journey", json={"id": 1, "people": 4})
    client.post("/journey", json={"id": 2, "people": 4})  # queued
    assert client.post("/dropoff", data={"ID": 2}).status_code == 204


def test_dropoff_not_found(client):
    load_cars(client)
    assert client.post("/dropoff", data={"ID": 99}).status_code == 404


def test_dropoff_bad_id(client):
    load_cars(client)
    assert client.post("/dropoff", data={"ID": "abc"}).status_code == 400
    assert client.post("/dropoff", data={}).status_code == 400


def test_dropoff_serves_waiting_group(client):
    load_cars(client, cars=[(1, 4)])
    client.post("/journey", json={"id": 1, "people": 4})
    client.post("/journey", json={"id": 2, "people": 3})
    client.post("/dropoff", data={"ID": 1})
    response = client.post("/locate", data={"ID": 2})
    assert response.status_code == 200
    assert response.json() == {"id": 1, "seats": 4}


# ------------------------------------------------------------------- locate

def test_locate_traveling_group_returns_car(client):
    load_cars(client)
    client.post("/journey", json={"id": 1, "people": 4})
    response = client.post("/locate", data={"ID": 1})
    assert response.status_code == 200
    assert response.json() == {"id": 1, "seats": 4}


def test_locate_waiting_group(client):
    load_cars(client, cars=[(1, 4)])
    client.post("/journey", json={"id": 1, "people": 6})
    response = client.post("/locate", data={"ID": 1})
    assert response.status_code == 204
    assert response.content == b""


def test_locate_not_found(client):
    load_cars(client)
    assert client.post("/locate", data={"ID": 99}).status_code == 404


def test_locate_bad_id(client):
    load_cars(client)
    assert client.post("/locate", data={"ID": "abc"}).status_code == 400


# ------------------------------------------------------- end-to-end scenario

def test_full_scenario(client):
    """Spec example, end to end through the HTTP API."""
    load_cars(client, cars=[(1, 4), (2, 6)])

    # group of 4 fills car 1; group of 2 shares car 2
    assert client.post("/journey", json={"id": 1, "people": 4}).status_code == 200
    assert client.post("/journey", json={"id": 2, "people": 2}).status_code == 200

    # group of 6 cannot fit anywhere (only 4 seats free) -> waits
    assert client.post("/journey", json={"id": 3, "people": 6}).status_code == 202
    assert client.post("/locate", data={"ID": 3}).status_code == 204

    # group of 2 may still ride: the waiting 6 could not use those seats
    assert client.post("/journey", json={"id": 4, "people": 2}).status_code == 200
    assert client.post("/locate", data={"ID": 4}).json() == {"id": 2, "seats": 6}

    # car 2 drops everyone off -> the waiting 6 finally rides
    client.post("/dropoff", data={"ID": 2})
    client.post("/dropoff", data={"ID": 4})
    assert client.post("/locate", data={"ID": 3}).json() == {"id": 2, "seats": 6}
