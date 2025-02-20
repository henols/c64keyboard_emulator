import serial
import serial.tools.list_ports
import threading
import time
import logging


BAUD = 19200
RECONNECT_DELAY = 5  # seconds


class SerialConnection:
    def __init__(self, path=None, callback=None):
        self.log = logging.getLogger("SerialConnection")
        self.log.addHandler(self.create_debug_console_handler())
        self.log.setLevel(logging.DEBUG)
        self.log.debug(f"Creating serial connection: {path}")

        self.callback = callback

        self.connected = False
        self.connection_path = path
        self.monitor_thread = threading.Thread(target=self.monitor_connection)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def _connect(self, path=None):
        if path:
            self.connection_path = path
        connect = False
        for p in serial.tools.list_ports.comports():
            # self.log.debug(f"Device: {p.device} ; Description: {p.description}")
            if p.device == self.connection_path:
                connect = True
                break

        if not connect:
            self.log.debug(f"Device {self.connection_path} not found")
            return None

        try:
            self.serial_connection = serial.Serial(self.connection_path, BAUD, timeout=0.1)

            self.serial_connection.write((3).to_bytes(1, byteorder="big"))
            self.serial_connection.write(b"cbm")
            self.serial_connection.flush()
            time.sleep(1)
            # time.sleep(4)
            while True:
                line = self.serial_connection.readline()
                if not line:
                    return
                line = line.decode("utf-8").strip()
                self.log.debug(f"Received: {line}")
                if line == "c64":
                    self.connected = True
                    break
        except serial.SerialException as e:
            self.log.debug(f"Cannot open serial device {self.connection_path}")
            raise e

        if self.connected:
            self.post_event("connected")

    def _disconnect(self):
        self.connected = False
        if self.serial_connection:
            self.serial_connection.close()
        self.post_event("disconnected")

    def connect(self):
        if not (self.connected or self.connection_path):
            return

        self.log.debug(f"Attempting to reconnect to {self.connection_path}...")
        if not self.connected:
            try:
                self._connect()
                if self.connected:
                    self.log.info(f"Connected to {self.connection_path}")

            except serial.SerialException:
                self.log.debug(f"Connection failed.")

    def set_serial(self, path=None):
        self.connection_path = path
        if self.connected:
            self._disconnect()
        self.connect()

    def send_data(self, data):
        try:
            if self.connected and data:
                self.serial_connection.write(bytearray([len(data)]) )
                sent = self.serial_connection.write(data)
                self.log.debug(f"Data len {len(data)} Sent {sent} bytes")
                self.serial_connection.flush()
                return sent
        except serial.SerialException:
            self._disconnect()
        return 0

    def readline(self):
        try:
            if self.connected:
                return self.serial_connection.readline()
        except serial.SerialException:
            self._disconnect()
        return None

    def close(self):
        if self.connected:
            self.serial_connection.close()
            self.connected = False
            self.post_event("disconnected")

    def is_connected(self):
        return self.connected

    def flush(self):
        try:
            if self.connected:
                self.serial_connection.flush()
        except serial.SerialException:
            self._disconnect()

    def post_event(self, event_type):
        if self.callback:
            event = {"type": event_type, "path": self.connection_path}
            self.monitor_thread = threading.Thread(target=self.callback(event))
            self.monitor_thread.start()

            # self.callback(event)

    def monitor_connection(self):
        while self.monitor_thread.daemon:
            if self.connected:
                ports = [p.device for p in serial.tools.list_ports.comports()]
                if self.connection_path not in ports:
                    self.log.debug(f"Port {self.connection_path} disappeared")
                    self.connected = False
                    self.post_event("disconnected")
            else:
                self.connect()
            time.sleep(1)

    def create_debug_console_handler(self):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)
        return console_handler
