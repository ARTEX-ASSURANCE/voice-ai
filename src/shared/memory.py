import redis
import json
from typing import Any, Optional

# The Adherent and ExtranetDatabaseDriver classes will be imported once
# the project structure is more stable and imports can be resolved.
# For now, we use comments and avoid strict type hinting for them.
# from ..data_access.driver import Adherent, ExtranetDatabaseDriver

class MemoryManager:
    """
    Manages different tiers of memory for a specific agent session.
    - Session Memory: Redis-backed, for data that persists across a single call.
    - Turn Memory: In-memory dict, for data relevant to a single conversational turn.
    - Long-Term Memory: DB-backed, for historical user data (placeholder).
    """
    def __init__(self, session_id: str, redis_client: redis.Redis, db_driver: Any = None):
        if not session_id:
            raise ValueError("session_id cannot be empty")
        self.session_id = session_id
        self.redis_client = redis_client
        self.db_driver = db_driver
        self.session_key = f"session:{self.session_id}"
        self._turn_memory = {}
        print(f"MemoryManager initialized for session {session_id}.")

    # --- Session Memory (Redis-backed) ---

    def set_session_data(self, key: str, value: Any):
        """Stores a key-value pair in the session memory, serializing to JSON."""
        try:
            serialized_value = json.dumps(value)
            self.redis_client.hset(self.session_key, key, serialized_value)
        except TypeError as e:
            print(f"Error serializing value for key '{key}': {e}")


    def get_session_data(self, key: str) -> Any:
        """Retrieves and deserializes a value from session memory."""
        value = self.redis_client.hget(self.session_key, key)
        if value:
            return json.loads(value)
        return None

    def get_all_session_data(self) -> dict:
        """Retrieves all data for the current session."""
        all_data = self.redis_client.hgetall(self.session_key)
        return {k.decode(): json.loads(v) for k, v in all_data.items()}

    def set_adherent_context(self, adherent: Any): # Type hint will be Adherent
        """A specific helper to store the adherent context."""
        from dataclasses import asdict, is_dataclass
        if is_dataclass(adherent):
            self.set_session_data("adherent_context", asdict(adherent))
        else:
            # Handle cases where it might be a dict already
            self.set_session_data("adherent_context", adherent)


    def get_adherent_context(self) -> Optional[dict]: # -> Optional[Adherent]
        """
        A specific helper to retrieve the adherent context as a dictionary.
        The caller is responsible for converting it back to a dataclass.
        """
        return self.get_session_data("adherent_context")

    # --- Turn Memory (In-memory) ---

    def set_turn_data(self, key: str, value: Any):
        """Stores data for the current turn."""
        self._turn_memory[key] = value

    def get_turn_data(self, key: str) -> Any:
        """Retrieves data from the current turn."""
        return self._turn_memory.get(key)

    def clear_turn_data(self):
        """Clears the turn memory. Should be called after each conversational turn."""
        self._turn_memory = {}

    # --- Long-Term Memory (DB-backed) ---

    def get_user_history(self, user_id: str, limit: int = 5) -> str:
        """
        Retrieves a summary of the user's past interactions.
        This is a placeholder for a more complex implementation.
        """
        if not self.db_driver:
            return "Database driver not configured. Cannot retrieve long-term memory."

        # Placeholder logic: In a real implementation, this would query 'journal_appels'
        # and other tables based on a user identifier (e.g., phone number, adherent_id).
        print(f"Fetching history for user {user_id} (limit {limit})...")
        return f"User {user_id} has no significant history on record."
