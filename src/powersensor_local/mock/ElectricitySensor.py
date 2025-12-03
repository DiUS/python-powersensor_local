from MockSensor import MockSensor


class ElectricitySensor(MockSensor):
    """Simulates a magnetic sensor"""

    def __init__(self, mac: str, role=None, update_interval: float = 30.0,shared_state : dict | None = None):
        super().__init__(mac, role,  update_interval, shared_state)

    def get_unit(self):
        return 'w'
