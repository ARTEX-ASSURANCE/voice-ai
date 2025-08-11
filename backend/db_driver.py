# db_driver.py (Réfractorié pour le nouveau schéma)

import mysql.connector
import os
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, fields
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
import logging
import json

# Configuration du logging
logger = logging.getLogger(__name__)

# Chargement des variables d'environnement
load_dotenv()

# --- NOUVEAUX Dataclasses pour le nouveau schéma ---

@dataclass
class Client:
    Id: int
    Phone: Optional[str] = None
    Mobile: Optional[str] = None
    Email: Optional[str] = None
    FirstName: Optional[str] = None
    LastName: Optional[str] = None
    Title: Optional[str] = None
    Address: Optional[str] = None
    City: Optional[str] = None
    Status: Optional[str] = None
    IsArchived: bool = False

@dataclass
class Contract:
    Id: int
    ClientId: int
    Reference: Optional[str] = None
    Status: Optional[str] = None
    Price: Optional[Decimal] = None
    Amount: Optional[Decimal] = None
    EffectiveDate: Optional[date] = None
    TerminationDate: Optional[date] = None
    CompanyId: Optional[int] = None
    FormulaId: Optional[int] = None

@dataclass
class ClientEventHistory:
    Id: int
    ClientId: int
    ForDate: Optional[datetime] = None
    Comment: Optional[str] = None
    IsCompleted: bool = False
    EventId: Optional[str] = None

# --- NOUVEAU Pilote de Base de Données ---

class ExtranetDatabaseDriver:
    def __init__(self):
        db_host = os.getenv("DB_HOST")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_name = os.getenv("DB_NAME")

        if not all([db_host, db_user, db_password, db_name]):
            raise ValueError("Une ou plusieurs variables d'environnement de la base de données ne sont pas définies.")

        self.connection_params = {
            'host': db_host,
            'user': db_user,
            'password': db_password,
            'database': db_name
        }
        logger.info("Pilote de base de données initialisé pour le nouveau schéma.")

    @contextmanager
    def _get_connection(self):
        conn = None
        try:
            conn = mysql.connector.connect(**self.connection_params)
            yield conn
        except mysql.connector.Error as err:
            logger.error(f"Erreur de connexion à la base de données : {err}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def _map_row(self, row: tuple, cursor, dataclass_type):
        if not row:
            return None
        column_names = [desc[0] for desc in cursor.description]
        row_dict = dict(zip(column_names, row))
        dataclass_fields = {f.name for f in fields(dataclass_type)}
        filtered_dict = {k: v for k, v in row_dict.items() if k in dataclass_fields}
        return dataclass_type(**filtered_dict)

    def _map_rows(self, rows: List[tuple], cursor, dataclass_type):
        if not rows:
            return []
        return [self._map_row(row, cursor, dataclass_type) for row in rows]

    # --- NOUVELLES Méthodes pour le nouveau schéma ---

    def get_client_by_id(self, client_id: int) -> Optional[Client]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Clients WHERE Id = %s", (client_id,))
            return self._map_row(cursor.fetchone(), cursor, Client)

    def get_client_by_email(self, email: str) -> Optional[Client]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Clients WHERE Email = %s", (email,))
            return self._map_row(cursor.fetchone(), cursor, Client)

    def get_clients_by_phone(self, phone: str) -> List[Client]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Clients WHERE Phone = %s OR Mobile = %s", (phone, phone))
            return self._map_rows(cursor.fetchall(), cursor, Client)

    def get_clients_by_fullname(self, last_name: str, first_name: str) -> List[Client]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Clients WHERE LastName = %s AND FirstName = %s", (last_name, first_name))
            return self._map_rows(cursor.fetchall(), cursor, Client)

    def update_client_contact_info(self, client_id: int, address: Optional[str] = None, city: Optional[str] = None, phone: Optional[str] = None, email: Optional[str] = None) -> bool:
        fields_to_update = {"Address": address, "City": city, "Phone": phone, "Email": email}
        updates = {k: v for k, v in fields_to_update.items() if v is not None}
        
        if not updates: return False

        set_clause = ", ".join([f"{key} = %s" for key in updates.keys()])
        query = f"UPDATE Clients SET {set_clause} WHERE Id = %s"
        values = list(updates.values()) + [client_id]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(query, tuple(values))
                conn.commit()
                return cursor.rowcount > 0
            except mysql.connector.Error as err:
                logger.error(f"Échec de la mise à jour des informations de contact pour le client {client_id}: {err}")
                conn.rollback()
                return False

    def get_contracts_by_client_id(self, client_id: int) -> List[Contract]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Contracts WHERE ClientId = %s", (client_id,))
            return self._map_rows(cursor.fetchall(), cursor, Contract)

    def create_client_event(self, client_id: int, event_id: str, comment: str, for_date: Optional[datetime] = None) -> Optional[ClientEventHistory]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                query = "INSERT INTO ClientEventsHistory (ClientId, EventId, Comment, ForDate, IsCompleted) VALUES (%s, %s, %s, %s, %s)"
                values = (client_id, event_id, comment, for_date or datetime.now(), False)
                cursor.execute(query, values)
                new_id = cursor.lastrowid
                conn.commit()
                return ClientEventHistory(Id=new_id, ClientId=client_id, EventId=event_id, Comment=comment, ForDate=for_date)
            except mysql.connector.Error as err:
                logger.error(f"Erreur de base de données lors de la création de l'événement client : {err}")
                conn.rollback()
                return None
                
    # Toutes les autres méthodes pour la journalisation, la base de connaissances, etc. sont supprimées pour le moment
    # car elles dépendent de l'ancien schéma et devraient également être réfractoriées.
    # Cette réfractoriation se concentre sur les tables principales.
