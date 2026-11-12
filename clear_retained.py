import threading
from common import load_config
from mqtt_link import make_client

config = load_config()
answer = input(f"Station stopped? Type {config['station_id']} to clear its retained broker data: ")
if answer != config["station_id"]:
    raise SystemExit("Cancelled; nothing changed.")
client = make_client(config, "cleanup")
ready = threading.Event()

def connected(client, userdata, flags, reason_code, properties):
    if not reason_code.is_failure:
        ready.set()

client.on_connect = connected
client.connect_async(config["broker_host"], config["broker_port"], 30)
client.loop_start()
try:
    if not ready.wait(15):
        raise SystemExit("Broker unavailable; do not claim broker deletion succeeded.")
    for suffix in ("telemetry", "status"):
        info = client.publish(f"weather/{config['station_id']}/{suffix}", b"", qos=1, retain=True)
        info.wait_for_publish(timeout=5)
        if not info.is_published():
            raise SystemExit("Deletion not acknowledged. Check the broker and retry.")
    print("Broker acknowledged empty retained values. Verify with a new subscription; remove archives and exports separately.")
finally:
    client.disconnect()
    client.loop_stop()