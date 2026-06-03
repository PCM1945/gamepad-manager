from enum import Enum

class ControllerType(Enum):
    XBOX = "Xbox"
    PLAYSTATION = "PlayStation"
    NINTENDO = "Nintendo"
    GAMESIR = "GameSir"
    UNKNOWN = "Unknown"

class ConnectionType(Enum):
    USB = "USB"
    BLUETOOTH = "Bluetooth"
    DONGLE = "Dongle"
    UNKNOWN = "Unknown"

class Controller:
    def __init__(self, name, ctype, connection, battery):
        self.name = name
        self.type = ctype
        self.connection = connection
        self.battery = battery  # int | None
