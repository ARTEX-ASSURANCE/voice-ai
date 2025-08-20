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
    Agent
)
from livekit.plugins import google, silero, deepgram
from langchain_google_genai import ChatGoogleGenerativeAI

import redis
# Adjusted imports for the new project structure
from src.data_access.driver import ExtranetDatabaseDriver
from src.shared.memory import MemoryManager
from src.shared.prompts import INSTRUCTIONS, WELCOME_MESSAGE
from src.execution.tools import (
    lookup_adherent_by_email,
    lookup_adherent_by_telephone,
    lookup_adherent_by_fullname,
    confirm_identity,
    get_adherent_details,
    clear_context,
    update_contact_information,
    list_available_products,
    get_product_guarantees,
    list_adherent_contracts,
    create_claim,
    request_quote,
    log_issue,
    send_confirmation_email,
    schedule_callback_with_advisor,
    expliquer_garantie_specifique,
    envoyer_document_adherent,
    qualifier_prospect_pour_conseiller,
    enregistrer_feedback_appel,
    transfer_call,
    hangup_call
)
# error_logger is deprecated and will be removed.
# from error_logger import log_system_error, set_db_connection_params

# --- Agent Definition ---

class ArtexAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=INSTRUCTIONS,
            llm=google.LLM(model="gemini-2.0-flash-lite", temperature=0.3),
            tts=google.TTS(language="fr-FR", voice_name="fr-FR-Chirp3-HD-Zephyr"),
            stt=deepgram.STT(model="nova-2", language="fr", endpointing_ms=300),
            vad=silero.VAD.load(min_silence_duration=0.3),
            tools=[
                lookup_adherent_by_email,
                lookup_adherent_by_telephone,
                lookup_adherent_by_fullname,
                confirm_identity,
                get_adherent_details,
                clear_context,
                list_available_products,
                get_product_guarantees,
                update_contact_information,
                list_adherent_contracts,
                create_claim,
                request_quote,
                log_issue,
                send_confirmation_email,
                schedule_callback_with_advisor,
                expliquer_garantie_specifique,
                envoyer_document_adherent,
                qualifier_prospect_pour_conseiller,
                enregistrer_feedback_appel,
                transfer_call,
                hangup_call
            ],
        )
        self.task_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite", temperature=0.3)
        logging.info("Schéma ArtexAgent configuré avec des LLMs séparés pour la conversation et les tâches.")

    def get_initial_userdata(self) -> dict:
        # The context is now fully managed by the MemoryManager and set in the entrypoint.
        return {}

# --- Worker Entrypoint ---

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("artex_agent_worker")
logger.setLevel(logging.INFO)

load_dotenv()

# The error_logger configuration has been removed as it is part of the old,
# tightly-coupled architecture. Error handling will be managed by the services directly.

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
        # 1. Initialize dependencies
        db_driver = ExtranetDatabaseDriver()
        redis_client = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=os.getenv("REDIS_PORT", 6379), db=0)
        memory_manager = MemoryManager(session_id=ctx.job.id, redis_client=redis_client, db_driver=db_driver)

        # 2. Agent and Session setup
        artex_agent = ArtexAgent()
        session = AgentSession()
        session.userdata['memory'] = memory_manager

        await ctx.connect()
        logger.info(f"{call_id_log_prefix} Agent connected to room.")

        # 3. Setup shutdown hook
        async def shutdown_hook():
            if session:
                logger.info(f"{call_id_log_prefix} Shutdown hook initiated. Saving final data...")
                history_list = [item.model_dump() for item in session.history.items]
                transcription_json = json.dumps(history_list, ensure_ascii=False)

                call_journal_id = memory_manager.get_session_data('current_call_journal_id')
                if call_journal_id and db_driver:
                    db_driver.enregistrer_fin_appel(
                        id_appel=call_journal_id,
                        transcription=transcription_json,
                        statut='Terminé'
                    )
                    logger.info(f"{call_id_log_prefix} Final data saved for ID: {call_journal_id}")

        ctx.add_shutdown_callback(shutdown_hook)

        # 4. Initial call processing
        caller_number = None
        if ctx.room.metadata:
            metadata = json.loads(ctx.room.metadata)
            caller_number = metadata.get('caller_number')

        current_call_journal_id = db_driver.enregistrer_debut_appel(id_livekit_room=ctx.job.id, numero_appelant=caller_number)
        memory_manager.set_session_data("current_call_journal_id", current_call_journal_id)
        logger.info(f"{call_id_log_prefix} Call registered in DB with ID: {current_call_journal_id}. Caller: {caller_number or 'Unknown'}")

        # 5. Initial message and lookup
        initial_message = WELCOME_MESSAGE
        if caller_number:
            # The tool now gets the memory manager from the context
            lookup_result = await lookup_adherent_by_telephone(session, telephone=caller_number)
            if "Bonjour, je m'adresse bien à" in lookup_result:
                initial_message = lookup_result
                logger.info(f"{call_id_log_prefix} Caller identified.")

        # 6. Start the agent loop
        await session.start(agent=artex_agent, room=ctx.room)
        logger.info(f"{call_id_log_prefix} Agent session started.")
        await session.say(initial_message, allow_interruptions=True)

    except Exception as e:
        logger.error(f"{call_id_log_prefix} An unrecoverable error occurred: {e}", exc_info=True)

        if session and memory_manager:
            logger.info(f"{call_id_log_prefix} Attempting to save transcription after error...")
            history_list = [item.model_dump() for item in session.history.items]
            transcription_json = json.dumps(history_list, ensure_ascii=False)
            call_journal_id = memory_manager.get_session_data('current_call_journal_id')
            if call_journal_id:
                db_driver = memory_manager.db_driver
                if db_driver:
                    db_driver.enregistrer_fin_appel(
                        id_appel=call_journal_id,
                        transcription=transcription_json,
                        statut='Interrupted (Error)'
                    )
                    logger.info(f"{call_id_log_prefix} Backup transcription saved for ID: {call_journal_id}")

    finally:
        logger.info(f"{call_id_log_prefix} Entrypoint finished.")


# --- Standard CLI Runner ---
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
