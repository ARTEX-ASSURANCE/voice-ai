import os
from flask import Flask, request
from dotenv import load_dotenv
from flask_cors import CORS
from livekit.api import LiveKitAPI, AccessToken, VideoGrants, ListRoomsRequest # Importations mises à jour
import uuid
import os # Assurez-vous que os est importé pour getenv

# Importer le logger d'erreurs et sa fonction de configuration
from error_logger import set_db_connection_params, log_system_error

load_dotenv()

# Configurer les paramètres de connexion pour le error_logger au démarrage
# Ceci suppose que les mêmes variables d'environnement DB_* sont utilisées par db_driver et error_logger
try:
    db_params_for_error_logger = {
        'host': os.getenv("DB_HOST"),
        'user': os.getenv("DB_USER"),
        'password': os.getenv("DB_PASSWORD"),
        'database': os.getenv("DB_NAME"),
        'port': os.getenv("DB_PORT", 3306) # Ajouter le port avec une valeur par défaut
    }
    if not all(db_params_for_error_logger[key] for key in ['host', 'user', 'password', 'database']):
        raise ValueError("Variables d'environnement BD manquantes pour error_logger.")
    set_db_connection_params(db_params_for_error_logger)
except ValueError as ve:
    # Utiliser le logger standard Python si la configuration de error_logger échoue.
    import logging
    logging.critical(f"Échec de la configuration des paramètres BD pour error_logger: {ve}. La journalisation des erreurs BD sera désactivée.")
except Exception as e:
    import logging
    logging.critical(f"Erreur inattendue lors de la configuration de error_logger: {e}. La journalisation des erreurs BD sera désactivée.")


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Enregistrer le blueprint du tableau de bord
from dashboard_api import dashboard_bp
app.register_blueprint(dashboard_bp)

async def generate_room_name():
    name = "room-" + str(uuid.uuid4())[:8]
    rooms = await get_rooms()
    while name in rooms:
        name = "room-" + str(uuid.uuid4())[:8]
    return name

async def get_rooms():
    livekit_host = os.getenv("LIVEKIT_URL")
    livekit_api_key = os.getenv("LIVEKIT_API_KEY")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([livekit_host, livekit_api_key, livekit_api_secret]):
        print("Avertissement : L'URL du serveur LiveKit, la clé API ou le secret API ne sont pas entièrement configurés pour get_rooms.")
        return [] # Retourner une liste vide car l'appel API échouera

    # Utiliser l'importation directe de LiveKitAPI, ListRoomsRequest
    lk_api = LiveKitAPI(host=livekit_host, api_key=livekit_api_key, api_secret=livekit_api_secret)
    try:
        rooms_response = await lk_api.room.list_rooms(ListRoomsRequest())
    finally:
        await lk_api.aclose()
    
    return [room.name for room in rooms_response.rooms]

@app.route("/create-token", methods=['POST'])
async def get_token():
    data = request.get_json()
    room_name = data.get("room_name")
    identity = data.get("identity", "default-identity") # Identité par défaut

    if not room_name:
        room_name = await generate_room_name() # Conserver la logique originale pour générer la salle si non fournie

    livekit_api_key = os.getenv("LIVEKIT_API_KEY")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([livekit_api_key, livekit_api_secret]): # L'hôte n'est pas strictement nécessaire pour la génération de token elle-même
        return {"error": "La clé API ou le secret API LiveKit ne sont pas configurés"}, 500

    # Utiliser l'importation directe de AccessToken, VideoGrants
    token_builder = AccessToken(livekit_api_key, livekit_api_secret) \
        .with_identity(identity) \
        .with_name(identity) \
        .with_grants(VideoGrants(
            room_join=True,
            room=room_name
        ))
    
    return {"token": token_builder.to_jwt()} # Retourner comme objet JSON

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)