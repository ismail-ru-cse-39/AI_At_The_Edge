import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from storage import Store
from test_core import CONFIG, reading

@unittest.skipUnless(importlib.util.find_spec("flask"), "Flask not installed")
class WebTests(unittest.TestCase):
    def setUp(self):
        from webapp import create_app
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.db = self.folder / "weather.db"
        config = {**CONFIG, "database": str(self.db), "retention_days": 7}
        path = self.folder / "config.json"
        path.write_text(json.dumps(config))
        app = create_app(str(path))
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def test_empty_and_stale_states(self):
        self.assertEqual(self.client.get("/api/status").json["state"], "unknown")
        Store(self.db).add(reading(epoch=time.time() - 30))
        result = self.client.get("/api/status").json
        self.assertEqual(result["temperature"], "Unavailable")
        self.assertIn("stale", result["why"])

    def test_control_requires_post_and_token(self):
        self.assertEqual(self.client.get("/control").status_code, 405)
        self.assertEqual(self.client.post("/control", data={"action": "mute"}).status_code, 400)
        self.client.get("/")
        with self.client.session_transaction() as session:
            token = session["csrf"]
        response = self.client.post("/control", data={"csrf": token, "action": "mute"})
        self.assertEqual(response.status_code, 303)
        self.assertGreater(Store(self.db).get("mute_until"), time.time())

    def test_unknown_command_rejected(self):
        self.client.get("/")
        with self.client.session_transaction() as session:
            token = session["csrf"]
        self.assertEqual(self.client.post("/control", data={"csrf": token, "action": "shell"}).status_code, 400)

    def test_untrusted_host_rejected(self):
        self.assertEqual(self.client.get("/", headers={"Host": "attacker.invalid"}).status_code, 400)

if __name__ == "__main__":
    unittest.main()
