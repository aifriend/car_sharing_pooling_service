class IService:
    """
    Interface for REST API services
    """

    def status(self):
        pass

    def cars(self, car_list):
        pass

    def journey(self, journey_id, journey_passenger):
        pass

    def drop_off(self, journey_id):
        pass

    def location(self, journey_id):
        pass
