import os
from flask import Flask, request
from dotenv import load_dotenv
from flask_cors import CORS
from livekit.api import LiveKitAPI, AccessToken, VideoGrants, ListRoomsRequest
import uuid
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
if not all(db_params_for_logger[key] for key in ['host', 'user', 'password', 'database']):
    configure_logger() # Configure sans la BD
    log_activity("server.startup", "Variables d'environnement BD manquantes, journalisation BD désactivée.", level="WARNING")
else:
    configure_logger(db_params=db_params_for_logger)


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Enregistre le blueprint du tableau de bord
from dashboard_api import dashboard_bp
app.register_blueprint(dashboard_bp)

async def generate_room_name():
    """Génère un nom de salle unique."""
    name = "salle-" + str(uuid.uuid4())[:8]
    rooms = await get_rooms()
    while name in rooms:
        name = "salle-" + str(uuid.uuid4())[:8]
    return name

async def get_rooms():
    """Récupère la liste des salles actives depuis LiveKit."""
    livekit_host = os.getenv("LIVEKIT_URL")
    livekit_api_key = os.getenv("LIVEKIT_API_KEY")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([livekit_host, livekit_api_key, livekit_api_secret]):
        log_activity("server.get_rooms", "Les détails de connexion à LiveKit ne sont pas entièrement configurés.", level="WARNING")
        return [] # Retourne une liste vide car l'appel API échouera

    # Utilise l'importation directe de LiveKitAPI, ListRoomsRequest
    lk_api = LiveKitAPI(host=livekit_host, api_key=livekit_api_key, api_secret=livekit_api_secret)
    try:
        rooms_response = await lk_api.room.list_rooms(ListRoomsRequest())
    finally:
        await lk_api.aclose()
    
    return [room.name for room in rooms_response.rooms]

@app.route("/create-token", methods=['POST'])
async def get_token():
    """Crée un jeton d'accès LiveKit pour un client."""
    data = request.get_json()
    room_name = data.get("room_name")
    identity = data.get("identity", "identite-par-defaut") # Identité par défaut

    if not room_name:
        room_name = await generate_room_name() # Conserve la logique originale pour générer la salle si non fournie

    livekit_api_key = os.getenv("LIVEKIT_API_KEY")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([livekit_api_key, livekit_api_secret]): # L'hôte n'est pas strictement nécessaire pour la génération de jeton
        return {"error": "La clé API ou le secret API LiveKit ne sont pas configurés"}, 500

    # Utilise l'importation directe de AccessToken, VideoGrants
    token_builder = AccessToken(livekit_api_key, livekit_api_secret) \
        .with_identity(identity) \
        .with_name(identity) \
        .with_grants(VideoGrants(
            room_join=True,
            room=room_name
        ))
    
    return {"token": token_builder.to_jwt()} # Retourne comme objet JSON

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)