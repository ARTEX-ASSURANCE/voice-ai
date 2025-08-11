import logging
import traceback
import json
from typing import Optional, Dict, Any
import mysql.connector
import os

# --- Standard Logger Configuration ---

# Get the standard Python logger
_logger = logging.getLogger("artex_logger")
_logger.setLevel(logging.INFO)

# Create a handler for console output
if not _logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    _logger.addHandler(ch)

# --- Database Connection ---

DB_CONNECTION_PARAMS = None

def configure_logger(db_params: Optional[Dict] = None):
    """
    Configures the logger, including setting DB connection parameters.
    To be called once at application startup.
    """
    global DB_CONNECTION_PARAMS
    if db_params:
        DB_CONNECTION_PARAMS = db_params
        _logger.info("Logger configured with database parameters.")
    else:
        _logger.warning("Logger configured without database parameters. Database logging will be disabled.")

def _get_db_connection():
    """
    Establishes a new database connection.
    Returns a connection object or None if parameters are not set or connection fails.
    """
    if not DB_CONNECTION_PARAMS:
        return None
    try:
        conn = mysql.connector.connect(**DB_CONNECTION_PARAMS)
        return conn
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
    """
    Logs a system error to the console and the 'erreurs_systeme' database table.
    """
    trace_str = None
    if exception:
        trace_str = traceback.format_exc()
        if not message:
            message = str(exception)

    # 1. Log to standard logger
    log_message_std = f"ERROR: Source: {source}, Message: {message}"
    if call_id:
        log_message_std += f", CallID: {call_id}"
    if context:
        # Ensure context is serializable for standard log
        try:
            context_str = json.dumps(context)
            log_message_std += f", Context: {context_str}"
        except TypeError:
            log_message_std += ", Context: (unserializable)"

    _logger.error(log_message_std)
    if trace_str:
        _logger.debug(f"Traceback for the above error:\n{trace_str}")


    # 2. Log to database
    conn = _get_db_connection()
    if not conn:
        _logger.warning("DB connection not available. Skipping database error log.")
        return

    query = """
        INSERT INTO erreurs_systeme
        (id_appel_fk, timestamp_erreur, source_erreur, message_erreur, trace_erreur, contexte_supplementaire)
        VALUES (%s, NOW(), %s, %s, %s, %s)
    """
    try:
        cursor = conn.cursor()
        context_json_str = json.dumps(context) if context else None
        # Note: The table expects id_appel_fk as an INT, but we have a string call_id.
        # This will be logged in context for now. A schema change would be needed to store call_id directly.
        # For now, we'll pass NULL for id_appel_fk unless it can be mapped.
        # This is a limitation of the current schema vs desired logging.
        cursor.execute(query, (None, source, message, trace_str, context_json_str))
        conn.commit()
    except mysql.connector.Error as db_log_err:
        _logger.critical(f"CRITICAL LOGGING FAILURE: Could not write to erreurs_systeme. Original error: '{message}'. DB log error: {db_log_err}")
    except TypeError as json_err:
        _logger.critical(f"CRITICAL LOGGING FAILURE: JSON serialization error for context. Original error: '{message}'. JSON error: {json_err}")
        # Attempt to log without the problematic context
        try:
            cursor = conn.cursor()
            cursor.execute(query, (None, source, message, trace_str, json.dumps({"json_serialization_error": str(json_err)})))
            conn.commit()
        except Exception as fallback_err:
            _logger.critical(f"CRITICAL LOGGING FAILURE: Fallback logging attempt failed. Error: {fallback_err}")
    finally:
        if conn and conn.is_connected():
            conn.close()


def log_activity(
    source: str,
    message: str,
    call_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    level: str = "INFO"
):
    """
    Logs a system activity to the console and the 'system_activity' database table.
    """
    # 1. Log to standard logger
    log_message_std = f"ACTIVITY: Source: {source}, Message: {message}"
    if call_id:
        log_message_std += f", CallID: {call_id}"
    if context:
        try:
            context_str = json.dumps(context)
            log_message_std += f", Context: {context_str}"
        except TypeError:
            log_message_std += ", Context: (unserializable)"

    _logger.info(log_message_std) # Always log activities at INFO level to console for visibility

    # 2. Log to database
    conn = _get_db_connection()
    if not conn:
        # Not logging a warning here to avoid flooding logs if DB is intentionally not configured
        return

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
    except mysql.connector.Error as db_log_err:
        _logger.error(f"DB Logging Failure: Could not write to system_activity. Message: '{message}'. DB Error: {db_log_err}")
    finally:
        if conn and conn.is_connected():
            conn.close()
