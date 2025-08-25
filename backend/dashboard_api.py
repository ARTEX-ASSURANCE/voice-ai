from flask import Blueprint, jsonify, request, current_app
import mysql.connector # For type hinting and error handling
 
import datetime

# Assuming ExtranetDatabaseDriver is accessible.
# If db_driver.py is in the same directory (backend), this should work.
from db_driver import ExtranetDatabaseDriver
from error_logger import log_system_error # Assuming error_logger.py is in the same directory

dashboard_bp = Blueprint('dashboard_api', __name__, url_prefix='/api/dashboard')

# Helper to get DB driver instance.
# In a real Flask app, db connections are often managed via app context (g object)
# or specific Flask extensions like Flask-SQLAlchemy.
# For simplicity here, we'll instantiate it or assume it can be accessed if set globally.
def get_db_driver():
    # This is a simplified approach. If ExtranetDatabaseDriver is already instantiated
    # globally in agent.py (as db_driver), we might want to use that instance.
    # However, for API requests that are separate from agent worker lifecycle,
    # a new instance or a request-scoped instance might be better.
    # For now, creating a new instance:
    return ExtranetDatabaseDriver()

def format_datetime_for_json(data):
    """
    Recursively formats datetime objects in data structures to ISO 8601 strings.
    """
    if isinstance(data, list):
        return [format_datetime_for_json(item) for item in data]
    elif isinstance(data, dict):
        return {key: format_datetime_for_json(value) for key, value in data.items()}
    elif isinstance(data, datetime.datetime):
        return data.isoformat()
    return data

@dashboard_bp.route('/kpis', methods=['GET'])
def get_kpis():
    """
    Endpoint pour récupérer les Indicateurs Clés de Performance (KPIs) agrégés.
    """
    db = get_db_driver()
    kpis_data = {}
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor(dictionary=True) # Use dictionary=True for easier access

            # Nombre total d'appels
            cursor.execute("SELECT COUNT(*) as total_appels FROM journal_appels")
            result = cursor.fetchone()
            kpis_data['nombre_total_appels'] = result['total_appels'] if result else 0

            # Durée moyenne des appels (en secondes)
            cursor.execute("SELECT AVG(TIMESTAMPDIFF(SECOND, timestamp_debut, timestamp_fin)) as avg_duration FROM journal_appels WHERE timestamp_fin IS NOT NULL AND timestamp_debut IS NOT NULL")
            result = cursor.fetchone()
            kpis_data['duree_moyenne_appels_secondes'] = float(result['avg_duration']) if result and result['avg_duration'] is not None else 0

            # Nombre d'erreurs critiques
            cursor.execute("SELECT COUNT(*) as total_errors FROM erreurs_systeme") # Peut être filtré par sévérité si ajoutée
            result = cursor.fetchone()
            kpis_data['nombre_erreurs_critiques'] = result['total_errors'] if result else 0

            # Utilisation des outils (Top 5)
            cursor.execute("""
                SELECT nom_outil, COUNT(*) as count
                FROM actions_agent
                WHERE type_action = 'TOOL_CALL' AND nom_outil IS NOT NULL
                GROUP BY nom_outil
                ORDER BY count DESC
                LIMIT 5
            """)
            kpis_data['utilisation_outils_top5'] = cursor.fetchall()

            # Taux de confirmation d'identité réussie
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
    except mysql.connector.Error as db_err:
        log_system_error("dashboard_api.get_kpis", f"Erreur BD KPIs: {db_err}", db_err)
        current_app.logger.error(f"Erreur BD dashboard_api.get_kpis: {db_err}")
        return jsonify({"succes": False, "erreur": "Erreur interne du serveur lors de la récupération des KPIs."}), 500
    except Exception as e:
        log_system_error("dashboard_api.get_kpis", f"Erreur API KPIs: {e}", e)
        current_app.logger.error(f"Erreur API dashboard_api.get_kpis: {e}", exc_info=True)
        return jsonify({"succes": False, "erreur": "Erreur interne du serveur lors de la récupération des KPIs."}), 500


