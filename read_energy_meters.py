#!/usr/bin/env python3
"""
CharX1000 Blitz Power Station to MQTT Publisher
Reads energy data from Blitz chargers and publishes to MQTT
with mbmd-compatible topic structure
"""
from pymodbus.client import ModbusTcpClient
import paho.mqtt.client as mqtt
import os
import time
import struct
from typing import Dict, Optional

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

def read_u32(client, address) -> Optional[int]:
    """Read 32-bit unsigned value"""
    try:
        rr = client.read_holding_registers(address=address, count=2, device_id=DEVICE_ID)
        if rr.isError():
            return None
        return (rr.registers[0] << 16) | rr.registers[1]
    except Exception as e:
        print(f"Error reading u32 @ {address}: {e}")
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
        print(f"Error reading i32 @ {address}: {e}")
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
        print(f"Error reading u64 @ {address}: {e}")
        return None

def read_u16(client, address) -> Optional[int]:
    """Read 16-bit unsigned value"""
    try:
        rr = client.read_holding_registers(address=address, count=1, device_id=DEVICE_ID)
        if rr.isError():
            return None
        return rr.registers[0]
    except Exception as e:
        print(f"Error reading u16 @ {address}: {e}")
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
        mqtt_client.publish(topic, value, retain=True)

    print(f"Published {len(data)} metrics for {cp_name}")

def main():
    print("CharX1000 Blitz Charger MQTT Publisher (mbmd-compatible format)")
    print(f"Connecting to Modbus: {MODBUS_HOST}:{MODBUS_PORT}")
    print(f"Connecting to MQTT: {MQTT_BROKER}:{MQTT_PORT}")

    # Connect to MQTT
    mqtt_client = mqtt.Client(client_id="blitz_publisher")
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        print("✓ Connected to MQTT")
    except Exception as e:
        print(f"✗ Failed to connect to MQTT: {e}")
        return

    # Connect to Modbus
    modbus_client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)

    try:
        if not modbus_client.connect():
            print("✗ Failed to connect to Modbus server")
            return
        print("✓ Connected to Modbus\n")

        while True:
            for cp_id, config in CHARGING_POINTS.items():
                cp_name = config["name"]
                data = read_charging_point(modbus_client, cp_id, config)

                if data:
                    publish_data(mqtt_client, cp_id, cp_name, data)
                    print(f"  {cp_name}: Power={data.get('Power', 0):.1f}W, "
                          f"Import={data.get('Import', 0):.0f}Wh")
                else:
                    print(f"  {cp_name}: Failed to read data")

            print()
            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        modbus_client.close()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        print("Disconnected")

if __name__ == "__main__":
    main()
