# ai/backend/agent.py (Version Failsafe pour la Transcription)

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
from tools import lookup_adherent_by_telephone
from error_logger import set_db_connection_params

# --- Configuration du Logging (Inchangé) ---
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("artex_agent")
logger.setLevel(logging.INFO)

load_dotenv()

# --- Configuration Initiale (Error Logger) ---
try:
    db_params_for_error_logger = {
        'host': os.getenv("DB_HOST"), 'user': os.getenv("DB_USER"),
        'password': os.getenv("DB_PASSWORD"), 'database': os.getenv("DB_NAME"),
        'port': os.getenv("DB_PORT", 3306)
    }
    if not all(db_params_for_error_logger[key] for key in ['host', 'user', 'password', 'database']):
        raise ValueError("Variables d'environnement BD manquantes pour error_logger.")
    set_db_connection_params(db_params_for_error_logger)
except Exception as e:
    logger.critical(f"CRITICAL: Échec de la configuration du error_logger au démarrage: {e}", exc_info=True)


# --- Main Agent Entrypoint ---
async def entrypoint(ctx: JobContext):
    """
    Cette fonction est exécutée pour chaque nouvel appel que l'agent gère.
    """
    await asyncio.sleep(2)

    call_id_log_prefix = f"[{ctx.job.id}]"
    logger.info(f"{call_id_log_prefix} Nouvel appel reçu pour la room: {ctx.room.name}")

    # Initialisation avant le bloc try pour qu'ils soient accessibles partout
    db_driver = None
    session = None
    
    try:
        db_driver = ExtranetDatabaseDriver()
        artex_agent = ArtexAgent(db_driver=db_driver)

        await ctx.connect()
        logger.info(f"{call_id_log_prefix} Agent connecté à la room.")

        async def shutdown_hook():
            # Ce hook s'exécute lors d'une déconnexion NORMALE
            if session:
                logger.info(f"{call_id_log_prefix} Le crochet d'arrêt est initié (déconnexion normale). Sauvegarde des données finales...")
                history_list = [item.model_dump() for item in session.history.items]
                transcription_json = json.dumps(history_list, ensure_ascii=False)
                
                call_journal_id = session.userdata.get('current_call_journal_id')
                if call_journal_id and db_driver:
                    db_driver.enregistrer_fin_appel(
                        id_appel=call_journal_id,
                        transcription=transcription_json,
                        statut='Terminé'
                    )
                    logger.info(f"{call_id_log_prefix} Données finales sauvegardées pour l'ID: {call_journal_id}")

        ctx.add_shutdown_callback(shutdown_hook)

        session = AgentSession()
        
        caller_number = None
        if ctx.room.metadata:
            metadata = json.loads(ctx.room.metadata)
            caller_number = metadata.get('caller_number')
        
        current_call_journal_id = db_driver.enregistrer_debut_appel(id_livekit_room=ctx.job.id, numero_appelant=caller_number)
        logger.info(f"{call_id_log_prefix} Appel enregistré dans la BDD avec l'ID: {current_call_journal_id}. Appelant: {caller_number or 'Inconnu'}")
        
        initial_userdata = artex_agent.get_initial_userdata()
        initial_userdata["current_call_journal_id"] = current_call_journal_id
        assert session is not None
        session.userdata = initial_userdata

        initial_message = WELCOME_MESSAGE
        if caller_number:
            lookup_result = await lookup_adherent_by_telephone(session, telephone=caller_number)
            if "Bonjour, je m'adresse bien à" in lookup_result:
                initial_message = lookup_result
                logger.info(f"{call_id_log_prefix} Appelant identifié.")

        assert session is not None
        await session.start(artex_agent, room=ctx.room)
        logger.info(f"{call_id_log_prefix} Session de l'agent démarrée.")
        await session.say(initial_message, allow_interruptions=True)

    except Exception as e:
        logger.error(f"{call_id_log_prefix} Une erreur irrécupérable s'est produite: {e}", exc_info=True)
        
        # --- AJOUT DE LA SAUVEGARDE DE SECOURS ---
        # Cette partie s'exécute si l'appel est interrompu par une ERREUR
        if session and db_driver:
            logger.info(f"{call_id_log_prefix} Tentative de sauvegarde de la transcription après erreur...")
            history_list = [item.model_dump() for item in session.history.items]
            transcription_json = json.dumps(history_list, ensure_ascii=False)
            call_journal_id = session.userdata.get('current_call_journal_id')
            if call_journal_id:
                db_driver.enregistrer_fin_appel(
                    id_appel=call_journal_id,
                    transcription=transcription_json,
                    statut='Interrompu (Erreur)' # On met un statut spécifique
                )
                logger.info(f"{call_id_log_prefix} Transcription de secours sauvegardée pour l'ID: {call_journal_id}")
        # --- FIN DE L'AJOUT ---

    finally:
        logger.info(f"{call_id_log_prefix} L'entrypoint est terminé.")


# --- Standard CLI Runner ---
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))