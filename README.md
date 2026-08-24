# Car Pooling Service

REST API for managing a car pooling service, built as a coding challenge. Handles car fleet management, journey requests, passenger allocation, and drop-off operations.

## Overview

A microservice that matches groups of people to available cars based on seat availability. Groups share cars, and groups that fit nowhere wait in a FIFO queue until capacity frees up.

## API Endpoints

| Method | Endpoint | Description | Response |
|--------|----------|-------------|----------|
| `GET` | `/status` | Health check | `200 OK` |
| `GET` | `/metrics` | Fleet/queue snapshot (JSON; not part of the challenge contract) | `200 OK` |
| `PUT` | `/cars` | Load car fleet, wiping all previous state (JSON) | `200 OK` / `400 Bad Request` |
| `POST` | `/journey` | Request a ride (JSON) | `200 OK` (seated) / `202 Accepted` (queued) / `400 Bad Request` |
| `POST` | `/dropoff` | End a journey, traveled or not (form data `ID=X`) | `204 No Content` / `404 Not Found` / `400 Bad Request` |
| `POST` | `/locate` | Find the car a group travels with (form data `ID=X`) | `200 JSON` / `204 No Content` (waiting) / `404 Not Found` / `400 Bad Request` |

## Tech Stack

- **Language:** Python 3.12+ (developed on 3.14)
- **Framework:** FastAPI + Uvicorn
- **Deployment:** Docker
- **Port:** 9091

## Project Structure

```
├── service/
│   ├── car_pooling/
│   │   └── pool.py           # Core domain logic (framework-independent)
│   ├── test/
│   │   ├── test_pool.py      # Unit tests for the domain logic
│   │   ├── test_policies.py  # Unit tests for TTL / priority policies
│   │   ├── test_api.py       # HTTP API contract tests
│   │   ├── test_property.py  # Hypothesis property-based invariant tests
│   │   └── test_concurrency.py  # Async concurrency consistency tests
│   ├── manage.py             # FastAPI app / entry point
│   └── requirements.txt
├── Dockerfile
├── Makefile
├── CHALLENGE.md              # Original challenge specification
└── README.md
```

## Getting Started

### Local Development
```bash
make setup   # create .venv and install dependencies
make run     # serve on http://localhost:9091
```

Or manually:
```bash
python3 -m venv .venv
.venv/bin/pip install -r service/requirements.txt
cd service && ../.venv/bin/python manage.py
```

### Docker
```bash
docker build -t car-pooling-service .
docker run -p 9091:9091 car-pooling-service
```

### Run Tests
```bash
make test
```

## Example Usage

Load cars:
```bash
curl -X PUT http://localhost:9091/cars \
  -H "Content-Type: application/json" \
  -d '[{"id": 1, "seats": 4}, {"id": 2, "seats": 6}]'
```

Request a journey:
```bash
curl -X POST http://localhost:9091/journey \
  -H "Content-Type: application/json" \
  -d '{"id": 1, "people": 3}'
```

Locate a group:
```bash
curl -X POST http://localhost:9091/locate -d "ID=1"
# => {"id": 1, "seats": 4}   (the car, with its total seat count)
```

## Design Decisions

- **Seat sharing.** Cars have 1–6 seats and can carry several groups at once, as the spec's "4 empty seats at a car for 6" example requires. The pool tracks each car's free seats.
- **Best-fit allocation.** A group is seated in the car with the fewest free seats that still fits it, minimising fragmentation — a group of 2 will not take a 6-seater when a tighter car exists ("only if you have nowhere else to make them ride").
- **FIFO waiting queue, opportunistic riding.** Groups that fit nowhere wait in arrival order. The queue is drained whenever seats are freed (drop-off); a waiting group that still fits nowhere is skipped so later groups can ride. Because the queue only ever holds groups that fit *nowhere*, new arrivals can be seated directly without ever stealing capacity from a waiter.
- **Fast lookups.** Cars are indexed in buckets by free-seat count, so finding the best-fit car is O(1) in fleet size (at most 6 bucket probes) instead of scanning the whole fleet per request.
- **Atomic fleet reset.** `PUT /cars` validates the whole payload first; on any error it returns `400` and keeps the previous state. On success it wipes all cars *and* journeys, as the spec requires.
- **Validation.** Seats and group sizes must be integers in 1–6; duplicate car ids in one load and duplicate group ids while a group is active are rejected with `400`. A group id can be reused after drop-off.
- **Thin API layer.** `manage.py` only translates HTTP ⇄ domain calls; all rules live in `car_pooling/pool.py`, which is unit-tested without HTTP.
- **Contract status codes.** Request validation errors are mapped to `400` (not FastAPI's default `422`); `/journey` returns `200` when the group is seated immediately and `202` when queued (both allowed by the spec); `/locate` returns the full car payload.
- **Concurrency by design.** All handlers are `async` and every pool operation runs under a single `asyncio.Lock`, so check-then-act sequences are atomic even under concurrent requests — verified by dedicated concurrency tests.
- **Observability.** `GET /metrics` returns a JSON snapshot: fleet size, total/free seats, traveling and waiting group counts.

## Optional Fairness Policies

Both are **disabled by default** (the default behavior is exactly the challenge contract) and are enabled via environment variables:

| Variable | Effect |
|----------|--------|
| `QUEUE_TTL_SECONDS` | Waiting groups older than this give up and leave, as if they had sent `/dropoff`. Enforced lazily on the next request — no background threads. |
| `PRIORITY_AFTER_SECONDS` | Once the oldest waiting group has waited this long, the service switches to strict FIFO: new arrivals queue behind it instead of being seated directly, until the queue drains. Bounds starvation of large groups under a stream of small ones. |

Example:
```bash
QUEUE_TTL_SECONDS=300 PRIORITY_AFTER_SECONDS=60 make run
```

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Author

**Jose** — [@aifriend](https://github.com/aifriend)
