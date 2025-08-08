# agent.py (Refactored for new schema)

import logging
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
from tools import lookup_client_by_phone # Changed from lookup_adherent_by_telephone
# from error_logger import log_system_error, set_db_connection_params # Commented out as not refactored

# --- Logging Configuration ---
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("artex_agent")
logger.setLevel(logging.INFO)

load_dotenv()

# --- Main Agent Entrypoint ---
async def entrypoint(ctx: JobContext):
    """
    This function is executed for each new call the agent handles.
    """
    await asyncio.sleep(2)

    call_id_log_prefix = f"[{ctx.job.id}]"
    logger.info(f"{call_id_log_prefix} New call received for room: {ctx.room.name}")

    db_driver = None
    session = None
    
    try:
        db_driver = ExtranetDatabaseDriver()
        artex_agent = ArtexAgent(db_driver=db_driver)

        await ctx.connect()
        logger.info(f"{call_id_log_prefix} Agent connected to room.")

        # Shutdown hook for graceful exit (logging part commented out)
        # async def shutdown_hook():
        #     if session:
        #         logger.info(f"{call_id_log_prefix} Shutdown hook initiated. Saving final data...")
        #         # Data saving logic would be here...
        #
        # ctx.add_shutdown_callback(shutdown_hook)

        session = AgentSession()
        
        caller_number = None
        if ctx.room.metadata:
            metadata = json.loads(ctx.room.metadata)
            caller_number = metadata.get('caller_number')
        
        # Call logging is temporarily disabled as it depends on the old schema.
        # current_call_journal_id = db_driver.enregistrer_debut_appel(...)
        # logger.info(f"{call_id_log_prefix} Call registered in DB...")
        
        initial_userdata = artex_agent.get_initial_userdata()
        # initial_userdata["current_call_journal_id"] = current_call_journal_id
        session.userdata = initial_userdata

        initial_message = WELCOME_MESSAGE
        if caller_number:
            # Use the new lookup tool
            lookup_result = await lookup_client_by_phone(session, phone=caller_number)
            # Adapt to the new confirmation prompt
            if "I found a file for" in lookup_result:
                initial_message = lookup_result
                logger.info(f"{call_id_log_prefix} Caller identified.")

        await session.start(artex_agent, room=ctx.room)
        logger.info(f"{call_id_log_prefix} Agent session started.")
        await session.say(initial_message, allow_interruptions=True)

    except Exception as e:
        logger.error(f"{call_id_log_prefix} An unrecoverable error occurred: {e}", exc_info=True)
        # Backup logging on error is also disabled for now.

    finally:
        logger.info(f"{call_id_log_prefix} Entrypoint finished.")


# --- Standard CLI Runner ---
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
