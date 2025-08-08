# api.py (Corrected and Finalized)

import logging
from livekit.agents import Agent
from livekit.plugins import google, silero, deepgram
from db_driver import ExtranetDatabaseDriver
from prompts import INSTRUCTIONS
from langchain_google_genai import ChatGoogleGenerativeAI

# --- Importation des outils (Liste finale et corrigée) ---
from tools import (
    # Outils d'Identité & Contexte
    lookup_adherent_by_email,
    lookup_adherent_by_telephone,
    lookup_adherent_by_fullname,
    confirm_identity,
    get_adherent_details,
    clear_context,
    update_contact_information,
    list_available_products,
    get_product_guarantees,
    # Outils de Contrat & Sinistre (Base Transactionnelle)
    list_adherent_contracts,
    create_claim,
    # Outils d'Action & Communication
    request_quote,
    log_issue,
    send_confirmation_email, # Corrigé depuis send_confirmation_by_email
    schedule_callback_with_advisor,
    schedule_callback,
    expliquer_garantie_specifique,
    envoyer_document_adherent,
    qualifier_prospect_pour_conseiller,
    enregistrer_feedback_appel
)


class ArtexAgent(Agent):
    def __init__(self, db_driver: ExtranetDatabaseDriver):
        super().__init__(
            instructions=INSTRUCTIONS,
            llm=google.LLM(model="gemini-2.0-flash-lite", temperature=0.3),
            tts=google.TTS(language="fr-FR", voice_name="fr-FR-Chirp3-HD-Zephyr"),
            stt=deepgram.STT(model="nova-2", language="fr", endpointing_ms=300),
            vad=silero.VAD.load(min_silence_duration=0.3),
            # --- LISTE D'OUTILS CORRIGÉE ET SIMPLIFIÉE ---
            tools=[
                # Identité & Contexte
                lookup_adherent_by_email,
                lookup_adherent_by_telephone,
                lookup_adherent_by_fullname,
                confirm_identity,
                get_adherent_details,
                clear_context,
                list_available_products,
                get_product_guarantees,               
                # Libre-Service
                update_contact_information,               
                # Contrats & Sinistres (Transactionnel)
                list_adherent_contracts,
                create_claim,
                # Actions & Communication
                request_quote,
                log_issue,
                send_confirmation_email,
                schedule_callback_with_advisor,
                schedule_callback,
                expliquer_garantie_specifique,
                envoyer_document_adherent,
                qualifier_prospect_pour_conseiller,
                enregistrer_feedback_appel
            ],
        )
        self.db_driver = db_driver
        self.task_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite", temperature=0.3)
        logging.info("Schéma ArtexAgent configuré avec des LLMs séparés pour la conversation et les tâches.")

    def get_initial_userdata(self) -> dict:
        return {
            "db_driver": self.db_driver,
            "agent": self,
            "task_llm": self.task_llm, 
            "adherent_context": None,
            "unconfirmed_adherent": None,
        }

    async def summarize_text(self, text: str) -> str:
        # Cette méthode peut être supprimée si elle n'est plus utilisée,
        # ou conservée si un autre processus l'appelle.
        return "La fonction de résumé a été déplacée vers un outil dédié."