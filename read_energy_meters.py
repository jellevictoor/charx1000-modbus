#!/usr/bin/env python3
"""
CharX1000 Blitz Power Station to MQTT Publisher
Reads energy data from Blitz chargers and publishes to MQTT
with mbmd-compatible topic structure
"""
import logging

from pymodbus.client import ModbusTcpClient
import paho.mqtt.client as mqtt
import os
import time
import struct
from typing import Dict, Optional

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s')
logging.getLogger().addHandler(logging.StreamHandler())
logging.getLogger().setLevel(logging.INFO)
# Configuration from environment variables with defaults
MODBUS_HOST = os.getenv("MODBUS_HOST", "192.168.1.50")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "502"))
DEVICE_ID = int(os.getenv("DEVICE_ID", "1"))

MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.1.5")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "klskmp/metering/blitz")

# Poll interval in seconds
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))

# Charging points configuration
CHARGING_POINTS = {
    "cp1": {
        "name": "links",
        "base_address": 1000
    },
    "cp2": {
        "name": "rechts",
        "base_address": 2000
    }
}

# Register offsets from base address
REGISTER_MAP = {
    "voltage_l1": 232,
    "voltage_l2": 234,
    "voltage_l3": 236,
    "current_l1": 238,
    "current_l2": 240,
    "current_l3": 242,
    "power": 244,
    "reactive_power": 246,
    "apparent_power": 248,
    "energy_total": 250,
    "energy_reactive": 254,
    "energy_apparent": 258,
    "current_setting": 297,
    "vehicle_status": 299,
}

def ensure_connection(client, max_retries=3) -> bool:
    """Ensure Modbus connection is alive, reconnect if necessary"""
    for attempt in range(max_retries):
        if client.connected:
            # Test the connection with a simple read
            try:
                test_read = client.read_holding_registers(address=1000, count=1, device_id=DEVICE_ID)
                if not test_read.isError():
                    return True
                log.warning("Connection test failed, reconnecting...")
            except Exception as e:
                log.warning(f"Connection test exception: {e}, reconnecting...")

        # Connection is not alive, try to reconnect
        try:
            if client.connected:
                client.close()
            time.sleep(1)  # Brief delay before reconnect
            if client.connect():
                log.info(f"✓ Reconnected to Modbus (attempt {attempt + 1}/{max_retries})")
                return True
            else:
                log.warning(f"✗ Reconnection failed (attempt {attempt + 1}/{max_retries})")
        except Exception as e:
            log.warning(f"Reconnection error (attempt {attempt + 1}/{max_retries}): {e}")

        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)  # Exponential backoff

    log.error("Failed to establish Modbus connection after all retries")
    return False

def read_u32(client, address) -> Optional[int]:
    """Read 32-bit unsigned value"""
    try:
        rr = client.read_holding_registers(address=address, count=2, device_id=DEVICE_ID)
        if rr.isError():
            return None
        return (rr.registers[0] << 16) | rr.registers[1]
    except Exception as e:
        log.exception(f"Error reading u32 @ {address}")
        return None

def read_i32(client, address) -> Optional[int]:
    """Read 32-bit signed value"""
    try:
        rr = client.read_holding_registers(address=address, count=2, device_id=DEVICE_ID)
        if rr.isError():
            return None
        unsigned = (rr.registers[0] << 16) | rr.registers[1]
        return struct.unpack('>i', struct.pack('>I', unsigned))[0]
    except Exception as e:
        log.exception(f"Error reading i32 @ {address}")
        return None

def read_u64(client, address) -> Optional[int]:
    """Read 64-bit unsigned value"""
    try:
        rr = client.read_holding_registers(address=address, count=4, device_id=DEVICE_ID)
        if rr.isError():
            return None
        return (rr.registers[0] << 48) | (rr.registers[1] << 32) | \
            (rr.registers[2] << 16) | rr.registers[3]
    except Exception as e:
        log.exception(f"Error reading u64 @ {address}")
        return None

def read_u16(client, address) -> Optional[int]:
    """Read 16-bit unsigned value"""
    try:
        rr = client.read_holding_registers(address=address, count=1, device_id=DEVICE_ID)
        if rr.isError():
            return None
        return rr.registers[0]
    except Exception as e:
        log.exception(f"Error reading u16 @ {address}")
        return None

