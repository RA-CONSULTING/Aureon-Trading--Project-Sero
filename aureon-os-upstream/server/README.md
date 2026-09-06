# Earth Live Data Server (Component)

Scope: Optional development server for simulated data feeds. For the unified trading engine overview and run path, see [../README.md](../README.md) and [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

This WebSocket server simulates Schumann Resonance and biometric sensor data for the AUREON Quantum Trading System.

## Quick Start

1. **Install dependencies:**
```bash
npm install ws
```

2. **Run the server:**
```bash
node server/earth-live-data-server.js
```

3. **Verify connection:**
Open your AUREON dashboard at `/aureon` and the sensors should automatically connect.

## Server Endpoints

- **Schumann Resonance:** `ws://localhost:8787/schumann`
  - Frequency (Hz)
  - Amplitude
  - Quality
  - Variance
  
- **Biometric Sensors:** `ws://localhost:8788/biometrics`
  - HRV (Heart Rate Variability)
  - Heart Rate (BPM)
  - Alpha waves (8-13 Hz)
  - Theta waves (4-8 Hz)
  - Delta waves (0.5-4 Hz)
  - Beta waves (13-30 Hz)
  - Coherence index

## Data Format

### Schumann Resonance
```json
{
  "frequency": 7.83,
  "amplitude": 0.85,
  "quality": 0.78,
  "variance": 0.03,
  "timestamp": "2025-11-18T16:52:00.000Z"
}
```

### Biometric Data
```json
{
  "hrv": 65.5,
  "heartRate": 72,
  "alpha": 0.35,
  "theta": 0.28,
  "delta": 0.17,
  "beta": 0.20,
  "coherenceIndex": 0.68,
  "sensorStatus": "connected",
  "timestamp": "2025-11-18T16:52:00.000Z"
}
```

## Integration with Real Hardware

To connect real sensors:

1. Replace the simulated data in `sendSchumannData()` and `sendBiometricData()` with readings from your hardware
2. Common interfaces:
   - **HRV monitors:** Bluetooth/ANT+ (Polar H10, Garmin HRM)
   - **EEG headsets:** Bluetooth (Muse, OpenBCI, Emotiv)
   - **Schumann monitors:** Serial/USB data loggers

## Troubleshooting

**Port already in use:**
```bash
# Find and kill process using port 8787
lsof -ti:8787 | xargs kill -9
lsof -ti:8788 | xargs kill -9
```

**Connection refused:**
- Ensure the server is running
- Check firewall settings
- Verify WebSocket support in your browser

**No data received:**
- Check browser console for WebSocket errors
- Verify server logs show "sensor connected"
- Ensure correct WebSocket URLs in the React hooks
