# inbound_sip_handler.py

import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from livekit import api
import uvicorn

# --- Load Environment Variables ---
# Make sure you have a .env file with your LiveKit credentials
load_dotenv()

LIVEKIT_URL = os.environ.get("LIVEKIT_URL")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET")

# --- Basic Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("sip_inbound_handler")

# --- FastAPI Application ---
app = FastAPI()

# --- LiveKit API Client ---
# It's good practice to create the client once and reuse it.
lk_api = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)

@app.on_event("startup")
async def startup_event():
    """Check for credentials on startup."""
    if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET]):
        logger.critical("FATAL: Missing LiveKit credentials. Please check your .env file.")
        
@app.on_event("shutdown")
async def shutdown_event():
    """Close the LiveKit API client gracefully on shutdown."""
    await lk_api.aclose()
    logger.info("LiveKit API client closed.")

@app.post("/inbound-sip-handler")
async def handle_inbound_sip(request: Request):
    """
    This endpoint receives webhook events from LiveKit for inbound SIP calls.
    It creates a room and returns instructions for LiveKit to route the call.
    """
    logger.info("Received inbound SIP call webhook.")

    try:
        # 1. Parse the incoming request from LiveKit
        data = await request.json()
        # CORRECTED: The field is 'call_id', not 'sip_call_id'
        call_id = data.get('call_id')
        caller_number = data.get('from')
        callee_number = data.get('to')

        if not all([call_id, caller_number, callee_number]):
            logger.error("Webhook payload missing required fields (call_id, from, to).")
            raise HTTPException(status_code=400, detail="Missing required fields.")

        logger.info(f"Processing call from '{caller_number}' to '{callee_number}' (Call ID: {call_id})")

        # 2. Create a unique room name for this call.
        room_name = f"sip-inbound-{call_id}"
        
        # 3. Create the room on the LiveKit server.
        await lk_api.room.create_room(name=room_name, empty_timeout=60)
        logger.info(f"Created LiveKit room: '{room_name}'")

        # 4. Define the participant's details.
        participant_identity = f"sip-user-{caller_number}"
        participant_name = f"Caller ({caller_number})"
        # This metadata will be available to your agent in the room.
        participant_metadata = f'{{"caller_number": "{caller_number}"}}'

        # 5. Return the response to LiveKit.
        # MAJOR CHANGE: We no longer generate a token. We provide the details,
        # and LiveKit creates the token for us. This is the modern workflow.
        response_data = {
            "room_name": room_name,
            "participant_identity": participant_identity,
            "participant_name": participant_name,
            "participant_metadata": participant_metadata,
        }
        
        logger.info(f"Sending instructions to LiveKit for participant '{participant_identity}'.")
        return response_data

    except Exception as e:
        logger.error(f"An error occurred while processing inbound SIP call: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

# --- To run this server ---
# 1. Make sure you have fastapi and uvicorn installed:
#    pip install fastapi "uvicorn[standard]"
#
# 2. Run the server from your terminal:
#    uvicorn inbound_sip_handler:app --host 0.0.0.0 --port 8080
#
# 3. Expose this server to the internet using a tool like ngrok.
#
# 4. In LiveKit, create a Dispatch Rule for your inbound number and set the
#    Webhook URL to your public server address (e.g., http://<your-ngrok-url>/inbound-sip-handler)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)