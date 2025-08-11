import logging
import traceback
import json
from typing import Optional, Dict, Any
import mysql.connector
import os
from json_log_formatter import JSONFormatter

# --- Instance Globale du Logger ---
_logger = logging.getLogger("artex_logger")
_logger.setLevel(logging.INFO)
_logger.propagate = False # Empêche les logs de remonter aux loggers parents

# --- Stockage de la Configuration ---
DB_CONNECTION_PARAMS = None
LOG_FILE_PATH = None

def configure_logger(db_params: Optional[Dict] = None, log_file: Optional[str] = None):
    """
    Configure le logger. À appeler une seule fois au démarrage de l'application.
    - Configure la journalisation sur la console (toujours activée).
    - Configure la journalisation dans un fichier JSON si 'log_file' est fourni.
    - Configure la journalisation dans la base de données si 'db_params' sont fournis.
    """
    global DB_CONNECTION_PARAMS, LOG_FILE_PATH

    # Supprime agressivement les gestionnaires du logger racine pour éviter les doublons d'autres bibliothèques.
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Supprime également les gestionnaires existants sur notre logger spécifique
    if _logger.hasHandlers():
        _logger.handlers.clear()

    # 1. Gestionnaire de Console (Format Standard)
    ch = logging.StreamHandler()
    ch_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(ch_formatter)
    _logger.addHandler(ch)

    # 2. Gestionnaire de Fichier JSON (si le chemin est fourni)
    if log_file:
        LOG_FILE_PATH = log_file
        try:
            fh = logging.FileHandler(LOG_FILE_PATH, encoding='utf-8')
            # Utilise un format personnalisé pour les logs JSON
            json_formatter = JSONFormatter({
                'timestamp': 'asctime',
                'level': 'levelname',
                'message': 'message',
                'name': 'name',
                'source': 'source',
                'call_id': 'call_id',
                'context': 'context',
                'traceback': 'exc_info'
            })
            fh.setFormatter(json_formatter)
            _logger.addHandler(fh)
            _logger.info(f"Logger configuré pour écrire dans le fichier JSON : {log_file}")
        except Exception as e:
            _logger.error(f"Échec de la configuration du logger de fichier à {log_file}: {e}")

    # 3. Connexion à la Base de Données
    if db_params:
        DB_CONNECTION_PARAMS = db_params
        _logger.info("Logger configuré avec les paramètres de la base de données.")
    else:
        _logger.warning("Logger configuré sans paramètres de base de données. La journalisation en base de données sera désactivée.")

def _get_db_connection():
    if not DB_CONNECTION_PARAMS: return None
    try:
        return mysql.connector.connect(**DB_CONNECTION_PARAMS)
    except mysql.connector.Error as e:
        _logger.error(f"CRITIQUE : Impossible de se connecter à la BD pour la journalisation : {e}")
        return None

# --- Fonctions de Journalisation Publiques ---
def log_error(
    source: str,
    message: str,
    exception: Optional[Exception] = None,
    call_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
):
    trace_str = traceback.format_exc() if exception else None

    # Journalise sur la console/fichier via le logger standard
    log_extra = {'source': source, 'call_id': call_id, 'context': context}
    _logger.error(message, exc_info=exception, extra=log_extra)

    # Journalise dans la base de données
    conn = _get_db_connection()
    if not conn: return

    query = """
        INSERT INTO erreurs_systeme
        (id_appel_fk, timestamp_erreur, source_erreur, message_erreur, trace_erreur, contexte_supplementaire)
        VALUES (%s, NOW(), %s, %s, %s, %s)
    """
    try:
        cursor = conn.cursor()
        context_json_str = json.dumps(context) if context else None
        cursor.execute(query, (None, source, message, trace_str, context_json_str))
        conn.commit()
    except Exception as db_err:
        _logger.error("ÉCHEC CRITIQUE DE LA JOURNALISATION EN BD", exc_info=True, extra={'source': 'logger.log_error'})
    finally:
        if conn and conn.is_connected(): conn.close()

def log_activity(
    source: str,
    message: str,
    call_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    level: str = "INFO"
):
    log_extra = {'source': source, 'call_id': call_id, 'context': context}

    # Journalise sur la console/fichier via le logger standard
    _logger.log(logging.getLevelName(level.upper()), message, extra=log_extra)

    # Journalise dans la base de données
    conn = _get_db_connection()
    if not conn: return

    query = """
        INSERT INTO system_activity
        (level, source, message, call_id, additional_context)
        VALUES (%s, %s, %s, %s, %s)
    """
    try:
        cursor = conn.cursor()
        context_json_str = json.dumps(context) if context else None
        cursor.execute(query, (level.upper(), source, message, call_id, context_json_str))
        conn.commit()
    except Exception as db_err:
        _logger.error("Échec de la journalisation d'activité en BD", exc_info=True, extra={'source': 'logger.log_activity'})
    finally:
        if conn and conn.is_connected(): conn.close()