@dashboard_bp.route('/calls', methods=['GET'])
def get_calls():
    """
    Endpoint pour récupérer une liste paginée des appels, avec filtres optionnels.
    """
    db = get_db_driver()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        offset = (page - 1) * per_page

        filters_sql = []
        params_sql = []

        date_debut_str = request.args.get('date_debut')
        if date_debut_str:
            filters_sql.append("ja.timestamp_debut >= %s")
            params_sql.append(date_debut_str)

        date_fin_str = request.args.get('date_fin')
        if date_fin_str: # Pour inclure toute la journée, on pourrait faire <= date_fin_str + 1 jour
            filters_sql.append("ja.timestamp_debut <= DATE_ADD(%s, INTERVAL 1 DAY)")
            params_sql.append(date_fin_str)

        id_adherent = request.args.get('id_adherent', type=int)
        if id_adherent:
            filters_sql.append("ja.id_adherent_contexte = %s")
            params_sql.append(id_adherent)

        numero_appelant = request.args.get('numero_appelant')
        if numero_appelant:
            filters_sql.append("ja.numero_appelant LIKE %s")
            params_sql.append(f"%{numero_appelant}%")


        where_clause = "WHERE " + " AND ".join(filters_sql) if filters_sql else ""

        base_query = f"""
            FROM journal_appels ja
            LEFT JOIN adherents ad ON ja.id_adherent_contexte = ad.id_adherent
            {where_clause}
        """

        count_query = f"SELECT COUNT(*) as total_items {base_query}"

        data_query = f"""
            SELECT ja.id_appel, ja.id_livekit_room, ja.timestamp_debut, ja.timestamp_fin,
                   ja.numero_appelant, ja.id_adherent_contexte, ad.nom, ad.prenom,
                   TIMESTAMPDIFF(SECOND, ja.timestamp_debut, ja.timestamp_fin) as duree_secondes,
                   ja.evaluation_performance_prompt, ja.evaluation_resolution_appel
            {base_query}
            ORDER BY ja.timestamp_debut DESC
            LIMIT %s OFFSET %s
        """

        with db._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            cursor.execute(count_query, tuple(params_sql))
            total_items_result = cursor.fetchone()
            total_items = total_items_result['total_items'] if total_items_result else 0

            params_sql_with_pagination = params_sql + [per_page, offset]
            cursor.execute(data_query, tuple(params_sql_with_pagination))
            calls = cursor.fetchall()

        return jsonify({
            "succes": True,
            "donnees": format_datetime_for_json(calls),
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_items": total_items,
                "total_pages": (total_items + per_page - 1) // per_page if per_page > 0 else 0
            }
        }), 200
    except mysql.connector.Error as db_err:
        current_app.logger.error(f"Erreur BD dashboard_api.get_calls: {db_err}")
        log_system_error("dashboard_api.get_calls", f"Erreur BD: {db_err}", db_err)
        return jsonify({"succes": False, "erreur": "Erreur interne du serveur lors de la récupération des appels."}), 500
    except Exception as e:
        current_app.logger.error(f"Erreur API dashboard_api.get_calls: {e}", exc_info=True)
        log_system_error("dashboard_api.get_calls", f"Erreur API: {e}", e)
        return jsonify({"succes": False, "erreur": "Erreur interne du serveur lors de la récupération des appels."}), 500


@dashboard_bp.route('/calls/<int:call_id>', methods=['GET'])
def get_call_details(call_id):
    """
    Endpoint pour récupérer les détails d'un appel spécifique.
    """
    db = get_db_driver()
    call_details_response = {}
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # Informations de l'appel
            cursor.execute("""
                SELECT ja.*, ad.nom, ad.prenom
                FROM journal_appels ja
                LEFT JOIN adherents ad ON ja.id_adherent_contexte = ad.id_adherent
                WHERE ja.id_appel = %s
            """, (call_id,))
            call_info = cursor.fetchone()
            if not call_info:
                return jsonify({"succes": False, "erreur": "Appel non trouvé."}), 404
            call_details_response['informations_appel'] = call_info

            # Actions de l'agent
            cursor.execute("SELECT * FROM actions_agent WHERE id_appel_fk = %s ORDER BY timestamp_action ASC", (call_id,))
            call_details_response['actions_agent'] = cursor.fetchall()

            # Interactions BD
            cursor.execute("SELECT * FROM interactions_bd WHERE id_appel_fk = %s ORDER BY timestamp_interaction ASC", (call_id,))
            call_details_response['interactions_bd'] = cursor.fetchall()

            # Erreurs pour cet appel
            cursor.execute("SELECT * FROM erreurs_systeme WHERE id_appel_fk = %s ORDER BY timestamp_erreur ASC", (call_id,))
            call_details_response['erreurs_appel'] = cursor.fetchall()

        return jsonify({"succes": True, "donnees": format_datetime_for_json(call_details_response)}), 200
    except mysql.connector.Error as db_err:
        current_app.logger.error(f"Erreur BD dashboard_api.get_call_details pour ID {call_id}: {db_err}")
        log_system_error("dashboard_api.get_call_details", f"Erreur BD: {db_err}", db_err, id_appel_fk=call_id)
        return jsonify({"succes": False, "erreur": "Erreur interne du serveur."}), 500
    except Exception as e:
        current_app.logger.error(f"Erreur API dashboard_api.get_call_details pour ID {call_id}: {e}", exc_info=True)
        log_system_error("dashboard_api.get_call_details", f"Erreur API: {e}", e, id_appel_fk=call_id)
        return jsonify({"succes": False, "erreur": "Erreur interne du serveur."}), 500


