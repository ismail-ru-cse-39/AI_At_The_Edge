import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MEASUREMENTS = ("temperature_c", "humidity_pct", "pressure_hpa")
# These are deliberately broad project checks, NOT manufacturer specifications.
BOUNDS = {"temperature_c": (-20, 60), "humidity_pct": (0, 100),
          "pressure_hpa": (850, 1100)}


def project_path(value):
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def load_config(filename="config.json"):
    path = project_path(filename)
    if not path.exists():
        raise SystemExit(f"Missing {path}. Create config.json using the Week 2 steps first.")
    config = json.loads(path.read_text(encoding="utf-8"))
    if not re.fullmatch(r"[a-z][a-z0-9_-]{2,31}", config["station_id"]):
        raise SystemExit("Use a station ID such as station01: lower-case letters, digits, _ or -.")
    interval = config["sample_interval_s"]
    if isinstance(interval, bool) or not isinstance(interval, (float, int)) or not 1 <= interval <= 60:
        raise SystemExit("sample_interval_s must be a number from 1 to 60.")
    offset = config["temperature_offset_c"]
    if not finite_number(offset) or abs(offset) > 10:
        raise SystemExit("Check temperature_offset_c; use 0 until calibration is justified.")
    if type(config["retention_days"]) is not int or not 1 <= config["retention_days"] <= 30:
        raise SystemExit("Project retention_days must be from 1 to 30; choose a justified value.")
    port = config.get("broker_port", 1883)
    if type(port) is not int or not 1 <= port <= 65535:
        raise SystemExit("broker_port must be an integer from 1 to 65535.")
    return config


def utc_string(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def clean_values(values):
    """Keep usable numbers; record why a missing or implausible value was rejected."""
    clean, errors = {}, []
    for field in MEASUREMENTS:
        value = values.get(field)
        low, high = BOUNDS[field]
        if not finite_number(value) or not low <= value <= high:
            clean[field] = None  # Missing is not the same as zero.
            errors.append(f"{field}: missing or outside project bounds")
        else:
            clean[field] = float(value)
    return clean, errors


def observation(config, values, run_id, sequence, epoch, source, error=None):
    """Package one reading with its identity, time, units and data-quality evidence."""
    clean, errors = clean_values(values)
    if error:
        errors.append(error)
    raw_temperature = values.get("temperature_raw_c")
    return {
        "schema_version": 1, "station_id": config["station_id"],
        "run_id": run_id, "sample_id": f"{run_id}:{sequence}",
        "observed_at": utc_string(epoch), "observed_epoch": epoch,
        "sample_interval_s": config["sample_interval_s"], "source": source,
        "calibration_id": config["calibration_id"],
        "temperature_offset_c": config["temperature_offset_c"],
        "temperature_raw_c": raw_temperature if finite_number(raw_temperature) else None,
        **clean, "valid": not errors, "errors": errors,
    }


def validate_observation(row, expected_station=None):
    """Reject malformed network/file input before storing or using it."""
    if not isinstance(row, dict) or row.get("schema_version") != 1:
        raise ValueError("Unknown observation format")
    station = row.get("station_id", "")
    if not isinstance(station, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{2,31}", station):
        raise ValueError("Invalid station ID")
    if expected_station is not None and station != expected_station:
        raise ValueError("Topic and station ID do not match")
    for field in ("run_id", "sample_id", "observed_at", "calibration_id"):
        if not isinstance(row.get(field), str) or not 1 <= len(row[field]) <= 120:
            raise ValueError(f"Invalid {field}")
    epoch = row.get("observed_epoch")
    if not finite_number(epoch) or not 0 < epoch < 4102444800:
        raise ValueError("Invalid timestamp")
    stamp = datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00"))
    if stamp.tzinfo is None or abs(stamp.timestamp() - epoch) > 0.01:
        raise ValueError("Timestamp fields disagree or timezone is missing")
    if row.get("source") not in ("sense_hat", "simulated"):
        raise ValueError("Unknown sensor source")
    interval = row.get("sample_interval_s")
    if not finite_number(interval) or not 1 <= interval <= 60:
        raise ValueError("Invalid sampling interval")
    if type(row.get("valid")) is not bool or not isinstance(row.get("errors"), list):
        raise ValueError("Missing data-quality flag")
    if any(not isinstance(e, str) or len(e) > 250 for e in row["errors"]):
        raise ValueError("Invalid error description")
    _, errors = clean_values(row)
    if row["valid"] and (errors or row["errors"]):
        raise ValueError("A valid observation contains invalid measurements")
    for field in MEASUREMENTS:
        if row.get(field) is not None and not finite_number(row[field]):
            raise ValueError("Use null, not NaN, infinity or strings, for a failed measurement")
    offset = row.get("temperature_offset_c")
    if not finite_number(offset) or abs(offset) > 10:
        raise ValueError("Invalid calibration offset")
    if not row["valid"] and not row["errors"]:
        raise ValueError("An invalid observation needs a reason")
    return row