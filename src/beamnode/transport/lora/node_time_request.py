## Script to request time from supervisor and set system time accordingly
import os
import sys
import atexit
import subprocess
import time
import json
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from beamnode.paths import CONFIG_JSON

# --- Logging (redirect all output) ---
LOG_PATH = "/home/pi/logs/time_request.log"


def configure_logging():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    log_file = open(LOG_PATH, "a", buffering=1)
    sys.stdout = log_file
    sys.stderr = log_file
    atexit.register(log_file.close)


def create_radio():
    import adafruit_rfm9x
    import board
    import busio
    import digitalio

    spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
    cs = digitalio.DigitalInOut(board.CE1)
    reset = digitalio.DigitalInOut(board.D25)
    return adafruit_rfm9x.RFM9x(spi, cs, reset, 915.0)

# send a time request to the supervisor and wait for a response
def request_time(rfm9x, node_id, timeout=300):
    # Create a time request message
    request_msg = {
        "type": "TIME_REQUEST",
        "node_id": node_id
    }
    rfm9x.send(bytes(json.dumps(request_msg), "utf-8"))
    print(f"Sent time request to supervisor: {request_msg}")

    start_time = time.time()
    time.sleep(1)  # wait a bit before listening for response
    while time.time() - start_time < timeout:
        pkt = rfm9x.receive(timeout=1.0)
        if pkt:
            try:
                response_msg = json.loads(pkt.decode())
                if response_msg.get("type") == "TIME_RESPONSE":
                    print(f"Received time response: {response_msg}")
                    return response_msg.get("timestamp")
            except Exception as e:
                print(f"Failed to decode packet: {e}")
                continue
    print("Timeout waiting for time response from supervisor.")
    return None

def main():
    configure_logging()
    rfm9x = create_radio()

    # Load node ID from config
    time.sleep(3)
    with CONFIG_JSON.open("r", encoding="utf-8") as f:
        config = json.load(f)
    node_id = config["global"].get("node_id", "unknown-node")

    # Request time from supervisor
    timestamp = request_time(rfm9x, node_id)
    if timestamp:
        # Set system time using the received timestamp
        try:
            subprocess.run(["sudo", "date", "-s", timestamp], check=True)
            print(f"System time set to: {timestamp}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to set system time: {e}")


if __name__ == "__main__":
    main()
