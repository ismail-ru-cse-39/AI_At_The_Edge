"""Week 2: run one station process. Ctrl+C stops it safely."""
import argparse
import fcntl
import json
import time
import uuid
from common import ROOT, load_config, observation, project_path
from sensors import Sensor
from storage import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--simulate", action="store_true", help="Explicitly use labelled fake readings")
    parser.add_argument("--samples", type=int, default=0, help="Stop after N samples; 0 means keep running")
    parser.add_argument("--fault-every", type=int, default=0, help="Simulation only: invalidate every Nth reading")
    args = parser.parse_args()
    if args.samples < 0 or args.fault_every < 0 or (args.fault_every and not args.simulate):
        raise SystemExit("Counts cannot be negative; --fault-every requires --simulate.")
    config = load_config(args.config)
    database = project_path(config["database"])
    if args.simulate and "sim" not in database.stem:
        raise SystemExit("Simulation needs config_sim.json and a database name containing 'sim'.")
    store = Store(database)
    lockfile = ROOT / "data" / "station.lock"
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    lock = lockfile.open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Another station.py is running here. Stop it with Ctrl+C first.")
    sensor = Sensor(simulated=args.simulate)
    publisher = None
    run_id = uuid.uuid4().hex[:12]
    sequence = 0
    latest = None

    # A monotonic clock schedules readings without wall-clock jumps.
    next_sample = time.monotonic()
    last_purge = 0
    try:
        while True:
            now = time.monotonic()
            if now - last_purge > 3600:
                store.purge(config["retention_days"])
                last_purge = now
            if now >= next_sample:
                values, error = sensor.read(config["temperature_offset_c"])
                sequence += 1
                if args.fault_every and sequence % args.fault_every == 0:
                    values["temperature_c"] = None
                row = observation(config, values, run_id, sequence, time.time(), sensor.source, error)
                # Save locally before attempting any network transmission.
                store.add(row)
                if publisher:
                    publisher.publish(row)
                latest = row
                print(json.dumps(row, allow_nan=False))
                if args.samples and sequence >= args.samples:
                    break
                next_sample += config["sample_interval_s"]
                if next_sample <= time.monotonic():
                    # Skip missed deadlines instead of creating a burst of old samples.
                    next_sample = time.monotonic() + config["sample_interval_s"]
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Station stopped. Saved readings remain in the database.")
    finally:
        try:
            sensor.close()
        finally:
            if publisher:
                publisher.close()
            lock.close()


if __name__ == "__main__":
    main()
