import json
import tempfile
import time
import unittest
from pathlib import Path
from common import clean_values, observation, validate_observation
from storage import Store

CONFIG = {"station_id": "station01", "sample_interval_s": 5,
          "calibration_id": "uncalibrated", "temperature_offset_c": 0}

def reading(sequence=0, temperature=24, epoch=None):
    return observation(CONFIG, {"temperature_c": temperature, "humidity_pct": 50,
                               "pressure_hpa": 1013}, "test-run", sequence,
                       epoch if epoch is not None else time.time(), "simulated")

class CoreTests(unittest.TestCase):
    def test_zero_humidity_is_not_missing(self):
        clean, errors = clean_values({"temperature_c": 20, "humidity_pct": 0, "pressure_hpa": 1000})
        self.assertEqual(clean["humidity_pct"], 0)
        self.assertFalse(errors)

    def test_nonfinite_and_missing_are_null(self):
        clean, errors = clean_values({"temperature_c": float("nan"), "humidity_pct": 50})
        self.assertIsNone(clean["temperature_c"])
        self.assertIsNone(clean["pressure_hpa"])
        self.assertEqual(len(errors), 2)
        json.dumps(clean, allow_nan=False)

    def test_valid_schema_and_topic(self):
        row = reading()
        self.assertIs(validate_observation(row, "station01"), row)
        with self.assertRaises(ValueError):
            validate_observation(row, "station02")

    def test_false_quality_claim_rejected(self):
        row = reading()
        row["temperature_c"] = None
        with self.assertRaises(ValueError):
            validate_observation(row)

    def test_timestamp_mismatch_rejected(self):
        row = reading()
        row["observed_epoch"] += 100
        with self.assertRaises(ValueError):
            validate_observation(row)

    def test_storage_deduplicates_and_purges(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "test.db")
            row = reading()
            self.assertTrue(store.add(row))
            self.assertFalse(store.add(row))
            self.assertEqual(len(store.rows()), 1)
            store.add(reading(sequence=1, epoch=time.time() - 8 * 86400))
            self.assertEqual(store.purge(7), 1)
            self.assertEqual(len(store.rows()), 1)

    def test_control_value_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "test.db")
            self.assertEqual(store.get("mute_until", 0), 0)
            store.set("mute_until", 123)
            self.assertEqual(store.get("mute_until"), 123)

if __name__ == "__main__":
    unittest.main()