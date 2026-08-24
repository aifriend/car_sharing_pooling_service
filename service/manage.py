"""Car pooling service — REST API entry point.

Run with:  python manage.py   (or: uvicorn manage:app --port 9091)

Optional fairness policies (disabled by default to preserve the challenge
contract), set via environment variables:
    QUEUE_TTL_SECONDS       waiting groups give up after this many seconds
    PRIORITY_AFTER_SECONDS  after a group waits this long, new arrivals
                            queue behind it (strict FIFO) instead of being
                            seated directly

Concurrency: all handlers are async and every pool operation runs under a
single asyncio.Lock, so check-then-act sequences are atomic by design.
"""
import asyncio
import os

import uvicorn
from fastapi import FastAPI, Form, Response, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field

from car_pooling.pool import MAX_SEATS, MIN_SEATS, CarPool, CarPoolError


def _env_float(name):
    value = os.environ.get(name)
    return float(value) if value else None


pool = CarPool(
    queue_ttl_seconds=_env_float("QUEUE_TTL_SECONDS"),
    priority_after_seconds=_env_float("PRIORITY_AFTER_SECONDS"),
)
pool_lock = asyncio.Lock()

app = FastAPI(title="Car Pooling Service")


class CarIn(BaseModel):
    id: int
    seats: int = Field(ge=MIN_SEATS, le=MAX_SEATS)


class JourneyIn(BaseModel):
    id: int
    people: int = Field(ge=MIN_SEATS, le=MAX_SEATS)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    # The contract asks for 400 on malformed payloads, not FastAPI's 422.
    return Response(status_code=status.HTTP_400_BAD_REQUEST)


@app.get("/status")
async def service_status():
    """200 OK once the service is ready to receive requests."""
    return Response(status_code=status.HTTP_200_OK)


@app.get("/metrics")
async def service_metrics():
    """Snapshot of fleet utilisation and queue depth (JSON)."""
    async with pool_lock:
        pool.expire_waiting()
        return {
            "cars_total": pool.cars_total,
            "seats_total": pool.seats_total,
            "seats_free": pool.seats_free,
            "groups_traveling": pool.groups_traveling,
            "groups_waiting": pool.groups_waiting,
        }


@app.put("/cars")
async def service_load_cars(cars: list[CarIn]):
    """Load the fleet, removing all previous cars and journeys."""
    async with pool_lock:
        try:
            pool.reset([(car.id, car.seats) for car in cars])
        except CarPoolError:
            return Response(status_code=status.HTTP_400_BAD_REQUEST)
    return Response(status_code=status.HTTP_200_OK)


@app.post("/journey")
async def service_journey(journey: JourneyIn):
    """Register a group; 200 when seated at once, 202 when queued."""
    async with pool_lock:
        try:
            car_id = pool.journey(journey.id, journey.people)
        except CarPoolError:
            return Response(status_code=status.HTTP_400_BAD_REQUEST)
    if car_id is None:
        return Response(status_code=status.HTTP_202_ACCEPTED)
    return Response(status_code=status.HTTP_200_OK)


@app.post("/dropoff")
async def service_dropoff(ID: int = Form(...)):
    """Unregister a group, whether it traveled or not."""
    async with pool_lock:
        found = pool.dropoff(ID)
    if not found:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/locate")
async def service_locate(ID: int = Form(...)):
    """Return the car a group travels with; 204 while it waits."""
    async with pool_lock:
        try:
            car = pool.locate(ID)
        except KeyError:
            return Response(status_code=status.HTTP_404_NOT_FOUND)
    if car is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return {"id": car.id, "seats": car.seats}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9091, log_level="info")
