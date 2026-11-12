import argparse
import hashlib
import json
import platform
import time
import uuid
import numpy as np
import sklearn
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from common import load_config, project_path, utc_string, validate_observation
from features import FEATURE_NAMES, WINDOW_SIZE, continuous, feature_vector
from model_runtime import in_training_range, linear_predict
from storage import Store

HORIZON_STEPS = 12  # 12 * 5 seconds = 60 seconds.


def make_examples(rows):
    examples = []
    for i in range(WINDOW_SIZE - 1, len(rows) - HORIZON_STEPS):
        start, target = i - WINDOW_SIZE + 1, i + HORIZON_STEPS
        segment = rows[start:target + 1]
        if not all(r["valid"] and r["sample_interval_s"] == 5 for r in segment):
            continue
        if not all(continuous(a, b) for a, b in zip(segment, segment[1:])):
            continue
        examples.append({"start": start, "target": target,
                         "features": feature_vector(rows[start:i + 1]),
                         "actual_c": rows[target]["temperature_c"]})
    return examples


def partition(examples, total):
    """Keep the full input-and-target span inside one chronological data partition."""
    # Full feature+target spans stay inside their partition: no overlapping raw samples.
    first, second = int(total * 0.6), int(total * 0.8)
    train = [e for e in examples if e["target"] < first]
    validation = [e for e in examples if e["start"] >= first and e["target"] < second]
    test = [e for e in examples if e["start"] >= second]
    return train, validation, test


def errors(actual, predicted):
    differences = np.asarray(predicted) - np.asarray(actual)
    return {"mae_c": float(np.mean(np.abs(differences))),
            "rmse_c": float(np.sqrt(np.mean(differences ** 2)))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--database", help="Override the configured database, e.g. data/demo.db")
    parser.add_argument("--source", choices=["sense_hat", "simulated"], default="sense_hat")
    parser.add_argument("--output", default="models/temperature_model.json")
    args = parser.parse_args()
    config = load_config(args.config)
    database = project_path(args.database or config["database"])
    if not database.exists():
        raise SystemExit("Dataset does not exist; collect or transfer it first.")
    rows = [r for r in Store(database).rows(config["station_id"]) if r["source"] == args.source]
    for row in rows:
        validate_observation(row, config["station_id"])
    if len(rows) < 600:
        raise SystemExit("Need at least 600 observations (50 minutes at 5-second sampling).")
    if ({r["calibration_id"] for r in rows} != {config["calibration_id"]}
            or {r["temperature_offset_c"] for r in rows} != {config["temperature_offset_c"]}):
        raise SystemExit("Do not mix calibration versions. Select a consistent dataset/configuration.")
    examples = make_examples(rows)
    train, validation, test = partition(examples, len(rows))
    if min(map(len, (train, validation, test))) < 40:
        raise SystemExit("Too few continuous examples in a partition. Collect more uninterrupted data.")
    X = np.asarray([e["features"] for e in train])
    y = np.asarray([e["actual_c"] for e in train])
    Xv = np.asarray([e["features"] for e in validation])
    yv = np.asarray([e["actual_c"] for e in validation])
    scaler = StandardScaler().fit(X)  # Fit ONLY on training inputs.
    trials = []
    for alpha in (0.1, 1.0, 10.0, 100.0):
        model = Ridge(alpha=alpha).fit(scaler.transform(X), y)
        mae = errors(yv, model.predict(scaler.transform(Xv)))["mae_c"]
        trials.append((mae, alpha, model))
    validation_mae, alpha, fitted = min(trials, key=lambda entry: entry[0])
    fingerprint = hashlib.sha256(json.dumps(rows, sort_keys=True, allow_nan=False).encode()).hexdigest()
    exported = {
        "format_version": 1, "model_id": uuid.uuid4().hex[:12], "created_at": utc_string(time.time()),
        "station_id": config["station_id"], "source": args.source,
        "calibration_id": config["calibration_id"],
        "temperature_offset_c": config["temperature_offset_c"], "sample_interval_s": 5, "horizon_s": 60,
        "feature_names": FEATURE_NAMES, "coefficients": fitted.coef_.tolist(),
        "intercept": float(fitted.intercept_), "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
        "training_min": X.min(axis=0).tolist(), "training_max": X.max(axis=0).tolist(),
        "alpha": alpha, "dataset_sha256": fingerprint,
        "purpose": "Teaching only: forecast this station's local sensor temperature, in shadow mode."
    }
    Xt = [e["features"] for e in test]
    yt = [e["actual_c"] for e in test]
    predictions = [linear_predict(exported, x) for x in Xt]
    # Check that the deployed JSON maths reproduces the training library's maths.
    if not np.allclose(predictions, fitted.predict(scaler.transform(Xt)), atol=1e-9):
        raise RuntimeError("Export/runtime mismatch")
    accepted = [i for i, x in enumerate(Xt) if in_training_range(exported, x)]
    report = {
        "source": args.source, "station_id": config["station_id"],
        "raw_observations": len(rows), "examples": len(examples),
        "train_examples": len(train), "validation_examples": len(validation), "test_examples": len(test),
        "validation_trials": [{"alpha": a, "mae_c": m} for m, a, _ in trials],
        "selected_alpha": alpha, "selected_validation_mae_c": validation_mae,
        "test_persistence_all": errors(yt, [x[0] for x in Xt]),
        "test_ridge_all_before_guard": errors(yt, predictions),
        "test_guard_coverage": len(accepted) / len(test),
        "test_ridge_accepted_only": errors([yt[i] for i in accepted], [predictions[i] for i in accepted]) if accepted else None,
        "test_persistence_on_same_accepted_cases": errors([yt[i] for i in accepted], [Xt[i][0] for i in accepted]) if accepted else None,
        "python": platform.python_version(), "numpy": np.__version__, "sklearn": sklearn.__version__,
        "warning": "Chronological holdout, not independent field validation. Adjacent errors remain correlated."
    }
    out = project_path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        backup = out.with_suffix(".previous.json")
        backup.write_bytes(out.read_bytes())
        print("Previous model backed up to", backup)
    out.write_text(json.dumps(exported, indent=2), encoding="utf-8")
    out.with_suffix(".report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    out.with_suffix(".cases.json").write_text(json.dumps(test, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("Model:", out)
    print("A worse ML result is a valid result. Do not retune on this test partition.")


if __name__ == "__main__":
    main()
