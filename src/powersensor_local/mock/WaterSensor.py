from MockSensor import MockSensor


class WaterSensor(MockSensor):
    """Simulates a water sensor"""

    def __init__(self, mac: str, update_interval: float = 30.0,shared_state : dict | None = None):
        super().__init__(mac, 'water',  update_interval, shared_state)

    def get_unit(self):
        return 'L'
