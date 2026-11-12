import json
import tempfile
import unittest
from pathlib import Path
from features import FEATURE_NAMES
from model_runtime import Model, linear_predict
from test_core import reading

class ModelTests(unittest.TestCase):
    def fixture(self):
        return {"format_version": 1, "feature_names": FEATURE_NAMES, "model_id": "test",
                "station_id": "station01", "source": "simulated", "calibration_id": "uncalibrated",
                "temperature_offset_c": 0.0, "sample_interval_s": 5, "horizon_s": 60, "coefficients": [1, 0, 0, 0, 0, 0],
                "intercept": 0, "mean": [0] * 6, "scale": [1] * 6,
                "training_min": [-20, 0, 850, -20, 0, -10],
                "training_max": [60, 100, 1100, 60, 100, 10]}

    def test_json_prediction_and_source_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "model.json"
            path.write_text(json.dumps(self.fixture()))
            model = Model(path)
            row = reading()
            features = [24, 50, 1013, 24, 50, 0]
            self.assertEqual(model.infer(row, features)["prediction_c"], 24)
            row["source"] = "sense_hat"
            self.assertIsNone(model.infer(row, features)["prediction_c"])

    def test_training_range_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "model.json"
            model_data = self.fixture()
            model_data["training_max"][0] = 23
            path.write_text(json.dumps(model_data))
            model = Model(path)
            self.assertIsNone(model.infer(reading(), [24, 50, 1013, 24, 50, 0])["prediction_c"])

    def test_bad_feature_order_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "model.json"
            model = self.fixture()
            model["feature_names"] = list(reversed(FEATURE_NAMES))
            path.write_text(json.dumps(model))
            with self.assertRaises(ValueError):
                Model(path)

if __name__ == "__main__":
    unittest.main()
