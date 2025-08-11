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

# --- Chargement de l'Environnement & Configuration du Logger ---
load_dotenv()

# Configure le logger au démarrage
db_params_for_logger = {
    'host': os.getenv("DB_HOST"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'database': os.getenv("DB_NAME"),
    'port': os.getenv("DB_PORT", 3306)
}
log_file_path = os.path.join(os.path.dirname(__file__), 'agent.log')

# Configure avec la journalisation fichier et, si disponible, la journalisation base de données
if not all(db_params_for_logger[key] for key in ['host', 'user', 'password', 'database']):
    configure_logger(log_file=log_file_path)
    log_activity("agent.startup", "Variables d'environnement BD manquantes, journalisation BD désactivée.", level="WARNING")
else:
    configure_logger(db_params=db_params_for_logger, log_file=log_file_path)

# --- Point d'Entrée Principal de l'Agent ---
async def entrypoint(ctx: JobContext):
    """
    Cette fonction est exécutée pour chaque nouvel appel que l'agent traite.
    """
    await asyncio.sleep(2)

    call_id = ctx.job.id
    log_activity("agent.entrypoint", "Nouvel appel reçu", call_id=call_id, context={"room_name": ctx.room.name})

    db_driver = None
    session = None
    
    try:
        db_driver = ExtranetDatabaseDriver()
        artex_agent = ArtexAgent(db_driver=db_driver)

        await ctx.connect()
        log_activity("agent.entrypoint", "Agent connecté à la room", call_id=call_id)

        session = AgentSession()
        
        caller_number = None
        if ctx.room.metadata:
            metadata = json.loads(ctx.room.metadata)
            caller_number = metadata.get('caller_number')
            log_activity("agent.entrypoint", "Numéro de l'appelant extrait", call_id=call_id, context={"caller_number": caller_number})

        initial_userdata = artex_agent.get_initial_userdata()
        session.userdata = initial_userdata

        initial_message = WELCOME_MESSAGE
        if caller_number:
            # Utilise le nouvel outil de recherche
            lookup_result = await lookup_client_by_phone(session, phone=caller_number)
            # S'adapte à la nouvelle invite de confirmation
            if "J'ai trouvé un dossier pour" in lookup_result:
                initial_message = lookup_result
                log_activity("agent.entrypoint", "Appelant identifié via recherche par téléphone", call_id=call_id)

        await session.start(artex_agent, room=ctx.room)
        log_activity("agent.entrypoint", "Session de l'agent démarrée", call_id=call_id)
        await session.say(initial_message, allow_interruptions=True)

    except Exception as e:
        log_error(
            source="agent.entrypoint",
            message="Une erreur non récupérable est survenue dans le point d'entrée de l'agent",
            exception=e,
            call_id=call_id
        )

    finally:
        log_activity("agent.entrypoint", "Point d'entrée terminé", call_id=call_id)


# --- Lanceur CLI Standard ---
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
