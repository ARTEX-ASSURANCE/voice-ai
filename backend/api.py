# api.py (Refactored for new schema)

import logging
from livekit.agents import Agent
from livekit.plugins import google, silero, deepgram
from db_driver import ExtranetDatabaseDriver
from prompts import INSTRUCTIONS
from langchain_google_genai import ChatGoogleGenerativeAI

# --- Import refactored tools ---
from tools import (
    # Identity & Context
    lookup_client_by_email,
    lookup_client_by_phone,
    lookup_client_by_fullname,
    confirm_identity,
    get_client_details,
    clear_context,
    update_contact_information,
    # Contracts
    list_client_contracts,
    # Communication & Scheduling
    send_confirmation_email,
    schedule_callback,
)

class ArtexAgent(Agent):
    def __init__(self, db_driver: ExtranetDatabaseDriver):
        super().__init__(
            instructions=INSTRUCTIONS,
            llm=google.LLM(model="gemini-2.0-flash-lite", temperature=0.3),
            tts=google.TTS(language="fr-FR", voice_name="fr-FR-Chirp3-HD-Zephyr"),
            stt=deepgram.STT(model="nova-2", language="fr", endpointing_ms=300),
            vad=silero.VAD.load(min_silence_duration=0.3),
            # --- Updated tool list ---
            tools=[
                lookup_client_by_email,
                lookup_client_by_phone,
                lookup_client_by_fullname,
                confirm_identity,
                get_client_details,
                clear_context,
                update_contact_information,
                list_client_contracts,
                send_confirmation_email,
                schedule_callback,
            ],
        )
        self.db_driver = db_driver
        self.task_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite", temperature=0.3)
        logging.info("ArtexAgent configured with new schema tools.")

    def get_initial_userdata(self) -> dict:
        return {
            "db_driver": self.db_driver,
            "agent": self,
            "task_llm": self.task_llm,
            "client_context": None,
            "unconfirmed_client": None,
        }

    async def summarize_text(self, text: str) -> str:
        # This method can be removed if it's not used elsewhere.
        return "The summary function has been moved to a dedicated tool."
