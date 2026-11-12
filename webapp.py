import argparse
import secrets
import time
from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from common import load_config, project_path
from storage import Store


def create_app(config_filename="config.json"):
    config = load_config(config_filename)
    store = Store(project_path(config["database"]))
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)  # Restarting deliberately invalidates old local sessions.
    app.config.update(MAX_CONTENT_LENGTH=4096, SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE="Strict", TRUSTED_HOSTS=["localhost", "127.0.0.1"])

    def view_model():
        """Translate stored data into text; never present an old reading as current."""
        row = store.latest(config["station_id"])
        now = time.time()
        age = now - row["observed_epoch"] if row else None
        fresh = age is not None and -5 <= age <= 15
        valid = bool(row and row["valid"] and fresh)
        context = row.get("context", {}) if row else {}
        forecast = row.get("forecast", {}) if row else {}
        state = context.get("state", "unknown") if valid else "unknown"
        reason = context.get("why", "Context processing is not running yet.")
        if not row:
            reason = "No readings yet. Start station.py in another terminal."
        elif not fresh:
            reason = "Reading stale or device clock incorrect. Check station.py and the clock."
        elif not row["valid"]:
            reason = "Invalid measurement. Check the sensor; missing data is not zero."
        def number(value, unit):
            return f"{value:.2f} {unit}" if value is not None and valid else "Unavailable"
        ack = store.get("display_ack", {})
        mute_left = max(0, round(store.get("mute_until", 0) - now))
        return {
            "station": config["station_id"], "state": state,
            "status": f"Station state: {state.replace('_', ' ')}.", "why": reason,
            "temperature": number(row.get("temperature_c") if row else None, "°C"),
            "humidity": number(row.get("humidity_pct") if row else None, "% RH"),
            "pressure": number(row.get("pressure_hpa") if row else None, "hPa"),
            "heat_index": number(context.get("heat_index_c"), "°C") + " (restricted teaching estimate)",
            "forecast": number(forecast.get("prediction_c"), "°C"),
            "forecast_why": forecast.get("why", "No model result yet.") if valid else "No forecast from stale/invalid data.",
            "baseline": number(row.get("baseline_60s_c") if row else None, "°C"),
            "observed_at": row["observed_at"] if row else "No observation yet",
            "source": row["source"] if row else "Unknown",
            "age": f"{max(0, age):.0f} seconds" if age is not None else "Unavailable",
            "network": row.get("mqtt_state", "Not enabled") if row and fresh else "Unknown: no fresh status",
            "display": ack.get("state", "Not acknowledged") if fresh else "Unknown: check the station",
            "override": f"Visual alert pause requested: {mute_left} seconds remaining" if mute_left else "Automatic display requested",
        }

    @app.after_request
    def security_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = ("default-src 'self'; script-src 'self'; "
            "style-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
        return response

    @app.get("/")
    def index():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return render_template("index.html", values=view_model(), csrf=session["csrf"])

    @app.get("/api/status")
    def status():
        return jsonify(view_model())

    @app.post("/control")
    def control():
        token = request.form.get("csrf", "")
        if not session.get("csrf") or not secrets.compare_digest(token, session["csrf"]):
            abort(400, "Form token missing or expired. Reload the dashboard.")
        action = request.form.get("action")
        if action not in ("mute", "resume"):
            abort(400, "Unknown action")
        now = time.time()
        if now - session.get("last_control", 0) < 1:
            abort(429, "Please wait one second before sending another command.")
        session["last_control"] = now
        store.set("mute_until", now + 60 if action == "mute" else 0)
        return redirect(url_for("index"), code=303)

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Open the local station dashboard.")
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    create_app(args.config).run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
