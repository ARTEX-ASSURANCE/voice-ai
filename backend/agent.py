# agent.py

import os
import asyncio
import json
from dotenv import load_dotenv
from livekit.agents import (
    JobContext,
    WorkerOptions,
    cli,
    AgentSession,
)
from api import ArtexAgent
from db_driver import ExtranetDatabaseDriver
from prompts import WELCOME_MESSAGE
from tools import lookup_client_by_phone
from logger import configure_logger, log_activity, log_error

# --- Load Environment & Configure Logger ---
load_dotenv()

# Configure logger at startup
db_params_for_logger = {
    'host': os.getenv("DB_HOST"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'database': os.getenv("DB_NAME"),
    'port': os.getenv("DB_PORT", 3306)
}
if not all(db_params_for_logger[key] for key in ['host', 'user', 'password', 'database']):
    configure_logger() # Configure without DB
    log_activity("agent.startup", "Database env vars missing, DB logging disabled.", level="WARNING")
else:
    configure_logger(db_params=db_params_for_logger)

# --- Main Agent Entrypoint ---
async def entrypoint(ctx: JobContext):
    """
    This function is executed for each new call the agent handles.
    """
    await asyncio.sleep(2)

    call_id = ctx.job.id
    log_activity("agent.entrypoint", "New call received", call_id=call_id, context={"room_name": ctx.room.name})

    db_driver = None
    session = None
    
    try:
        db_driver = ExtranetDatabaseDriver()
        artex_agent = ArtexAgent(db_driver=db_driver)

        await ctx.connect()
        log_activity("agent.entrypoint", "Agent connected to room", call_id=call_id)

        session = AgentSession()
        
        caller_number = None
        if ctx.room.metadata:
            metadata = json.loads(ctx.room.metadata)
            caller_number = metadata.get('caller_number')
            log_activity("agent.entrypoint", "Extracted caller number", call_id=call_id, context={"caller_number": caller_number})

        initial_userdata = artex_agent.get_initial_userdata()
        session.userdata = initial_userdata

        initial_message = WELCOME_MESSAGE
        if caller_number:
            # Use the new lookup tool
            lookup_result = await lookup_client_by_phone(session, phone=caller_number)
            # Adapt to the new confirmation prompt
            if "I found a file for" in lookup_result:
                initial_message = lookup_result
                log_activity("agent.entrypoint", "Caller identified via phone lookup", call_id=call_id)

        await session.start(artex_agent, room=ctx.room)
        log_activity("agent.entrypoint", "Agent session started", call_id=call_id)
        await session.say(initial_message, allow_interruptions=True)

    except Exception as e:
        log_error(
            source="agent.entrypoint",
            message="An unrecoverable error occurred in agent entrypoint",
            exception=e,
            call_id=call_id
        )

    finally:
        log_activity("agent.entrypoint", "Entrypoint finished", call_id=call_id)


# --- Standard CLI Runner ---
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
