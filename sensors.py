import math
import random


class Sensor:
    def __init__(self, simulated=False, seed=7):
        self.simulated = simulated
        self.source = "simulated" if simulated else "sense_hat"
        self.random = random.Random(seed)
        self.sequence = 0
        self.hat = None
        if not simulated:
            try:
                from sense_hat import SenseHat
                self.hat = SenseHat()
                self.hat.low_light = True
            except (ImportError, OSError, RuntimeError) as exc:
                raise SystemExit("Sense HAT unavailable. Stop, check the installation and reboot. "
                                 "Use --simulate only when deliberately testing simulated data.") from exc

    def read(self, offset=0.0):
        self.sequence += 1
        try:
            if self.simulated:
                x = self.sequence
                temperature = 25 + 6 * math.sin(x / 30) + self.random.gauss(0, 0.12)
                humidity = 58 + 20 * math.sin(x / 45) + self.random.gauss(0, 0.3)
                pressure = 1012 + 3 * math.sin(x / 90) + self.random.gauss(0, 0.04)
            else:
                temperature = self.hat.get_temperature()
                humidity = self.hat.get_humidity()
                pressure = self.hat.get_pressure()
            return {"temperature_raw_c": temperature, "temperature_c": temperature + offset,
                    "humidity_pct": humidity, "pressure_hpa": pressure}, None
        except (OSError, RuntimeError, ValueError) as exc:
            return {}, f"Sensor read failed: {type(exc).__name__}"

    def close(self):
        if self.hat:
            self.hat.clear()