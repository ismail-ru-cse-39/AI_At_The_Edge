import argparse
import time
from common import load_config, observation, project_path
from sensors import Sensor
from storage import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--output", default="data/demo.db")
    parser.add_argument("--samples", type=int, default=1800)
    args = parser.parse_args()
    if not 600 <= args.samples <= 20000:
        raise SystemExit("Use 600 to 20000 samples.")
    config = load_config(args.config)
    config["sample_interval_s"] = 5
    output = project_path(args.output)
    if output.exists():
        raise SystemExit("Output already exists. Choose another filename; nothing has been overwritten.")
    sensor = Sensor(simulated=True, seed=7)
    store = Store(output)
    start = time.time() - args.samples * 5
    for index in range(args.samples):
        values, error = sensor.read(config["temperature_offset_c"])
        row = observation(config, values, "demo-seed7", index, start + index * 5, sensor.source, error)
        store.add(row)
    print(f"Created {args.samples} SIMULATED observations in {output}.")
    print("This is a software test dataset, not weather measurements or evidence of field accuracy.")


if __name__ == "__main__":
    main()