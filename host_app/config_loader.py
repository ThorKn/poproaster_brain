import json
import os

class ConfigLoader:
    def __init__(self, config_path=None):
        if config_path is None:
            # Default to root config.json
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config.json")
        
        self.config_path = config_path
        self.config_data = {}
        self.load()

    def load(self):
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found at '{self.config_path}'")
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config_data = json.load(f)

    @property
    def system(self):
        return self.config_data.get("system", {
            "device_name": "PopRoaster Brain",
            "modbus_slave_id": 1,
            "modbus_timeout_ms": 5000
        })

    @property
    def display_defaults(self):
        return self.config_data.get("display_defaults", {
            "update_rate_ms": 100,
            "graph_time_window_s": 60,
            "rotation": 0
        })

    @property
    def sensor_defaults(self):
        return self.config_data.get("sensor_defaults", {
            "poll_interval_ms": 250
        })

    @property
    def actors(self):
        return self.config_data.get("actors", [])

    @property
    def sensors(self):
        return self.config_data.get("sensors", [])

    @property
    def slave_id(self):
        return self.system.get("modbus_slave_id", 1)

    @property
    def timeout_ms(self):
        return self.system.get("modbus_timeout_ms", 5000)
