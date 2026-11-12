import argparse
import csv
import json
import math
import platform
import resource
import statistics
import time
from common import project_path
from model_runtime import Model, linear_predict


def summary(values):
    values = sorted(values)
    return {"n": len(values), "median_ms": statistics.median(values),
            "p95_ms": values[max(0, math.ceil(0.95 * len(values)) - 1)]}


def measure(function, cases, iterations):
    for i in range(200):
        function(cases[i % len(cases)])
    durations = []
    cpu_start, wall_start = time.process_time(), time.perf_counter()
    for i in range(iterations):
        start = time.perf_counter_ns()
        function(cases[i % len(cases)])
        durations.append((time.perf_counter_ns() - start) / 1e6)
    cpu = time.process_time() - cpu_start
    wall = time.perf_counter() - wall_start
    return {**summary(durations), "cpu_seconds": cpu, "wall_seconds": wall,
            "one_core_cpu_percent": 100 * cpu / wall}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="models/temperature_model.json")
    parser.add_argument("--runtime", default="data/runtime.csv")
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--output", default="data/benchmark.json")
    args = parser.parse_args()
    if not 100 <= args.iterations <= 100000:
        raise SystemExit("Use 100 to 100000 iterations.")
    path = project_path(args.model)
    start = time.perf_counter_ns()
    model = Model(path)
    load_ms = (time.perf_counter_ns() - start) / 1e6
    cases = json.loads(path.with_suffix(".cases.json").read_text())
    features = [case["features"] for case in cases]
    if not features:
        raise SystemExit("No benchmark cases. Recreate the model and its .cases.json file.")
    result = {"platform": platform.platform(), "python": platform.python_version(),
              "model_id": model.data["model_id"], "model_bytes": path.stat().st_size,
              "model_load_ms_one_run": load_ms,
              "persistence": measure(lambda x: x[0], features, args.iterations),
              "ridge_arithmetic_only": measure(lambda x: linear_predict(model.data, x), features, args.iterations)}
    # Linux reports KiB; macOS reports bytes. This is a process high-water mark, NOT model-only RAM.
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result["process_peak_rss_mib"] = peak / (1024**2 if platform.system() == "Darwin" else 1024)
    runtime = project_path(args.runtime)
    if runtime.exists():
        with runtime.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if rows:
            last_run = rows[-1]["run_id"]
            rows = [r for r in rows if r["run_id"] == last_run]
            result["last_station_run"] = last_run
            result["last_station_source"] = rows[-1]["source"]
            result["local_sample_path"] = summary([float(r["local_path_ms"]) for r in rows])
    result["scope"] = ("Model timing excludes sensor IO and training. Local sample path includes sensor read, "
                       "features/inference, LED update where enabled, SQLite commit and MQTT enqueue where enabled. "
                       "It excludes sample waiting, broker delivery, browser refresh and runtime CSV logging. "
                       "CPU time is NOT energy; measure watts with suitable hardware.")
    out = project_path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
