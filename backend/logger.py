import logging
import traceback
import json
from typing import Optional, Dict, Any
import mysql.connector
import os
from json_log_formatter import JSONFormatter

# --- Global Logger Instance ---
_logger = logging.getLogger("artex_logger")
_logger.setLevel(logging.INFO)
_logger.propagate = False # Prevent duplicate logs in parent loggers

# --- Configuration Store ---
DB_CONNECTION_PARAMS = None
LOG_FILE_PATH = None

def configure_logger(db_params: Optional[Dict] = None, log_file: Optional[str] = None):
    """
    Configures the logger. To be called once at application startup.
    - Sets up console logging (always on).
    - Sets up JSON file logging if 'log_file' is provided.
    - Sets up database logging if 'db_params' are provided.
    """
    global DB_CONNECTION_PARAMS, LOG_FILE_PATH

    # Clear existing handlers to prevent duplication on re-configuration
    if _logger.hasHandlers():
        _logger.handlers.clear()

    # 1. Console Handler (Standard Formatter)
    ch = logging.StreamHandler()
    ch_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(ch_formatter)
    _logger.addHandler(ch)

    # 2. JSON File Handler (if path is provided)
    if log_file:
        LOG_FILE_PATH = log_file
        try:
            fh = logging.FileHandler(LOG_FILE_PATH)
            # Use a custom format for the JSON logs
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
            _logger.info(f"Logger configured to output to JSON file: {log_file}")
        except Exception as e:
            _logger.error(f"Failed to configure file logger at {log_file}: {e}")

    # 3. Database Connection
    if db_params:
        DB_CONNECTION_PARAMS = db_params
        _logger.info("Logger configured with database parameters.")
    else:
        _logger.warning("Logger configured without database parameters. Database logging will be disabled.")

def _get_db_connection():
    if not DB_CONNECTION_PARAMS: return None
    try:
        return mysql.connector.connect(**DB_CONNECTION_PARAMS)
    except mysql.connector.Error as e:
        _logger.error(f"CRITICAL: Could not connect to DB for logging: {e}")
        return None

# --- Public Logging Functions ---
def log_error(
    source: str,
    message: str,
    exception: Optional[Exception] = None,
    call_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
):
    trace_str = traceback.format_exc() if exception else None

    # Log to console/file via standard logger
    log_extra = {'source': source, 'call_id': call_id, 'context': context}
    _logger.error(message, exc_info=exception, extra=log_extra)

    # Log to database
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
        _logger.error("CRITICAL DB LOGGING FAILURE", exc_info=True, extra={'source': 'logger.log_error'})
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

    # Log to console/file via standard logger
    _logger.log(logging.getLevelName(level.upper()), message, extra=log_extra)

    # Log to database
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
        _logger.error("DB activity logging failure", exc_info=True, extra={'source': 'logger.log_activity'})
    finally:
        if conn and conn.is_connected(): conn.close()
