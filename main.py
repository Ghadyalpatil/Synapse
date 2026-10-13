
import csv
import json
import os
import time
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template_string

# Optional sensor libraries: a missing library won't stop the dashboard.
try:
    import board
    import busio
    import adafruit_mlx90640
except Exception:
    board = busio = adafruit_mlx90640 = None

try:
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
except Exception:
    ADS = AnalogIn = None

try:
    import serial
except Exception:
    serial = None


# ---------------- CONFIGURATION ----------------

BASE_DIR = Path.home() / "Synapse"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CSV_FILE = DATA_DIR / "sensor_readings.csv"

SAMPLE_INTERVAL = 1.0

# Radar settings. Confirm these with the C4001 configuration.
RADAR_ENABLED = True
RADAR_PORT = "/dev/serial0"
RADAR_BAUD = 9600  # Change to the baud rate configured on your sensor.

# Leave off until the fan hardware and safe driver wiring are confirmed.
GPIO_FAN_CONTROL = False
FAN_GPIO = 18

app = Flask(__name__)
lock = threading.Lock()

latest = {
    "timestamp": "",
    "thermal_min_c": None,
    "thermal_max_c": None,
    "thermal_avg_c": None,
    "thermal_pixels_c": [],
    "mic_voltage_v": None,
    "mic_raw": None,
    "radar_raw": "",
    "status": {
        "thermal": "Not initialized",
        "microphone": "Not initialized",
        "radar": "Not initialized",
        "fan": "Software control disabled"
    }
}


def initialize_thermal():
    if not all([board, busio, adafruit_mlx90640]):
        raise RuntimeError("MLX90640 libraries unavailable")

    i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
    camera = adafruit_mlx90640.MLX90640(i2c)
    camera.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ
    return camera


def initialize_microphone():
    if not all([board, busio, ADS, AnalogIn]):
        raise RuntimeError("ADS1115 libraries unavailable")

    i2c = busio.I2C(board.SCL, board.SDA)
    adc = ADS.ADS1115(i2c, address=0x48)
    channel = AnalogIn(adc, ADS.P0)
    return channel


def initialize_radar():
    if not RADAR_ENABLED:
        return None
    if serial is None:
        raise RuntimeError("pyserial unavailable")

    return serial.Serial(
        RADAR_PORT,
        RADAR_BAUD,
        timeout=0.05
    )


def create_csv_if_needed():
    if not CSV_FILE.exists() or CSV_FILE.stat().st_size == 0:
        with CSV_FILE.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "thermal_min_c",
                "thermal_max_c",
                "thermal_avg_c",
                "mic_raw",
                "mic_voltage_v",
                "radar_raw"
            ])


def sensor_worker():
    camera = None
    mic = None
    radar = None
    thermal_frame = [0.0] * 768

    # Initialize devices independently, so one failure doesn't stop others.
    try:
        camera = initialize_thermal()
        latest["status"]["thermal"] = "Connected"
    except Exception as e:
        latest["status"]["thermal"] = f"Unavailable: {e}"

    try:
        mic = initialize_microphone()
        latest["status"]["microphone"] = "Connected"
    except Exception as e:
        latest["status"]["microphone"] = f"Unavailable: {e}"

    try:
        radar = initialize_radar()
        if radar:
            latest["status"]["radar"] = "Serial connected; awaiting data"
        else:
            latest["status"]["radar"] = "Disabled"
    except Exception as e:
        latest["status"]["radar"] = f"Unavailable: {e}"

    create_csv_if_needed()

    while True:
        timestamp = datetime.now().astimezone().isoformat(
            timespec="milliseconds"
        )

        row = {
            "timestamp": timestamp,
            "thermal_min_c": None,
            "thermal_max_c": None,
            "thermal_avg_c": None,
            "thermal_pixels_c": [],
            "mic_raw": None,
            "mic_voltage_v": None,
            "radar_raw": ""
        }

        if camera is not None:
            try:
                camera.getFrame(thermal_frame)
                temps = [float(t) for t in thermal_frame]

                row["thermal_min_c"] = round(min(temps), 2)
                row["thermal_max_c"] = round(max(temps), 2)
                row["thermal_avg_c"] = round(
                    sum(temps) / len(temps), 2
                )
                row["thermal_pixels_c"] = [round(t, 1) for t in temps]
                latest["status"]["thermal"] = "Live"
            except Exception as e:
                latest["status"]["thermal"] = f"Read error: {e}"

        if mic is not None:
            try:
                row["mic_raw"] = int(mic.value)
                row["mic_voltage_v"] = round(float(mic.voltage), 4)
                latest["status"]["microphone"] = "Live"
            except Exception as e:
                latest["status"]["microphone"] = f"Read error: {e}"

        if radar is not None:
            try:
                # Store received text as raw data until the sensor's
                # actual output protocol is confirmed and decoded.
                line = radar.readline()
                if line:
                    row["radar_raw"] = line.decode(
                        "utf-8", errors="replace"
                    ).strip()
                    latest["status"]["radar"] = "Receiving serial data"
            except Exception as e:
                latest["status"]["radar"] = f"Read error: {e}"

        with CSV_FILE.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                row["timestamp"],
                row["thermal_min_c"],
                row["thermal_max_c"],
                row["thermal_avg_c"],
                row["mic_raw"],
                row["mic_voltage_v"],
                row["radar_raw"]
            ])

        with lock:
            latest.update(row)

        time.sleep(SAMPLE_INTERVAL)


