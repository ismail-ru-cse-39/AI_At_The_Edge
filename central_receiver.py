import argparse
import json
import queue
import time
from common import load_config, project_path, validate_observation
from storage import Store
from mqtt_link import make_client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config_pc.json")
    args = parser.parse_args()
    config = load_config(args.config)
    store = Store(project_path(config["database"]))
    incoming = queue.Queue(maxsize=256)
    client = make_client(config, "collector")

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print("Connection rejected:", reason_code)
            return
        for topic in (f"weather/{config['station_id']}/telemetry",
                      f"weather/{config['station_id']}/history",
                      f"weather/{config['station_id']}/status"):
            client.subscribe(topic, qos=1)
        print("Connected. Waiting for stations...")

    def on_message(client, userdata, message):
        if len(message.payload) > 16384:
            print("Rejected an oversized message.")
            return
        try:
            incoming.put_nowait((message.topic, message.payload))
        except queue.Full:
            print("Receiver queue full: message dropped. Recover history from the Pi.")

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_connect_fail = lambda client, userdata: print("Cannot reach broker; check the Pi address, broker and network.")
    client.connect_async(config["broker_host"], config["broker_port"], keepalive=30)
    client.loop_start()
    last_purge = 0
    try:
        while True:
            if time.monotonic() - last_purge > 3600:
                store.purge(config["retention_days"])
                last_purge = time.monotonic()
            try:
                topic, payload = incoming.get(timeout=1)
            except queue.Empty:
                continue
            try:
                parts = topic.split("/")
                if len(parts) != 3 or parts[0] != "weather" or parts[1] != config["station_id"]:
                    raise ValueError("Unexpected topic")
                if parts[2] == "status":
                    print(parts[1], "broker status:", payload.decode("utf-8"))
                    continue
                row = validate_observation(json.loads(payload.decode("utf-8")), parts[1])
                age = time.time() - row["observed_epoch"]
                if age < -5 or age > config["retention_days"] * 86400:
                    raise ValueError("Future-dated or beyond the archive retention period")
                inserted = store.add(row)
                freshness = "stale/history" if age > 15 else "recent"
                print(row["station_id"], row["observed_at"], freshness,
                      "saved" if inserted else "duplicate ignored", "valid:", row["valid"])
            except (ValueError, TypeError, KeyError, UnicodeError) as exc:
                print("Rejected message:", exc)
    except KeyboardInterrupt:
        print("Receiver stopped.")
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