@dashboard_bp.route('/db_log', methods=['GET'])
def get_db_log():
    """
    Endpoint pour récupérer les logs d'interactions avec la base de données, paginés.
    """
    db = get_db_driver()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        offset = (page - 1) * per_page

        # TODO: Ajouter des filtres (date_debut, date_fin, type_requete, table_affectee)
        filters_sql = []
        params_sql = []
        # Exemple de filtre:
        # type_req = request.args.get('type_requete')
        # if type_req:
        #     filters_sql.append("type_requete = %s")
        #     params_sql.append(type_req)

        where_clause = "WHERE " + " AND ".join(filters_sql) if filters_sql else ""

        count_query = f"SELECT COUNT(*) as total_items FROM interactions_bd {where_clause}"
        data_query = f"SELECT * FROM interactions_bd {where_clause} ORDER BY timestamp_interaction DESC LIMIT %s OFFSET %s"

        with db._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(count_query, tuple(params_sql))
            total_items = cursor.fetchone()['total_items']

            params_sql_with_pagination = params_sql + [per_page, offset]
            cursor.execute(data_query, tuple(params_sql_with_pagination))
            logs = cursor.fetchall()

        return jsonify({
            "succes": True,
            "donnees": format_datetime_for_json(logs),
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_items": total_items,
                "total_pages": (total_items + per_page - 1) // per_page if per_page > 0 else 0
            }
        }), 200
    except mysql.connector.Error as db_err:
        current_app.logger.error(f"Erreur BD dashboard_api.get_db_log: {db_err}")
        log_system_error("dashboard_api.get_db_log", f"Erreur BD: {db_err}", db_err)
        return jsonify({"succes": False, "erreur": "Erreur interne du serveur."}), 500
    except Exception as e:
        current_app.logger.error(f"Erreur API dashboard_api.get_db_log: {e}", exc_info=True)
        log_system_error("dashboard_api.get_db_log", f"Erreur API: {e}", e)
        return jsonify({"succes": False, "erreur": "Erreur interne du serveur."}), 500


@dashboard_bp.route('/errors', methods=['GET'])
def get_error_log():
    """
    Endpoint pour récupérer les logs d'erreurs système, paginés.
    """
    db = get_db_driver()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        offset = (page - 1) * per_page

        # TODO: Ajouter des filtres (date_debut, date_fin, source_erreur)
        filters_sql = []
        params_sql = []
        # Exemple:
        # source_err = request.args.get('source_erreur')
        # if source_err:
        #     filters_sql.append("source_erreur = %s")
        #     params_sql.append(source_err)

        where_clause = "WHERE " + " AND ".join(filters_sql) if filters_sql else ""

        count_query = f"SELECT COUNT(*) as total_items FROM erreurs_systeme {where_clause}"
        data_query = f"SELECT * FROM erreurs_systeme {where_clause} ORDER BY timestamp_erreur DESC LIMIT %s OFFSET %s"

        with db._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(count_query, tuple(params_sql))
            total_items = cursor.fetchone()['total_items']

            params_sql_with_pagination = params_sql + [per_page, offset]
            cursor.execute(data_query, tuple(params_sql_with_pagination))
            errors = cursor.fetchall()

        return jsonify({
            "succes": True,
            "donnees": format_datetime_for_json(errors),
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_items": total_items,
                "total_pages": (total_items + per_page - 1) // per_page if per_page > 0 else 0
            }
        }), 200
    except mysql.connector.Error as db_err:
        current_app.logger.error(f"Erreur BD dashboard_api.get_error_log: {db_err}")
        log_system_error("dashboard_api.get_error_log", f"Erreur BD: {db_err}", db_err)
        return jsonify({"succes": False, "erreur": "Erreur interne du serveur."}), 500
    except Exception as e:
        current_app.logger.error(f"Erreur API dashboard_api.get_error_log: {e}", exc_info=True)
        log_system_error("dashboard_api.get_error_log", f"Erreur API: {e}", e)
        return jsonify({"succes": False, "erreur": "Erreur interne du serveur."}), 500

# Pour que current_app.logger fonctionne correctement, Flask app doit être configurée.
# Si ce fichier est séparé, le logger Flask standard est accessible via current_app.
# Les appels à log_system_error sont commentés car error_logger.py n'est pas encore
# complètement intégré et testé pour éviter les dépendances circulaires avec db_driver utilisé par error_logger lui-même.
# Une fois error_logger stabilisé, ces appels peuvent être décommentés.
