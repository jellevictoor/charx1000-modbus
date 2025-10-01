# CharX1000 Modbus MQTT Publisher

MQTT publisher for CharX1000 Blitz charging stations via Modbus TCP. Reads energy metrics from charging points and publishes them to MQTT with mbmd-compatible topic structure.

## Features

- Reads voltage, current, power, and energy data from CharX1000 Blitz chargers
- Publishes to MQTT with mbmd-compatible topic structure
- Configurable via environment variables
- Docker-ready for Raspberry Pi deployment
- Auto-restart on failure
- Configurable polling interval

## Quick Start

### Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your settings:
   ```env
   MODBUS_HOST=192.168.1.50
   MQTT_BROKER=192.168.1.5
   MQTT_TOPIC_PREFIX=klskmp/metering/blitz
   POLL_INTERVAL=5
   ```

### Running with Docker Compose

```bash
docker-compose up -d
```

### View Logs

```bash
docker-compose logs -f
```

### Stop

```bash
docker-compose down
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODBUS_HOST` | `192.168.1.50` | Modbus TCP host address |
| `MODBUS_PORT` | `502` | Modbus TCP port |
| `DEVICE_ID` | `1` | Modbus device/unit ID |
| `MQTT_BROKER` | `192.168.1.5` | MQTT broker address |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_TOPIC_PREFIX` | `klskmp/metering/blitz` | MQTT topic prefix |
| `POLL_INTERVAL` | `5` | Polling interval in seconds |

## MQTT Topics

Data is published to topics following this pattern:
```
{MQTT_TOPIC_PREFIX}/{charging_point_name}/{metric}
```

Example topics:
- `klskmp/metering/blitz/links/Power`
- `klskmp/metering/blitz/links/Voltage/L1`
- `klskmp/metering/blitz/rechts/Import`

### Available Metrics

- `Voltage/L1`, `Voltage/L2`, `Voltage/L3` (V)
- `Current/L1`, `Current/L2`, `Current/L3` (A)
- `Power` (W)
- `ReactivePower` (VAR)
- `ApparentPower` (VA)
- `Import` (Wh)
- `Cosphi` (power factor)

## Development

### Running Locally

```bash
# Install dependencies with uv
uv pip install -e .

# Run the script
python read_energy_meters.py
```

### Building for Different Architectures

The Dockerfile is compatible with ARM64 (Raspberry Pi) and AMD64 platforms. Docker will automatically use the correct base image.

## Deployment on Raspberry Pi

1. Clone the repository on your Raspberry Pi:
   ```bash
   git clone https://github.com/yourusername/charx1000-modbus.git
   cd charx1000-modbus
   ```

2. Create `.env` file with your configuration

3. Start the service:
   ```bash
   docker-compose up -d
   ```

4. (Optional) Enable automatic startup on boot - Docker Compose with `restart: unless-stopped` handles this automatically.

## License

MIT
