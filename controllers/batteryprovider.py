class BatteryProvider:
    def get_battery(self, controller) -> int | None:
        raise NotImplementedError