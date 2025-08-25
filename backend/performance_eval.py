# ai/backend/performance_eval.py (Version Finale avec Gestion des Quotas)

import logging
import os
import json
import time # Import du module time pour la pause
from dotenv import load_dotenv
from db_driver import ExtranetDatabaseDriver
from error_logger import log_system_error, set_db_connection_params
from prompts import PERFORMANCE_EVALUATION_PROMPT
from langchain_google_genai import ChatGoogleGenerativeAI

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def evaluate_and_summarize_call(id_appel: int, db: ExtranetDatabaseDriver, llm: ChatGoogleGenerativeAI):
    """
    Génère un résumé et une évaluation via un LLM, puis met à jour la base de données.
    """
    logger.info(f"Début de l'évaluation et du résumé pour l'appel ID: {id_appel}")
    
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT transcription_complete FROM journal_appels WHERE id_appel = %s", (id_appel,))
            call_data = cursor.fetchone()

            if not call_data or not call_data['transcription_complete'] or call_data['transcription_complete'] in ('[]', 'Transcription non disponible.'):
                logger.warning(f"Pas de transcription valide pour l'appel {id_appel}. Annulation.")
                return

            transcription = call_data['transcription_complete']
            
            prompt = PERFORMANCE_EVALUATION_PROMPT.format(transcription=transcription)
            response = llm.invoke(prompt)
            
            # --- Amélioration du parsing JSON ---
            try:
                # Gère le cas où le LLM retourne le JSON dans un bloc de code
                response_content_raw = response.content
                response_content = response_content_raw.strip() if isinstance(response_content_raw, str) else json.dumps(response_content_raw)
                if response_content.startswith("```json"):
                    response_content = response_content[7:-3].strip()
                
                eval_data = json.loads(response_content)
                resume = eval_data.get("resume_evaluation", "Résumé non fourni par l'IA.")
                conformite = str(eval_data.get("conformite", "Évaluation de conformité non fournie."))
                resolution = str(eval_data.get("points_amelioration", "Points d'amélioration non fournis."))
            except (json.JSONDecodeError, AttributeError, KeyError) as e:
                logger.error(f"Impossible de parser la réponse du LLM pour l'appel {id_appel}. Erreur: {e}. Réponse brute: {response.content}")
                resume, conformite, resolution = "Erreur de parsing.", "Erreur de parsing.", "Erreur de parsing."
            
            success = db.enregistrer_evaluation_appel(id_appel, resume, conformite, resolution)
            if success:
                logger.info(f"Évaluation et résumé enregistrés pour l'appel {id_appel}.")
            else:
                logger.error(f"Échec de l'enregistrement de l'évaluation pour l'appel {id_appel}.")

    except Exception as e:
        logger.error(f"Erreur inattendue lors de l'évaluation de l'appel {id_appel}: {e}", exc_info=True)
        log_system_error("performance_eval.evaluate_and_summarize_call", f"Unexpected Error: {e}", e, id_appel_fk=id_appel)


if __name__ == '__main__':
    load_dotenv()

    try:
        db_params = {
            'host': os.getenv("DB_HOST"), 'user': os.getenv("DB_USER"),
            'password': os.getenv("DB_PASSWORD"), 'database': os.getenv("DB_NAME")
        }
        if not all(db_params.values()):
            raise ValueError("Variables d'environnement de la base de données manquantes.")
        set_db_connection_params(db_params)
    except Exception as e:
        logger.critical(f"Impossible de configurer la connexion à la BDD. Arrêt. Erreur: {e}")
        exit(1)

    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0.2)
    except Exception as e:
        logger.critical(f"Impossible d'initialiser le modèle LLM. Vérifiez votre clé d'API Google. Erreur: {e}")
        exit(1)

    db_driver = ExtranetDatabaseDriver()

    try:
        with db_driver._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            query = """
                SELECT id_appel FROM journal_appels 
                WHERE (resume_appel IS NULL OR resume_appel LIKE '%Erreur%' OR resume_appel LIKE '%Non généré%')
                  AND (transcription_complete IS NOT NULL AND transcription_complete != '[]')
            """
            cursor.execute(query)
            appels_a_evaluer = cursor.fetchall()
            
            if not appels_a_evaluer:
                logger.info("Aucun nouvel appel à évaluer.")
            else:
                logger.info(f"Trouvé {len(appels_a_evaluer)} appel(s) à traiter.")
                for appel in appels_a_evaluer:
                    evaluate_and_summarize_call(appel['id_appel'], db_driver, llm)
                    
                    # --- AJOUT DE LA PAUSE ICI ---
                    logger.info("Pause de 1 secondes pour respecter les quotas de l'API...")
                    time.sleep(1)
                    # --- FIN DE L'AJOUT ---
        
        logger.info("Processus d'évaluation terminé.")
    except Exception as e:
        logger.error(f"Le processus principal d'évaluation a échoué: {e}", exc_info=True)