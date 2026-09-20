"""ESP32 Serial Client."""
import serial
from smart_parking.application.ports.serial_port import SerialPort

class ESP32Client(SerialPort):
    def __init__(self, port: str = "COM3", baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None

    def send_command(self, cmd_type: str, payload: dict) -> bool:
        return True