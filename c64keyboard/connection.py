import serial
import serial.tools.list_ports

BAUD = 19200


class SerialConnection:
    def __init__(self, path):
        print(f"Creating serial connection: {path}")
        self.connected = False
        self.path = path

    def connect(self):
        print(
            "\n".join(
                f"Device: {p.device} ; Description: {p.description}"
                for p in serial.tools.list_ports.comports()
            )
        )
        connect = False
        for p in serial.tools.list_ports.comports():
            if p.device == self.path:
                connect = True
                break

        if not connect:
            print(f"Device {self.path} not found")
            return None
        self.ser = serial.Serial(self.path, BAUD, timeout=0.1)
        self.connected = True

    def write(self, data):
        try:
            if self.connected:
                return self.ser.write(data)
        except serial.SerialException:
            self.connected = False

    def readline(self):
        try:
            if self.connected:
                return self.ser.readline()
        except serial.SerialException:
            self.connected = False
            return ""

    def close(self):
        if self.connected:
            self.ser.close()
            self.connected = False

    def is_connected(self):
        return self.connected

    def flush(self):
        try:
            if self.connected:
                self.ser.flush()
        except serial.SerialException:
            self.connected = False
