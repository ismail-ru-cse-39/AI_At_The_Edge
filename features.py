from collections import deque
from statistics import mean

WINDOW_SIZE = 5
FEATURE_NAMES = ["temperature_c", "humidity_pct", "pressure_hpa",
                 "temperature_mean5_c", "humidity_mean5_pct", "temperature_delta5_c"]


def feature_vector(rows):
    if len(rows) != WINDOW_SIZE or not all(row["valid"] for row in rows):
        raise ValueError("Five valid readings are required")
    last = rows[-1]
    return [last["temperature_c"], last["humidity_pct"], last["pressure_hpa"],
            mean(row["temperature_c"] for row in rows),
            mean(row["humidity_pct"] for row in rows),
            last["temperature_c"] - rows[0]["temperature_c"]]


def continuous(previous, current):
    """Do not join readings across a restart, clock reversal, long gap or calibration change."""
    gap = current["observed_epoch"] - previous["observed_epoch"]
    interval = current["sample_interval_s"]
    return (gap > 0
            and previous["station_id"] == current["station_id"]
            and previous["temperature_offset_c"] == current["temperature_offset_c"]
            and previous["run_id"] == current["run_id"]
            and previous["source"] == current["source"]
            and previous["calibration_id"] == current["calibration_id"]
            and previous["sample_interval_s"] == interval
            and abs(gap - interval) <= 1.5)


class FeatureWindow:
    def __init__(self):
        self.rows = deque(maxlen=WINDOW_SIZE)

    def push(self, row):
        """Use only the past and present; invalid data starts the window again."""
        if not row["valid"]:
            self.rows.clear()
            return None
        if self.rows and not continuous(self.rows[-1], row):
            self.rows.clear()
        self.rows.append(row)
        return feature_vector(list(self.rows)) if len(self.rows) == WINDOW_SIZE else None
