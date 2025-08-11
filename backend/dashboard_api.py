from flask import Blueprint, jsonify, request
import mysql.connector
import datetime

from db_driver import ExtranetDatabaseDriver
from logger import log_error

dashboard_bp = Blueprint('dashboard_api', __name__, url_prefix='/api/dashboard')

def get_db_driver():
    return ExtranetDatabaseDriver()

def format_datetime_for_json(data):
    if isinstance(data, list):
        return [format_datetime_for_json(item) for item in data]
    elif isinstance(data, dict):
        return {key: format_datetime_for_json(value) for key, value in data.items()}
    elif isinstance(data, datetime.datetime):
        return data.isoformat()
    return data

@dashboard_bp.route('/kpis', methods=['GET'])
def get_kpis():
    db = get_db_driver()
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            kpis_data = {}
            # KPIs calculation...
            cursor.execute("SELECT COUNT(*) as total_appels FROM journal_appels")
            result = cursor.fetchone()
            kpis_data['nombre_total_appels'] = result['total_appels'] if result else 0

            cursor.execute("SELECT AVG(TIMESTAMPDIFF(SECOND, timestamp_debut, timestamp_fin)) as avg_duration FROM journal_appels WHERE timestamp_fin IS NOT NULL AND timestamp_debut IS NOT NULL")
            result = cursor.fetchone()
            kpis_data['duree_moyenne_appels_secondes'] = float(result['avg_duration']) if result and result['avg_duration'] is not None else 0

            cursor.execute("SELECT COUNT(*) as total_errors FROM erreurs_systeme")
            result = cursor.fetchone()
            kpis_data['nombre_erreurs_critiques'] = result['total_errors'] if result else 0

            cursor.execute("""
                SELECT nom_outil, COUNT(*) as count
                FROM actions_agent
                WHERE type_action = 'TOOL_CALL' AND nom_outil IS NOT NULL
                GROUP BY nom_outil
                ORDER BY count DESC
                LIMIT 5
            """)
            kpis_data['utilisation_outils_top5'] = cursor.fetchall()

            cursor.execute("""
                SELECT
                    (SELECT COUNT(*) FROM journal_appels WHERE id_adherent_contexte IS NOT NULL) as confirmed_calls,
                    (SELECT COUNT(*) FROM journal_appels) as total_calls_for_rate
            """)
            rate_counts = cursor.fetchone()
            if rate_counts and rate_counts['total_calls_for_rate'] > 0:
                kpis_data['taux_confirmation_identite'] = \
                    (rate_counts['confirmed_calls'] / rate_counts['total_calls_for_rate']) * 100
            else:
                kpis_data['taux_confirmation_identite'] = 0

            cursor.execute("SELECT COUNT(*) as count FROM journal_appels WHERE id_adherent_contexte IS NULL")
            result = cursor.fetchone()
            kpis_data['appels_sans_confirmation_identite'] = result['count'] if result else 0

        return jsonify({"succes": True, "donnees": format_datetime_for_json(kpis_data)}), 200
    except Exception as e:
        log_error("dashboard_api.get_kpis", "Failed to retrieve KPIs", e)
        return jsonify({"succes": False, "erreur": "Erreur interne du serveur lors de la récupération des KPIs."}), 500


