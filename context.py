from math import isfinite


def heat_index_c(temperature_c, humidity_pct):
    """Rothfusz regression within a deliberately restricted teaching domain.

    The domain excludes the NWS low/high-humidity adjustment cases.
    Outside it we return None, NOT the air temperature as a fake heat index.
    Source: National Weather Service, https://www.weather.gov/ctp/heat
    """
    if not all(isinstance(x, (int, float)) and isfinite(x)
               for x in (temperature_c, humidity_pct)):
        return None
    if not (27 <= temperature_c <= 40 and 40 <= humidity_pct <= 85):
        return None
    t = temperature_c * 9 / 5 + 32  # This published regression uses Fahrenheit.
    r = humidity_pct
    result_f = (-42.379 + 2.04901523*t + 10.14333127*r - 0.22475541*t*r
                - 0.00683783*t*t - 0.05481717*r*r + 0.00122874*t*t*r
                + 0.00085282*t*r*r - 0.00000199*t*t*r*r)
    return (result_f - 32) * 5 / 9


class ContextPolicy:
    def __init__(self):
        self.attention = False

    def update(self, row, features):
        if not row["valid"]:
            self.attention = False
            return {"state": "unknown", "why": "Invalid measurement; inspect the sensor.",
                    "heat_index_c": None}
        if features is None:
            self.attention = False
            return {"state": "warming_up", "why": "Collecting five consecutive valid readings.",
                    "heat_index_c": None}
        temperature, humidity = features[3], features[4]
        if temperature >= 28 or humidity >= 75:
            self.attention = True
        elif temperature <= 26 and humidity <= 70:
            self.attention = False
        state = "attention" if self.attention else "normal"
        why = (f"Five-reading means: {temperature:.1f} C and {humidity:.1f}% RH. "
               "Enter attention at 28 C or 75% RH; clear at 26 C AND 70% RH.")
        return {"state": state, "why": why,
                "heat_index_c": heat_index_c(temperature, humidity)}
