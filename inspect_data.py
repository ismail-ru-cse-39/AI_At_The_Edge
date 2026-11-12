import argparse
import csv
import json
from common import load_config, project_path
from storage import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--export", help="CSV destination, e.g. data/readings.csv")
    parser.add_argument("--purge", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    store = Store(project_path(config["database"]))
    if args.purge:
        print("Removed old database rows:", store.purge(config["retention_days"]))
    rows = store.rows(config["station_id"])
    print("Saved observations for this station:", len(rows))
    if rows:
        print(json.dumps(rows[-1], indent=2))
    if args.export:
        fields = ["station_id", "sample_id", "observed_at", "source", "valid", "calibration_id",
                  "temperature_raw_c", "temperature_c", "humidity_pct", "pressure_hpa"]
        out = project_path(args.export)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        print("Exported:", out)
        print("An export is another copy: include it in your deletion plan.")


if __name__ == "__main__":
    main()