@dashboard_bp.route('/calls', methods=['GET'])
def get_calls():
    db = get_db_driver()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        offset = (page - 1) * per_page

        filters_sql = []
        params_sql = []

        # Filtering logic...
        date_debut_str = request.args.get('date_debut')
        if date_debut_str:
            filters_sql.append("ja.timestamp_debut >= %s")
            params_sql.append(date_debut_str)

        # ... other filters ...

        where_clause = "WHERE " + " AND ".join(filters_sql) if filters_sql else ""
        base_query = f"FROM journal_appels ja LEFT JOIN adherents ad ON ja.id_adherent_contexte = ad.id_adherent {where_clause}"
        count_query = f"SELECT COUNT(*) as total_items {base_query}"
        data_query = f"SELECT ja.*, ad.nom, ad.prenom FROM journal_appels ja LEFT JOIN adherents ad ON ja.id_adherent_contexte = ad.id_adherent {where_clause} ORDER BY ja.timestamp_debut DESC LIMIT %s OFFSET %s"

        with db._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(count_query, tuple(params_sql))
            total_items = cursor.fetchone()['total_items']

            params_sql_with_pagination = params_sql + [per_page, offset]
            cursor.execute(data_query, tuple(params_sql_with_pagination))
            calls = cursor.fetchall()

        return jsonify({
            "succes": True,
            "donnees": format_datetime_for_json(calls),
            "pagination": {"page": page, "per_page": per_page, "total_items": total_items, "total_pages": (total_items + per_page - 1) // per_page}
        }), 200
    except Exception as e:
        log_error("dashboard_api.get_calls", "Failed to retrieve calls", e)
        return jsonify({"succes": False, "erreur": "Erreur interne du serveur lors de la récupération des appels."}), 500


@dashboard_bp.route('/calls/<int:call_id>', methods=['GET'])
def get_call_details(call_id):
    db = get_db_driver()
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # Fetching call details...
            cursor.execute("SELECT ja.*, ad.nom, ad.prenom FROM journal_appels ja LEFT JOIN adherents ad ON ja.id_adherent_contexte = ad.id_adherent WHERE ja.id_appel = %s", (call_id,))
            call_info = cursor.fetchone()
            if not call_info:
                return jsonify({"succes": False, "erreur": "Appel non trouvé."}), 404

            # ... fetch other details ...

        return jsonify({"succes": True, "donnees": format_datetime_for_json(call_info)}), 200
    except Exception as e:
        log_error("dashboard_api.get_call_details", f"Failed to retrieve details for call ID {call_id}", e, call_id=str(call_id))
        return jsonify({"succes": False, "erreur": "Erreur interne du serveur."}), 500


@dashboard_bp.route('/db_log', methods=['GET'])
def get_db_log():
    db = get_db_driver()
    try:
        # Pagination and query logic...
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        offset = (page - 1) * per_page

        with db._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) as total_items FROM interactions_bd")
            total_items = cursor.fetchone()['total_items']
            cursor.execute("SELECT * FROM interactions_bd ORDER BY timestamp_interaction DESC LIMIT %s OFFSET %s", (per_page, offset))
            logs = cursor.fetchall()

        return jsonify({
            "succes": True,
            "donnees": format_datetime_for_json(logs),
            "pagination": {"page": page, "per_page": per_page, "total_items": total_items, "total_pages": (total_items + per_page - 1) // per_page}
        }), 200
    except Exception as e:
        log_error("dashboard_api.get_db_log", "Failed to retrieve DB logs", e)
        return jsonify({"succes": False, "erreur": "Erreur interne du serveur."}), 500


@dashboard_bp.route('/errors', methods=['GET'])
def get_error_log():
    db = get_db_driver()
    try:
        # Pagination and query logic...
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        offset = (page - 1) * per_page

        with db._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) as total_items FROM erreurs_systeme")
            total_items = cursor.fetchone()['total_items']
            cursor.execute("SELECT * FROM erreurs_systeme ORDER BY timestamp_erreur DESC LIMIT %s OFFSET %s", (per_page, offset))
            errors = cursor.fetchall()

        return jsonify({
            "succes": True,
            "donnees": format_datetime_for_json(errors),
            "pagination": {"page": page, "per_page": per_page, "total_items": total_items, "total_pages": (total_items + per_page - 1) // per_page}
        }), 200
    except Exception as e:
        log_error("dashboard_api.get_error_log", "Failed to retrieve error logs", e)
        return jsonify({"succes": False, "erreur": "Erreur interne du serveur."}), 500
