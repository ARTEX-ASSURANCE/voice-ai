import asyncio
import os
from dotenv import load_dotenv
from livekit import api
from livekit.api import RoomParticipantIdentity
# We need this import again for the older, object-based request
from livekit.protocol.sip import CreateSIPParticipantRequest

# Load variables from the .env file into the environment
load_dotenv()

# --- Configuration ---
LIVEKIT_URL = os.environ.get("LIVEKIT_URL")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET")

# --- Call Details ---
SIP_TRUNK_ID = "ST_eYfgXGHqrxcx"
PHONE_NUMBER_TO_DIAL = "+33257840179"
ROOM_NAME = "arthex-sip-test-room"
PARTICIPANT_IDENTITY = "ai-call-agent"
PARTICIPANT_NAME = "Artex Agent IA"


async def main():
    """
    Initiates, monitors, and then terminates an outbound SIP call using LiveKit.
    This version is adapted for older library versions to ensure compatibility.
    """
    if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET]):
        print("❌ Missing required credentials. Ensure they are in your .env file.")
        return

    # The 'async with' block handles closing the API connection automatically.
    async with api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET) as lk_api:
        try:
            print(f"📞 Placing call to {PHONE_NUMBER_TO_DIAL} via trunk {SIP_TRUNK_ID}...")

            # --- Compatibility Fix ---
            # Reverting to the request object structure, which is required by older
            # versions of the livekit-server-sdk library.
            request = CreateSIPParticipantRequest(
                sip_trunk_id=SIP_TRUNK_ID,
                sip_call_to=PHONE_NUMBER_TO_DIAL,
                room_name=ROOM_NAME,
                participant_identity=PARTICIPANT_IDENTITY,
                participant_name=PARTICIPANT_NAME,
                #wait_for_answer=True,
            )
            participant_info = await lk_api.sip.create_sip_participant(request)

            print("\n✅ Call Connected!")
            print(f"   Room: {participant_info.room_name}")
            print(f"   Identity: {participant_info.participant_identity}")

            print("\n⏳ Waiting for 15 seconds before hanging up...")
            await asyncio.sleep(15)

            print(f"\n📞 Terminating call for participant {PARTICIPANT_IDENTITY}...")
            
            # Using positional arguments for remove_participant for compatibility
            await lk_api.room.remove_participant(RoomParticipantIdentity(
            room=ROOM_NAME,
            identity=PARTICIPANT_IDENTITY,
            ))
            print("✅ Call termination request sent.")

        except api.TwirpError as e:
            print(f"\n❌ Call failed to connect: {e.message}")
            print(f"   Error Code: {e.code}")
            print("   Please check if the phone number is correct and able to receive calls.")
        except Exception as e:
            print(f"\n❌ An unexpected error occurred: {e}")



if __name__ == "__main__":
    asyncio.run(main())
