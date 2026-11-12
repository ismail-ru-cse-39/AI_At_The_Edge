import time

STATES = {"normal": ("O", (0, 100, 0)), "attention": ("!", (180, 90, 0)),
          "unknown": ("?", (140, 140, 140)), "warming_up": ("?", (80, 80, 120)),
          "muted": ("=", (60, 60, 100))}


class Matrix:
    def __init__(self, sensor):
        self.hat = sensor.hat
        self.last_state = None

    def service(self, row, store):
        """Apply local display policy and acknowledge it; a pause does not stop sensing."""
        now = time.time()
        if self.hat:
            for event in self.hat.stick.get_events():
                if event.direction == "middle" and event.action == "pressed":
                    current = store.get("mute_until", 0)
                    store.set("mute_until", 0 if current > now else now + 60)
        age = now - row["observed_epoch"] if row else 999
        state = row.get("context", {}).get("state", "unknown") if row else "unknown"
        if not row or not row["valid"] or age > 15 or age < -5:
            state = "unknown"
        # A temporary display override never hides invalid/missing measurements.
        if state in ("normal", "attention") and store.get("mute_until", 0) > now:
            state = "muted"
        if state != self.last_state:
            symbol, colour = STATES.get(state, STATES["unknown"])
            if self.hat:
                self.hat.show_letter(symbol, text_colour=colour)
            else:
                print(f"SIMULATED MATRIX: {symbol} ({state})")
            store.set("display_ack", {"state": state, "applied_at": now})
            self.last_state = state