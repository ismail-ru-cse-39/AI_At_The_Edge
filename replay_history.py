import argparse
import json
import threading
from common import load_config, project_path
from mqtt_link import make_client
from storage import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    config = load_config(args.config)
    store = Store(project_path(config["database"]))
    store.purge(config["retention_days"])
    client = make_client(config, "history")
    ready = threading.Event()

    def connected(client, userdata, flags, reason_code, properties):
        if not reason_code.is_failure:
            ready.set()

    client.on_connect = connected
    client.connect_async(config["broker_host"], config["broker_port"], keepalive=30)
    client.loop_start()
    count = 0
    try:
        if not ready.wait(15):
            raise SystemExit("No connection in 15 seconds. Check the broker.")
        for row in store.rows(config["station_id"]):
            info = client.publish(f"weather/{config['station_id']}/history",
                                  json.dumps(row, allow_nan=False), qos=1, retain=False)
            info.wait_for_publish(timeout=5)
            if not info.is_published():
                raise SystemExit("Replay interrupted. Rerun later; the PC ignores duplicate sample IDs.")
            count += 1
        print(count, "records acknowledged by the broker. Check the central PC's stored count too.")
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