PAGE = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Synapse Sensor Dashboard</title>
<style>
body {
    margin: 0; padding: 22px; background: #10131b; color: #f4f6ff;
    font-family: Arial, sans-serif;
}
h1 { margin-bottom: 5px; }
.muted { color: #a5adc2; }
.cards {
    display: grid; grid-template-columns: repeat(auto-fit,minmax(190px,1fr));
    gap: 12px; margin: 20px 0;
}
.card, .panel {
    background: #1b2130; border: 1px solid #30394c;
    border-radius: 12px; padding: 16px;
}
.label { color: #a5adc2; font-size: 13px; }
.value { font-size: 25px; font-weight: bold; margin-top: 8px; }
#heatmap {
    display: grid; grid-template-columns: repeat(32,minmax(0,1fr));
    gap: 2px; max-width: 800px; width: 100%; aspect-ratio: 4 / 3;
}
.pixel { min-width: 0; min-height: 0; border-radius: 1px; }
.statusrow { margin: 8px 0; overflow-wrap: anywhere; }
#radar { overflow-wrap: anywhere; white-space: pre-wrap; }
a { color: #86b7ff; }
</style>
</head>
<body>
<h1>SYNAPSE / SENSOR DASHBOARD</h1>
<div class="muted">Live readings from the Raspberry Pi</div>

<div class="cards">
  <div class="card"><div class="label">THERMAL MIN</div>
    <div class="value" id="tmin">--</div></div>
  <div class="card"><div class="label">THERMAL MAX</div>
    <div class="value" id="tmax">--</div></div>
  <div class="card"><div class="label">THERMAL AVERAGE</div>
    <div class="value" id="tavg">--</div></div>
  <div class="card"><div class="label">MICROPHONE VOLTAGE</div>
    <div class="value" id="micv">--</div></div>
  <div class="card"><div class="label">MICROPHONE ADC RAW</div>
    <div class="value" id="micraw">--</div></div>
</div>

<div class="panel">
  <h3>Thermal heatmap (32 × 24)</h3>
  <div id="heatmap"></div>
  <p class="muted">Colors are scaled to the minimum and maximum of each frame.</p>
</div>

<div class="panel" style="margin-top:14px">
  <h3>Radar serial output (raw)</h3>
  <div id="radar">Waiting for data...</div>
</div>

<div class="panel" style="margin-top:14px">
  <h3>Sensor status</h3>
  <div id="statuses"></div>
  <p class="muted">CSV file: ~/Synapse/data/sensor_readings.csv</p>
  <p class="muted">Last update: <span id="stamp">--</span></p>
</div>

<script>
const grid = document.getElementById("heatmap");
for (let i=0; i<768; i++) {
    const p = document.createElement("div");
    p.className = "pixel";
    grid.appendChild(p);
}
function color(v, lo, hi) {
    const r = hi === lo ? 0.5 : Math.max(0, Math.min(1, (v-lo)/(hi-lo)));
    return `hsl(${240*(1-r)},100%,50%)`;
}
async function refresh() {
    try {
        const res = await fetch("/api/data");
        const d = await res.json();
        const fmt = v => v === null || v === undefined ? "--" : v.toFixed(1)+" °C";
        document.getElementById("tmin").textContent = fmt(d.thermal_min_c);
        document.getElementById("tmax").textContent = fmt(d.thermal_max_c);
        document.getElementById("tavg").textContent = fmt(d.thermal_avg_c);
        document.getElementById("micv").textContent =
            d.mic_voltage_v == null ? "--" : d.mic_voltage_v.toFixed(3)+" V";
        document.getElementById("micraw").textContent =
            d.mic_raw == null ? "--" : d.mic_raw;

        if (d.thermal_pixels_c && d.thermal_pixels_c.length === 768) {
            const lo = Math.min(...d.thermal_pixels_c);
            const hi = Math.max(...d.thermal_pixels_c);
            [...grid.children].forEach((p,i) => {
                p.style.background = color(d.thermal_pixels_c[i], lo, hi);
                p.title = d.thermal_pixels_c[i] + " °C";
            });
        }
        document.getElementById("radar").textContent = d.radar_raw || "No text received";
        document.getElementById("stamp").textContent = d.timestamp || "--";
        document.getElementById("statuses").innerHTML = "";
        for (const [name, status] of Object.entries(d.status || {})) {
            const p = document.createElement("div");
            p.className = "statusrow";
            p.textContent = name + ": " + status;
            document.getElementById("statuses").appendChild(p);
        }
    } catch(e) {
        document.getElementById("statuses").textContent = "Waiting for server...";
    }
}
refresh();
setInterval(refresh, 1000);
</script>
</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(PAGE)


@app.route("/api/data")
def api_data():
    with lock:
        return jsonify(latest.copy())


if __name__ == "__main__":
    threading.Thread(target=sensor_worker, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
