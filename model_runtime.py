import json
import math
from pathlib import Path
from common import finite_number
from features import FEATURE_NAMES


def linear_predict(model, features):
    return model["intercept"] + sum(
        coefficient * (value - centre) / scale
        for value, coefficient, centre, scale in zip(
            features, model["coefficients"], model["mean"], model["scale"], strict=True))


def in_training_range(model, features):
    return all(low - 1e-9 <= value <= high + 1e-9 for value, low, high in
               zip(features, model["training_min"], model["training_max"], strict=True))


class Model:
    def __init__(self, filename):
        path = Path(filename)
        if path.stat().st_size > 65536:
            raise ValueError("Model file unexpectedly large")
        self.data = json.loads(path.read_text(encoding="utf-8"))
        m = self.data
        if m["format_version"] != 1 or m["feature_names"] != FEATURE_NAMES:
            raise ValueError("Model format or feature order does not match this program")
        for field in ("station_id", "calibration_id", "model_id"):
            if not isinstance(m.get(field), str) or not 1 <= len(m[field]) <= 120:
                raise ValueError(f"Invalid model provenance: {field}")
        if m.get("source") not in ("sense_hat", "simulated"):
            raise ValueError("Model source is missing or unknown")
        if not finite_number(m.get("temperature_offset_c")):
            raise ValueError("Model calibration offset is missing or invalid")
        if m["horizon_s"] != 60 or m["sample_interval_s"] != 5:
            raise ValueError("This runtime expects a 60-second model sampled every 5 seconds")
        for field in ("coefficients", "mean", "scale", "training_min", "training_max"):
            if len(m[field]) != len(FEATURE_NAMES) or not all(finite_number(v) for v in m[field]):
                raise ValueError(f"Invalid model numbers: {field}")
        if not finite_number(m["intercept"]) or any(s <= 0 for s in m["scale"]):
            raise ValueError("Invalid model intercept or scale")
        if any(lo > hi for lo, hi in zip(m["training_min"], m["training_max"], strict=True)):
            raise ValueError("Reversed training bounds")

    def infer(self, row, features):
        if features is None or not row["valid"]:
            return {"prediction_c": None, "why": "Waiting for valid history."}
        if len(features) != len(FEATURE_NAMES) or not all(finite_number(x) for x in features):
            return {"prediction_c": None, "why": "Invalid feature vector; model abstains."}
        for field in ("station_id", "source", "calibration_id", "sample_interval_s", "temperature_offset_c"):
            if row[field] != self.data[field]:
                return {"prediction_c": None, "why": f"Model/measurement mismatch: {field}."}
        if not in_training_range(self.data, features):
            return {"prediction_c": None, "why": "Outside observed training feature ranges; model abstains."}
        prediction = linear_predict(self.data, features)
        if not math.isfinite(prediction) or not -20 <= prediction <= 60:
            return {"prediction_c": None, "why": "Implausible prediction; model abstains."}
        return {"prediction_c": prediction,
                "why": "Experimental 60-second local sensor-temperature forecast; not a weather warning.",
                "model_id": self.data["model_id"]}