def read_charging_point(client, cp_id: str, config: Dict) -> Optional[Dict]:
    """Read all data from a charging point"""
    base = config["base_address"]
    data = {}

    # Voltages (mV -> V)
    if (val := read_u32(client, base + REGISTER_MAP["voltage_l1"])) is not None:
        data["Voltage/L1"] = val / 1000.0
    if (val := read_u32(client, base + REGISTER_MAP["voltage_l2"])) is not None:
        data["Voltage/L2"] = val / 1000.0
    if (val := read_u32(client, base + REGISTER_MAP["voltage_l3"])) is not None:
        data["Voltage/L3"] = val / 1000.0

    # Currents (mA -> A)
    if (val := read_u32(client, base + REGISTER_MAP["current_l1"])) is not None:
        data["Current/L1"] = val / 1000.0
    if (val := read_u32(client, base + REGISTER_MAP["current_l2"])) is not None:
        data["Current/L2"] = val / 1000.0
    if (val := read_u32(client, base + REGISTER_MAP["current_l3"])) is not None:
        data["Current/L3"] = val / 1000.0

    # Power (mW -> W)
    if (val := read_u32(client, base + REGISTER_MAP["power"])) is not None:
        data["Power"] = val / 1000.0
    if (val := read_i32(client, base + REGISTER_MAP["reactive_power"])) is not None:
        data["ReactivePower"] = val / 1000.0
    if (val := read_u32(client, base + REGISTER_MAP["apparent_power"])) is not None:
        data["ApparentPower"] = val / 1000.0

    # Energy (Wh)
    if (val := read_u64(client, base + REGISTER_MAP["energy_total"])) is not None:
        data["Import"] = val  # Keep in Wh like mbmd

    # Calculate power factor (Cosphi)
    if "Power" in data and "ApparentPower" in data and data["ApparentPower"] > 0:
        data["Cosphi"] = data["Power"] / data["ApparentPower"]

    return data if data else None

def publish_data(mqtt_client, cp_id: str, cp_name: str, data: Dict):
    """Publish data to MQTT with mbmd-compatible structure"""
    base_topic = f"{MQTT_TOPIC_PREFIX}/{cp_name}"

    # Publish each metric
    for key, value in data.items():
        topic = f"{base_topic}/{key}"
        mqtt_client.publish(topic, value, retain=False)

    log.info(f"Published {len(data)} metrics for {cp_name}")

def main():
    log.info("CharX1000 Blitz Charger MQTT Publisher (mbmd-compatible format)")
    log.info(f"Connecting to Modbus: {MODBUS_HOST}:{MODBUS_PORT}")
    log.info(f"Connecting to MQTT: {MQTT_BROKER}:{MQTT_PORT}")

    # Connect to MQTT
    mqtt_client = mqtt.Client(client_id="blitz_publisher")
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        log.info("✓ Connected to MQTT")
    except Exception as e:
        log.exception(f"✗ Failed to connect to MQTT")
        return

    # Connect to Modbus
    modbus_client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)

    try:
        if not modbus_client.connect():
            log.info("✗ Failed to connect to Modbus server")
            return
        log.info("✓ Connected to Modbus\n")

        consecutive_failures = 0
        max_consecutive_failures = 5

        while True:
            # Ensure connection is alive before reading
            if not ensure_connection(modbus_client):
                log.error("Cannot establish Modbus connection, retrying in 30 seconds...")
                time.sleep(30)
                continue

            # Reset failure counter on successful connection
            success = False

            for cp_id, config in CHARGING_POINTS.items():
                cp_name = config["name"]
                data = read_charging_point(modbus_client, cp_id, config)

                if data:
                    publish_data(mqtt_client, cp_id, cp_name, data)
                    log.info(f"  {cp_name}: Power={data.get('Power', 0):.1f}W, "
                          f"Import={data.get('Import', 0):.0f}Wh")
                    success = True
                else:
                    log.info(f"  {cp_name}: Failed to read data")

            # Track consecutive failures
            if not success:
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    log.warning(f"Too many consecutive failures ({consecutive_failures}), forcing reconnection...")
                    modbus_client.close()
                    consecutive_failures = 0
            else:
                consecutive_failures = 0

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        log.info("\nStopping...")
    finally:
        modbus_client.close()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        log.info("Disconnected")

if __name__ == "__main__":
    main()
