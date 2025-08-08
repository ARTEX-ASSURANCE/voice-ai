import logging
import traceback
import json
from typing import Optional, Dict, Any
import mysql.connector # Needed for type hinting if db_driver is passed, or for direct connection
# To avoid circular dependency if ExtranetDatabaseDriver also uses log_system_error,
# this module should ideally take connection parameters or a pre-configured db connection factory.

# Get the standard Python logger
logger = logging.getLogger(__name__)

# Global variable to hold DB connection parameters, to be set by the main application.
# This is a simple way to avoid direct dependency on ExtranetDatabaseDriver here,
# preventing circular imports if ExtranetDatabaseDriver also wants to use this logger.
DB_CONNECTION_PARAMS = None

def set_db_connection_params(params: Dict):
    """
    Sets the database connection parameters for the error logger.
    To be called once at application startup.
    """
    global DB_CONNECTION_PARAMS
    DB_CONNECTION_PARAMS = params

def _get_db_connection_for_error_logging():
    """
    Establishes a new database connection specifically for error logging.
    Returns a connection object or None if parameters are not set or connection fails.
    """
    if not DB_CONNECTION_PARAMS:
        logger.error("CRITIQUE: Paramètres de connexion BD non configurés pour error_logger.")
        return None
    try:
        conn = mysql.connector.connect(**DB_CONNECTION_PARAMS)
        return conn
    except mysql.connector.Error as e:
        logger.error(f"CRITIQUE: Impossible de se connecter à la BD pour la journalisation des erreurs: {e}")
        return None

def log_system_error(
    source_erreur: str,
    message_erreur: str,
    exception_obj: Optional[Exception] = None,
    id_appel_fk: Optional[int] = None,
    contexte_supplementaire: Optional[Dict[str, Any]] = None
):
    """
    Journalise une erreur dans la table 'erreurs_systeme' et dans le logger Python standard.
    """
    trace_str = None
    if exception_obj:
        trace_str = traceback.format_exc()
        if not message_erreur: # Si aucun message spécifique, utiliser le message de l'exception
            message_erreur = str(exception_obj)

    # Journaliser dans le logger Python standard en premier
    log_message_std = f"ERREUR SYSTÈME: Source: {source_erreur}, Message: {message_erreur}"
    if id_appel_fk is not None: # Vérifier explicitement None car 0 est un ID valide
        log_message_std += f", ID Appel FK: {id_appel_fk}"
    if contexte_supplementaire:
        log_message_std += f", Contexte: {json.dumps(contexte_supplementaire)}" # S'assurer que le contexte est sérialisable pour le log std

    # Ne pas inclure la trace complète dans le log INFO/ERROR initial, seulement dans le log de la DB ou un log DEBUG.
    # logger.error(log_message_std) # Journalisation simple
    # Pour une journalisation plus détaillée avec la trace si disponible :
    if trace_str:
        logger.error(f"{log_message_std}\nTrace:\n{trace_str}")
    else:
        logger.error(log_message_std)


    # Journaliser dans la base de données
    conn = _get_db_connection_for_error_logging()
    if not conn:
        logger.error("CRITIQUE: Connexion BD non disponible pour error_logger, l'erreur système ne sera pas journalisée dans la BD.")
        return

    query = """
        INSERT INTO erreurs_systeme
        (id_appel_fk, timestamp_erreur, source_erreur, message_erreur, trace_erreur, contexte_supplementaire)
        VALUES (%s, NOW(), %s, %s, %s, %s)
    """
    try:
        cursor = conn.cursor()
        contexte_json_str = json.dumps(contexte_supplementaire) if contexte_supplementaire else None
        cursor.execute(query, (id_appel_fk, source_erreur, message_erreur, trace_str, contexte_json_str))
        conn.commit()
    except mysql.connector.Error as db_log_err:
        # Si la journalisation dans la BD échoue, on ne peut que le logger dans le log standard.
        logger.critical(f"ÉCHEC CRITIQUE DE JOURNALISATION D'ERREUR: Impossible d'écrire dans erreurs_systeme. Erreur originale: '{message_erreur}'. Erreur de journalisation BD: {db_log_err}")
    except TypeError as json_err: # Erreur de sérialisation JSON
        logger.critical(f"ÉCHEC CRITIQUE DE JOURNALISATION D'ERREUR: Erreur de sérialisation JSON pour contexte_supplementaire. Erreur originale: '{message_erreur}'. Erreur JSON: {json_err}")
        # Tentative de journalisation sans le contexte JSON problématique
        try:
            cursor = conn.cursor()
            cursor.execute(query, (id_appel_fk, source_erreur, message_erreur, trace_str, json.dumps({"json_serialization_error": str(json_err)})))
            conn.commit()
        except Exception as fallback_err:
            logger.critical(f"ÉCHEC CRITIQUE DE JOURNALISATION D'ERREUR: Tentative de secours échouée. Erreur: {fallback_err}")
    finally:
        if conn and conn.is_connected():
            conn.close()

# Exemple d'utilisation (ne pas exécuter directement ici)
# if __name__ == '__main__':
#     # Simuler la configuration des paramètres de connexion BD au démarrage de l'application principale
#     # Ceci devrait être fait dans votre server.py ou équivalent.
#     test_db_params = {
#         'host': 'localhost',
#         'user': 'your_user',
#         'password': 'your_password',
#         'database': 'your_database_name'
#     }
#     set_db_connection_params(test_db_params)
#
#     logging.basicConfig(level=logging.INFO) # Configurer le logger standard pour voir les messages
#
#     try:
#         # Simuler une erreur
#         x = 1 / 0
#     except Exception as e:
#         log_system_error("test_script.main_logic", "Une division par zéro s'est produite.", e, id_appel_fk=123, contexte_supplementaire={"valeur_x": 1, "operation": "division"})
#
#     log_system_error("test_script.custom_error", "Ceci est une erreur personnalisée sans exception.", id_appel_fk=456)
