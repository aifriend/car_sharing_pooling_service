# Car Pooling Service

REST API for managing a car pooling service, built as a coding challenge. Handles car fleet management, journey requests, passenger allocation, and drop-off operations.

## Overview

A microservice that matches groups of people to available cars based on seat availability, implementing a priority queue for waiting passengers.

## API Endpoints

| Method | Endpoint | Description | Response |
|--------|----------|-------------|----------|
| `GET` | `/status` | Health check | `200 OK` |
| `PUT` | `/cars` | Load car fleet (JSON) | `200 OK` / `400 Bad Request` |
| `POST` | `/journey` | Request a ride (JSON) | `200 OK` / `202 Accepted` |
| `POST` | `/dropoff` | End a journey (form data) | `200 OK` / `404 Not Found` |
| `POST` | `/locate` | Find assigned car (form data) | `200 JSON` / `204 No Content` |

## Tech Stack

- **Language:** Python 3.7
- **Framework:** FastAPI
- **Deployment:** Docker
- **Port:** 9091

## Project Structure

```
├── service/
│   ├── car_pooling/      # Core business logic
│   ├── test/             # Unit tests
│   ├── manage.py         # Application entry point
│   └── requirements.txt
├── Dockerfile
├── Makefile
├── CHALLENGE.md          # Original challenge specification
└── setup.cfg
```

## Getting Started

### Local Development
```bash
cd service
pip install -r requirements.txt
python manage.py
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

## Design Decisions

- Waiting groups are served in FIFO order (priority over new requests)
- Resetting the car list maintains journey data integrity
- Continuous matching runs when cars become available after drop-offs

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Author

**Jose** — [@aifriend](https://github.com/aifriend)
