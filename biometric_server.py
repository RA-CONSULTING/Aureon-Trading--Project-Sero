import asyncio
import websockets
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store latest biometric data
latest_biometric = {}

async def handle_client(websocket):
    """Handle incoming biometric data from sensors"""
    global latest_biometric
    client_addr = websocket.remote_address
    logger.info(f"Biometric sensor connected from {client_addr}")
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                latest_biometric = data
                logger.info(f"Received: HR={data.get('heartRate', 'N/A')}bpm, "
                          f"HRV={data.get('hrv', 'N/A')}ms, "
                          f"Coherence={data.get('coherenceIndex', 'N/A')}")
                
                # Echo back confirmation
                await websocket.send(json.dumps({"status": "received", "timestamp": datetime.now().isoformat()}))
                
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {message[:100]}")
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Sensor disconnected from {client_addr}")
    except Exception as e:
        logger.error(f"Error handling client: {e}")

async def query_endpoint(websocket, path):
    """Allow querying current biometric state"""
    if latest_biometric:
        await websocket.send(json.dumps(latest_biometric))
    else:
        await websocket.send(json.dumps({"error": "No biometric data available yet"}))

async def main():
    logger.info("Starting Biometric WebSocket Server on ws://localhost:8788")
    logger.info("Waiting for real sensor data...")
    
    # Server for incoming sensor data
    async with websockets.serve(handle_client, "localhost", 8788):
        await asyncio.Future()  # Run forever

if __name__ == '__main__':
    asyncio.run(main())
