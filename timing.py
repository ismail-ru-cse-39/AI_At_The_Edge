import csv
from common import ROOT


def append_runtime(row, duration):
    path = ROOT / "data" / "runtime.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Bound diagnostic files to approximately 2 MB total; not indefinite logging.
    if path.exists() and path.stat().st_size > 1000000:
        path.replace(path.with_name("runtime.previous.csv"))
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if new:
            writer.writerow(["run_id", "sample_id", "source", "local_path_ms"])
        writer.writerow([row["run_id"], row["sample_id"], row["source"], duration])
