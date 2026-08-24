"""Concurrency tests: the app-level lock must keep state consistent even
when requests interleave inside the event loop."""
import asyncio

import httpx2

from manage import app, pool


def run_async(coro_factory):
    async def main():
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport,
                                      base_url="http://test") as client:
            return await coro_factory(client)
    return asyncio.run(main())


def test_concurrent_journeys_never_overbook():
    pool.reset([(i, 6) for i in range(1, 11)])  # 10 cars, 60 seats

    responses = run_async(lambda c: asyncio.gather(*[
        c.post("/journey", json={"id": g, "people": 4})
        for g in range(1, 101)
    ]))

    assert all(r.status_code in (200, 202) for r in responses)
    seated = sum(1 for r in responses if r.status_code == 200)
    queued = sum(1 for r in responses if r.status_code == 202)
    assert seated + queued == 100
    assert seated * 4 <= 60                       # never overbooked
    assert pool.seats_free == 60 - seated * 4     # seat accounting exact
    assert pool.groups_traveling + pool.groups_waiting == 100


def test_concurrent_duplicate_ids_register_once():
    pool.reset([(1, 6), (2, 6)])

    responses = run_async(lambda c: asyncio.gather(*[
        c.post("/journey", json={"id": 1, "people": 3}) for _ in range(50)
    ]))

    ok = [r for r in responses if r.status_code in (200, 202)]
    rejected = [r for r in responses if r.status_code == 400]
    assert len(ok) == 1                  # exactly one registration wins
    assert len(rejected) == 49
    assert pool.groups_traveling + pool.groups_waiting == 1


def test_concurrent_mixed_workload_stays_consistent():
    pool.reset([(i, 4 + i % 3) for i in range(1, 21)])  # 20 cars

    async def workload(client):
        journeys = [client.post("/journey", json={"id": g, "people": 1 + g % 6})
                    for g in range(1, 61)]
        dropoffs = [client.post("/dropoff", data={"ID": g})
                    for g in range(1, 61)]
        locates = [client.post("/locate", data={"ID": g}) for g in range(1, 61)]
        return await asyncio.gather(*(journeys + dropoffs + locates))

    responses = run_async(workload)

    assert all(r.status_code in (200, 202, 204, 400, 404) for r in responses)
    # final state must be internally consistent, whatever the interleaving
    assert set(pool._people) == set(pool._waiting) | set(pool._assignments)
    allocated = sum(pool._people[g] for g in pool._assignments)
    assert pool.seats_free + allocated == pool.seats_total
