import time
import queue
from PyQt6.QtCore import QThread, pyqtSignal

def _read_input_registers(client, address, count, slave_id):
    """Compatible helper for read_input_registers across pymodbus versions"""
    try:
        return client.read_input_registers(address, count=count, device_id=slave_id)
    except TypeError:
        try:
            return client.read_input_registers(address, count=count, slave=slave_id)
        except TypeError:
            return client.read_input_registers(address, count=count, unit=slave_id)

def _write_register(client, address, value, slave_id):
    """Compatible helper for write_register across pymodbus versions"""
    try:
        return client.write_register(address, value, device_id=slave_id)
    except TypeError:
        try:
            return client.write_register(address, value, slave=slave_id)
        except TypeError:
            return client.write_register(address, value, unit=slave_id)

class ModbusWorker(QThread):
    # Signals
    connection_status_changed = pyqtSignal(str, str) # (text_status, state_level: "connected"/"warning"/"disconnected")
    sensor_data_received = pyqtSignal(str, float, bool) # (sensor_id, temp_celsius, is_fault)
    log_emitted = pyqtSignal(str, str, int, str) # (timestamp, hex_frame, latency_ms, detail)

    def __init__(self, config_loader):
        super().__init__()
        self.config_loader = config_loader
        self.port = ""
        self.baudrate = 115200
        self.slave_id = self.config_loader.slave_id
        self.is_running = False
        self.is_connected = False
        self.write_queue = queue.Queue()
        self.serial_handle = None

    def set_connection_params(self, port, baudrate=115200, slave_id=1):
        self.port = port
        self.baudrate = baudrate
        self.slave_id = slave_id

    def request_write_actor(self, holding_reg, duty_percent):
        self.write_queue.put((holding_reg, duty_percent))

    def stop(self):
        self.is_running = False
        self.wait()

    def run(self):
        self.is_running = True
        import serial
        from pymodbus.client import ModbusSerialClient

        client = ModbusSerialClient(
            port=self.port,
            baudrate=self.baudrate,
            timeout=1.0,
            parity='N',
            stopbits=1,
            bytesize=8
        )

        if not client.connect():
            self.connection_status_changed.emit("[✗] DISCONNECTED", "disconnected")
            self.log_emitted.emit(time.strftime("%H:%M:%S"), "", 0, f"Failed to open serial port '{self.port}'")
            return

        self.is_connected = True
        self.connection_status_changed.emit("[✓] CONNECTED", "connected")
        self.log_emitted.emit(time.strftime("%H:%M:%S"), "", 0, f"Connected to '{self.port}' (Slave ID: {self.slave_id})")

        last_poll_time = 0
        poll_interval = self.config_loader.sensor_defaults.get("poll_interval_ms", 250) / 1000.0

        while self.is_running:
            now = time.time()

            # 1. Process pending write requests from GUI sliders/spinboxes
            while not self.write_queue.empty():
                try:
                    reg, val = self.write_queue.get_nowait()
                    t0 = time.time()
                    res = _write_register(client, reg, val, self.slave_id)
                    latency = int((time.time() - t0) * 1000)

                    if res.isError():
                        self.log_emitted.emit(time.strftime("%H:%M:%S"), f"FC06 Reg:{reg} Val:{val}", latency, "Write Error")
                        self.connection_status_changed.emit("[⚠] WARNING (TIMEOUT)", "warning")
                    else:
                        self.log_emitted.emit(time.strftime("%H:%M:%S"), f"FC06 Reg:{reg} Val:{val}", latency, "OK")
                except Exception as e:
                    self.log_emitted.emit(time.strftime("%H:%M:%S"), "", 0, f"Write exception: {e}")

            # 2. Periodic Sensor Polling
            if now - last_poll_time >= poll_interval:
                last_poll_time = now

                sensors = self.config_loader.sensors
                for s in sensors:
                    sensor_id = s.get("id")
                    input_reg = s.get("modbus_input_reg", 0)

                    t0 = time.time()
                    try:
                        res = _read_input_registers(client, input_reg, 1, self.slave_id)
                        latency = int((time.time() - t0) * 1000)

                        if res.isError():
                            self.sensor_data_received.emit(sensor_id, -1.0, True)
                            self.log_emitted.emit(time.strftime("%H:%M:%S"), f"FC04 Reg:{input_reg}", latency, "Read Error")
                            self.connection_status_changed.emit("[⚠] WARNING (TIMEOUT)", "warning")
                        else:
                            raw_val = res.registers[0]
                            # Convert 16-bit signed integer
                            if raw_val > 32767:
                                raw_val -= 65536
                            
                            is_fault = (raw_val <= -10)
                            temp_c = raw_val / 10.0 if not is_fault else -1.0

                            self.sensor_data_received.emit(sensor_id, temp_c, is_fault)
                            self.connection_status_changed.emit("[✓] CONNECTED", "connected")
                            self.log_emitted.emit(
                                time.strftime("%H:%M:%S"), 
                                f"FC04 Reg:{input_reg} Val:{raw_val}", 
                                latency, 
                                "ERR" if is_fault else f"{temp_c:.1f} °C"
                            )
                    except Exception as e:
                        self.sensor_data_received.emit(sensor_id, -1.0, True)
                        self.connection_status_changed.emit("[⚠] WARNING (TIMEOUT)", "warning")
                        self.log_emitted.emit(time.strftime("%H:%M:%S"), "", 0, f"Poll Exception: {e}")

            time.sleep(0.01)

        client.close()
        self.is_connected = False
        self.connection_status_changed.emit("[✗] DISCONNECTED", "disconnected")
        self.log_emitted.emit(time.strftime("%H:%M:%S"), "", 0, "Serial connection closed")
