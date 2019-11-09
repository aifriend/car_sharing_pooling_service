import uvicorn
from car_pooling.CarPooling import CarPooling
from fastapi import FastAPI, Form
from fastapi.exceptions import RequestValidationError
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, PlainTextResponse

car_pooling = None

app = FastAPI()  # API REST Framework


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return PlainTextResponse("", status_code=400)


@app.get("/")
def service_root_default():
    return Response(content="Car pooling service",
                    status_code=status.HTTP_200_OK)


@app.get("/status", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
def service_server_status():
    """
    Indicate the service has started up correctly and is ready to accept requests.

    **Method** GET
    **Url** /status

    Returns:
    * **200 OK** When the service is ready to receive requests.
    """
    try:
        if car_pooling is not None:
            return Response(status_code=status.HTTP_200_OK)

    except Exception:
        return


@app.put("/cars")
async def service_car_load(car_load: list, request: Request):
    """
    Load the list of available cars in the service and remove all previous
    data (existing journeys and cars). This method may be called more than
    once during the life cycle of the service.

    **Method** PUT
    **Url** /cars
    **Body** _required_ The list of cars to load.
    **Content Type** `application/json`
    Sample:
        [
          {
            "id": 1,
            "seats": 4
          },
          {
            "id": 2,
            "seats": 6
          }
        ]

    Returns:
    * **200 OK** When the list is registered correctly.
    * **400 Bad Request** When there is a failure in the request format, expected
    headers, or the payload can't be unmarshalled.
    """
    try:
        if request.headers["content-type"] != 'application/json':  # bad content type
            return Response(status_code=status.HTTP_400_BAD_REQUEST)

        if car_load is None:  # null request
            return Response(status_code=status.HTTP_400_BAD_REQUEST)

        if len(car_load) >= 0:  # at least one car: bad request
            for car in car_load:
                if len(car) >= 2:  # at least two items
                    car_id = car['id']  # must be 'id'
                    car_seats = car['seats']  # must be 'seats'
                    if car_pooling.add(int(car_id), int(car_seats)) is None:
                        return Response(status_code=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response(status_code=status.HTTP_400_BAD_REQUEST)

            return Response(status_code=status.HTTP_200_OK)

        else:
            return Response(status_code=status.HTTP_400_BAD_REQUEST)

    except Exception:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)


@app.post("/journey")
async def service_journey_request(journey_request: dict, request: Request):
    """
    A group of people requests to perform a journey.

    **Method** POST
    **Url** /journey
    **Body** _required_ The group of people that wants to perform the journey
    **Content Type** `application/json`
    Sample:
    {
      "id": 1,
      "people": 4
    }

    Returns:
    * **200 OK** or **202 Accepted** When the group is registered correctly
    * **400 Bad Request** When there is a failure in the request format or the
      payload can't be unmarshalled.
    """
    try:
        if request.headers["content-type"] != 'application/json':
            return Response(status_code=status.HTTP_400_BAD_REQUEST)

        if journey_request is None:
            return Response(status_code=status.HTTP_400_BAD_REQUEST)

        if len(journey_request) >= 2:
            journey_id = journey_request['id']
            journey_passengers = journey_request['people']
            allocated_car = car_pooling.journey(journey_id, journey_passengers)
            if allocated_car == CarPooling.BAD_REQUEST:
                return Response(status_code=status.HTTP_400_BAD_REQUEST)

            return Response(status_code=status.HTTP_202_ACCEPTED)

        else:
            return Response(status_code=status.HTTP_400_BAD_REQUEST)

    except Exception:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)


@app.post("/dropoff")
async def service_dropoff_request(*, ID: str = Form(...), request: Request):
    """
    A group of people requests to be dropped off. Whether they traveled or not.

    **Method** POST
    **Url** /dropoff
    **Body** _required_ A form with the group ID, such that `ID=X`
    **Content Type** `application/x-www-form-urlencoded`

    Returns:
    * **200 OK** or **204 No Content** When the group is unregistered correctly.
    * **404 Not Found** When the group is not to be found.
    * **400 Bad Request** When there is a failure in the request format or the
      payload can't be unmarshalled.
    """
    try:
        if request.headers["content-type"] != 'application/x-www-form-urlencoded':
            return Response(status_code=status.HTTP_400_BAD_REQUEST)

        if ID is None:
            return Response(status_code=status.HTTP_400_BAD_REQUEST)

        journey_id = int(ID)
        group_id = car_pooling.drop_off(journey_id)
        if group_id is None:  # drop-off group not found
            return Response(status_code=status.HTTP_404_NOT_FOUND)
        else:  # group unregistered correctly
            return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)


@app.post("/locate")
async def service_location_request(*, ID: str = Form(...), request: Request):
    """
    Given a group ID such that `ID=X`, return the car the group is traveling
    with, or no car if they are still waiting to be served (i.e.- journey requested)

    **Method** POST
    **Url** /location
    **Body** _required_ A url encoded form with the group ID such that `ID=X`
    **Content Type** `application/x-www-form-urlencoded`
    **Accept** `application/json`

    Returns:
    * **200 OK** With the car as the payload when the group is assigned to a car.
    * **204 No Content** When the group is waiting to be assigned to a car.
    * **404 Not Found** When the group is not to be found.
    * **400 Bad Request** When there is a failure in the request format or the
      payload can't be unmarshalled.
    """
    try:
        if request.headers["content-type"] != 'application/x-www-form-urlencoded':
            return Response(status_code=status.HTTP_400_BAD_REQUEST)

        if ID is None:
            return Response(status_code=status.HTTP_400_BAD_REQUEST)

        journey_id = int(ID)
        car_id = car_pooling.journey_location.is_allocated(journey_id)
        if car_id is None:  # car ID not found
            return Response(status_code=status.HTTP_404_NOT_FOUND)
        elif car_pooling.journey_request.is_waiting(journey_id):  # car ID waiting
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        else:  # car ID located
            return JSONResponse(content={'car_id': car_id},
                                status_code=status.HTTP_200_OK)

    except Exception:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)


if __name__ == "__main__":
    car_pooling = CarPooling()
    uvicorn.run(app, host="0.0.0.0", port=9091, log_level="info")
