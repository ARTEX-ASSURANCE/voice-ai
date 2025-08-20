import os
import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from livekit.api import LiveKitAPI, AccessToken, VideoGrants, ListRoomsRequest

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class CreateTokenRequest(BaseModel):
    room_name: str | None = None
    identity: str = "default-identity"

class CreateTokenResponse(BaseModel):
    token: str

async def generate_room_name() -> str:
    """Generates a unique room name."""
    name = "room-" + str(uuid.uuid4())[:8]
    rooms = await get_rooms()
    while name in rooms:
        name = "room-" + str(uuid.uuid4())[:8]
    return name

async def get_rooms() -> list[str]:
    """Gets a list of all active room names."""
    livekit_host = os.getenv("LIVEKIT_URL")
    livekit_api_key = os.getenv("LIVEKIT_API_KEY")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([livekit_host, livekit_api_key, livekit_api_secret]):
        print("Warning: LiveKit server URL, API key, or secret are not fully configured.")
        return []

    lk_api = LiveKitAPI(host=livekit_host, api_key=livekit_api_key, api_secret=livekit_api_secret)
    try:
        rooms_response = await lk_api.room.list_rooms(ListRoomsRequest())
    finally:
        await lk_api.aclose()

    return [room.name for room in rooms_response.rooms]

@app.post("/create-token", response_model=CreateTokenResponse)
async def create_token(request: CreateTokenRequest):
    """Creates a LiveKit access token."""
    room_name = request.room_name
    identity = request.identity

    if not room_name:
        room_name = await generate_room_name()

    livekit_api_key = os.getenv("LIVEKIT_API_KEY")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([livekit_api_key, livekit_api_secret]):
        # In a real app, you'd use FastAPI's HTTPException here
        return {"error": "LiveKit API key or secret not configured"}, 500

    token_builder = AccessToken(livekit_api_key, livekit_api_secret) \
        .with_identity(identity) \
        .with_name(identity) \
        .with_grants(VideoGrants(
            room_join=True,
            room=room_name
        ))

    return CreateTokenResponse(token=token_builder.to_jwt())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
