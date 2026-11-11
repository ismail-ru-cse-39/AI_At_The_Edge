import getpass
import json
import os
import uuid
import paho.mqtt.client as mqtt


def make_client(config, suffix):
    username = config["mqtt_username"]
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"{username}-{suffix}-{uuid.uuid4().hex[:8]}",
                         protocol=mqtt.MQTTv311)
    # Leave mqtt_username empty for the first, anonymous connection test.
    # A separate MQTT password can be enabled after that test; never reuse eduroam credentials.
    if username:
        password = os.environ.get("MQTT_PASSWORD") or getpass.getpass(f"MQTT password for {username}: ")
        client.username_pw_set(username, password)
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.max_queued_messages_set(32)
    client.max_inflight_messages_set(4)
    return client


class Publisher:
    def __init__(self, config):
        self.config = config
        self.base = f"weather/{config['station_id']}"
        self.client = make_client(config, "station")
        self.client.will_set(self.base + "/status", "offline", qos=1, retain=True)
        self.client.on_connect = self.on_connect
        self.client.on_connect_fail = lambda client, userdata: print("MQTT unreachable; local collection continues.")
        self.client.on_disconnect = self.on_disconnect
        self.client.connect_async(config["broker_host"], config["broker_port"], keepalive=30)
        self.client.loop_start()  # The network loop actually sends packets and handles acknowledgements.

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print("MQTT authentication/connection rejected:", reason_code)
        else:
            print("MQTT connected to the Pi broker (not encrypted).")
            client.publish(self.base + "/status", "online", qos=1, retain=True)

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        print("MQTT disconnected; local collection is independent of the broker.")

    def publish(self, row):
        if not self.client.is_connected():
            return False
        result = self.client.publish(self.base + "/telemetry", json.dumps(row, allow_nan=False),
                                     qos=1, retain=True)
        # Success means queued, NOT that the central database has committed the reading.
        return result.rc == mqtt.MQTT_ERR_SUCCESS

    def close(self):
        try:
            if self.client.is_connected():
                message = self.client.publish(self.base + "/status", "offline", qos=1, retain=True)
                message.wait_for_publish(timeout=2)
        finally:
            self.client.disconnect()
            self.client.loop_stop()
