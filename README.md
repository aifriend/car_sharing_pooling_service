# CABIFY CAR POOLING SERVICE
## Proposed challenge
https://gitlab.com/cabify-challenge/car-pooling-challenge-aifriend/blob/master/CHALLENGE.md

### Stack used
- Python 3.7
- FastAPI

### IDE
- PyCharm
- Gitlab CI
- Docker

### REST service endpoints

This service provide a REST API which will be used to interact with it.

This API comply with the following contract:

- GET /status
    
    Indicate the service has started up correctly and is ready to accept requests.
    
      http://localhost:9091/status
    
    Returns: 
    
    * **200 OK** When the service is ready to receive requests.

- PUT /cars

    Load the list of available cars in the service and remove all previous data (existing journeys and cars). This method may be called more than once during the life cycle of the service.

      http://localhost:9091/cars
     
    **Body** _required_ The list of cars to load.
    
    **Content Type** `application/json`

    Sample:
    
    ```json
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
    ```

    Returns:
    
    * **200 OK** When the list is registered correctly.
    * **400 Bad Request** When there is a failure in the request format, expected
      headers, or the payload can't be unmarshalled.

- POST /journey

    A group of people requests to perform a journey.
    
      http://localhost:9091/journey
         
    **Body** _required_ The group of people that wants to perform the journey
    
    **Content Type** `application/json`
    
    Sample:
    
    ```json
    {
      "id": 1,
      "people": 4
    }
    ```
    
    Returns:
    
    * **200 OK** or **202 Accepted** When the group is registered correctly
    * **400 Bad Request** When there is a failure in the request format or the
      payload can't be unmarshalled.

- POST /dropoff

    A group of people requests to be dropped off. Whether they traveled or not.

      http://localhost:9091/dropoff
      
    **Body** _required_ A form with the group ID, such that `ID=X`
    
    **Content Type** `application/x-www-form-urlencoded`
    
    Returns:
    
    * **200 OK** or **204 No Content** When the group is unregistered correctly.
    * **404 Not Found** When the group is not to be found.
    * **400 Bad Request** When there is a failure in the request format or the
      payload can't be unmarshalled.

- POST /locate

    Given a group ID such that `ID=X`, return the car the group is traveling
    with, or no car if they are still waiting to be served (i.e.- journey requested)
    
      http://localhost:9091/locate
        
    **Body** _required_ A url encoded form with the group ID such that `ID=X`
    
    **Content Type** `application/x-www-form-urlencoded`
    
    **Accept** `application/json`
    
    Returns:
    
    * **200 OK** With the car as the payload when the group is assigned to a car.
    * **204 No Content** When the group is waiting to be assigned to a car.
    * **404 Not Found** When the group is not to be found.
    * **400 Bad Request** When there is a failure in the request format or the
      payload can't be unmarshalled.

### Architecture
Just one microservice is implemented that will expose all the car pooling services at 9091 port through above endpoints.
* Car Pooling Service: This service is responsible for car availability to track the available seats in cars.

### What was not used (But would be good)
* Cache: Both client and server side cache can be a good choice in cases of high volume of request in production.
* Simple car pooling queue handler that should be improved with the use of deep reinforcement learning techniques to improve best action while serving car request in contexts of:
    - long waiting list
    - dynamically changing car list of availables car/seats 
    - frequent drop-offs

### Assumptions
* When a journey request is made, a car is immediately searched for journey allocation. If there is no car availabel, the request kept in the waiting list.
    * I assume that when a trip is requested, an available car is searched
    * If no car is found, the travel request is left wait
* I assume the list of car can be modified at any time maintaining the rest of the data structure of the pooling service as is
* Those journeys who are waiting they are served first before the new journey request is searched for car allocation
* The map of journeys/cars is performed each time a journey is requested:
    * Those who are waiting are served first
    * Then the current request is served if any

## A new approach 

### Reinforcement Learning 
A crucial point to consider in optimizing a carpooling policy is to gauge the future prospect of being able to pick up additional passengers along the way at each decision point. Reinforcement Learning (RL) is a data-driven approach for solving a Markov decision process (MDP), which models a multi-stage sequential decision-making process with a long optimization horizon.

I develop a reinforcement learning (RL) based system to learn an effective policy for carpooling that maximizes transportation efficiency so that fewer cars are required to fulfill the given amount of trip demand.
