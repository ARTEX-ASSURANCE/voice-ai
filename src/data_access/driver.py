# db_driver.py

import mysql.connector
import os
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, fields
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
import logging
import json

# Configurer le logging
logger = logging.getLogger(__name__)

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# --- Dataclasses correspondant à votre schéma de base de données ---

@dataclass
class Adherent:
    id_adherent: int
    nom: str
    prenom: str
    date_adhesion_mutuelle: date
    date_naissance: Optional[date] = None
    adresse: Optional[str] = None
    code_postal: Optional[str] = None
    ville: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    numero_securite_sociale: Optional[str] = None

@dataclass
class Formule:
    id_formule: int
    nom_formule: str
    tarif_base_mensuel: Decimal
    description_formule: Optional[str] = None

@dataclass
class Contrat:
    id_contrat: int
    id_adherent_principal: int
    numero_contrat: str
    date_debut_contrat: date
    id_formule: int
    date_fin_contrat: Optional[date] = None
    type_contrat: Optional[str] = None
    statut_contrat: str = 'Actif' # Par défaut à 'Actif'

@dataclass
class Garantie:
    id_garantie: int
    libelle: str
    description: Optional[str] = None

@dataclass
class FormuleGarantie:
    id_formule: int
    id_garantie: int
    plafond_remboursement: Optional[Decimal] = None
    taux_remboursement_pourcentage: Optional[Decimal] = None
    franchise: Optional[Decimal] = Decimal('0.00') # Par défaut à 0.00
    conditions_specifiques: Optional[str] = None

@dataclass
class SinistreArtex:
    id_sinistre_artex: int
    id_contrat: int
    id_adherent: int
    type_sinistre: str
    date_declaration_agent: date
    statut_sinistre_artex: str
    description_sinistre: Optional[str] = None
    date_survenance: Optional[date] = None


# --- Pilote de base de données pour toutes les tables 'extranet' ---

class ExtranetDatabaseDriver:
    """
    Gère toutes les connexions et opérations de base de données pour le système extranet.
    Cette classe agit comme une couche d'accès aux données centralisée, encapsulant toutes les requêtes SQL.
    """
    def __init__(self):
        """
        Initialise le pilote en chargeant les identifiants depuis les variables d'environnement.
        """
        db_host = os.getenv("DB_HOST")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_name = os.getenv("DB_NAME")

        if not all([db_host, db_user, db_password, db_name]):
            raise ValueError("Une ou plusieurs variables d'environnement de base de données ne sont pas définies.")

        self.connection_params = {
            'host': db_host,
            'user': db_user,
            'password': db_password,
            'database': db_name
        }
        logger.info("Pilote de base de données initialisé avec les paramètres de connexion.")

    @contextmanager
    def _get_connection(self):
        """Fournit une connexion gérée à la base de données MySQL."""
        conn = None
        try:
            conn = mysql.connector.connect(**self.connection_params)
            yield conn
        except mysql.connector.Error as err:
            logger.error(f"Erreur de connexion à la base de données : {err}")
            raise # Relancer l'exception après l'avoir journalisée
        finally:
            if conn and conn.is_connected():
                conn.close()

    def _map_row(self, row: tuple, cursor, dataclass_type):
        """Utilitaire pour mapper une seule ligne de base de données à une instance de dataclass."""
        if not row:
            return None
        
        column_names = [desc[0] for desc in cursor.description]
        row_dict = dict(zip(column_names, row))
        
        # Filtrer le dictionnaire pour n'inclure que les clés qui sont des champs dans la dataclass
        dataclass_fields = {f.name for f in fields(dataclass_type)}
        filtered_dict = {k: v for k, v in row_dict.items() if k in dataclass_fields}
        
        return dataclass_type(**filtered_dict)

    def _map_rows(self, rows: List[tuple], cursor, dataclass_type):
        """Utilitaire pour mapper plusieurs lignes de base de données à une liste d'instances de dataclass."""
        if not rows:
            return []
        return [self._map_row(row, cursor, dataclass_type) for row in rows]

    # --- Méthodes Adherent ---

    def get_adherent_by_id(self, adherent_id: int) -> Optional[Adherent]:
        """Récupère un seul adhérent par son ID unique."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM adherents WHERE id_adherent = %s", (adherent_id,))
            return self._map_row(cursor.fetchone(), cursor, Adherent)

    def get_adherent_by_email(self, email: str) -> Optional[Adherent]:
        """Récupère un seul adhérent par son adresse e-mail."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM adherents WHERE email = %s", (email,))
            return self._map_row(cursor.fetchone(), cursor, Adherent)

    def get_adherents_by_telephone(self, telephone: str) -> List[Adherent]:
        """Récupère une liste d'adhérents par leur numéro de téléphone."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM adherents WHERE telephone LIKE %s", (f"%{telephone}",))
            return self._map_rows(cursor.fetchall(), cursor, Adherent)

    def get_adherents_by_fullname(self, nom: str, prenom: str) -> List[Adherent]:
        """Récupère une liste d'adhérents par leur nom complet."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM adherents WHERE nom = %s AND prenom = %s", (nom, prenom))
            return self._map_rows(cursor.fetchall(), cursor, Adherent)

    def update_adherent_contact_info(self, adherent_id: int, address: Optional[str] = None, 
                                     code_postal: Optional[str] = None, ville: Optional[str] = None, 
                                     telephone: Optional[str] = None, email: Optional[str] = None) -> bool:
        """Met à jour les informations de contact pour un adhérent donné."""
        fields_to_update = {
            "adresse": address, "code_postal": code_postal, "ville": ville,
            "telephone": telephone, "email": email
        }
        updates = {k: v for k, v in fields_to_update.items() if v is not None}
        
        if not updates: return False

        set_clause = ", ".join([f"{key} = %s" for key in updates.keys()])
        query = f"UPDATE adherents SET {set_clause} WHERE id_adherent = %s"
        values = list(updates.values()) + [adherent_id]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(query, tuple(values))
                conn.commit()
                return cursor.rowcount > 0
            except mysql.connector.Error as err:
                logger.error(f"Échec de la mise à jour des informations de contact pour l'adhérent {adherent_id} : {err}")
                conn.rollback()
                return False

    # --- Méthodes Contrat & Formule ---

    def get_contrats_by_adherent_id(self, adherent_id: int) -> List[Contrat]:
        """Récupère tous les contrats pour un ID d'adhérent donné."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contrats WHERE id_adherent_principal = %s", (adherent_id,))
            return self._map_rows(cursor.fetchall(), cursor, Contrat)

    def get_contract_by_id(self, contract_id: int) -> Optional[Contrat]:
        """Récupère un seul contrat par son ID unique."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contrats WHERE id_contrat = %s", (contract_id,))
            return self._map_row(cursor.fetchone(), cursor, Contrat)

    def get_full_contract_details(self, contract_id: int) -> Optional[Dict[str, Any]]:
        """Récupère les détails combinés du contrat et de la formule pour un ID de contrat donné."""
        query = """
            SELECT c.*, f.nom_formule, f.tarif_base_mensuel, f.description_formule
            FROM contrats c JOIN formules f ON c.id_formule = f.id_formule
            WHERE c.id_contrat = %s
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, (contract_id,))
            return cursor.fetchone()

    # --- Méthodes Garantie (Couverture) ---

    def get_guarantees_for_formula(self, formula_id: int) -> List[Dict[str, Any]]:
        """Récupère toutes les garanties avec leurs termes pour une formule spécifique."""
        query = """
            SELECT g.libelle, g.description, fg.*
            FROM formules_garanties fg JOIN garanties g ON fg.id_garantie = g.id_garantie
            WHERE fg.id_formule = %s
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, (formula_id,))
            return cursor.fetchall()

    def get_specific_guarantee_detail(self, formula_id: int, guarantee_name: str) -> Optional[Dict[str, Any]]:
        """Récupère les détails d'une garantie spécifique unique au sein d'une formule."""
        query = """
            SELECT g.libelle, g.description, fg.*
            FROM formules_garanties fg JOIN garanties g ON fg.id_garantie = g.id_garantie
            WHERE fg.id_formule = %s AND g.libelle LIKE %s
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, (formula_id, f"%{guarantee_name}%"))
            return cursor.fetchone()

    # --- Méthodes Sinistre ---

    def get_sinistres_by_adherent_id(self, adherent_id: int) -> List[SinistreArtex]:
        """Récupère tous les sinistres déclarés par un adhérent spécifique."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sinistres_artex WHERE id_adherent = %s", (adherent_id,))
            return self._map_rows(cursor.fetchall(), cursor, SinistreArtex)

    def get_sinistre_by_id(self, sinistre_id: int) -> Optional[SinistreArtex]:
        """Récupère un seul sinistre par son ID unique."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sinistres_artex WHERE id_sinistre_artex = %s", (sinistre_id,))
            return self._map_row(cursor.fetchone(), cursor, SinistreArtex)

    def create_sinistre(self, id_contrat: int, id_adherent: int, type_sinistre: str,
                        description_sinistre: str, date_survenance: date) -> Optional[SinistreArtex]:
        """Crée un nouveau sinistre dans la base de données après validation de la propriété."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT id_adherent_principal FROM contrats WHERE id_contrat = %s", (id_contrat,))
                result = cursor.fetchone()
                if not result or result[0] != id_adherent:
                    logger.warning(f"Tentative de création de sinistre pour le contrat {id_contrat} par l'adhérent non principal {id_adherent}.")
                    return None

                query = """
                    INSERT INTO sinistres_artex (id_contrat, id_adherent, type_sinistre, date_declaration_agent, 
                                                 statut_sinistre_artex, description_sinistre, date_survenance)
                    VALUES (%s, %s, %s, CURDATE(), %s, %s, %s)
                """
                initial_status = "Soumis" # Statut initial
                values = (id_contrat, id_adherent, type_sinistre,
                          initial_status, description_sinistre, date_survenance)
                
                cursor.execute(query, values)
                new_id = cursor.lastrowid
                conn.commit()
                logger.info(f"Sinistre créé avec succès avec l'ID : {new_id}")
                return self.get_sinistre_by_id(new_id)

            except mysql.connector.Error as err:
                logger.error(f"Erreur de base de données lors de la création du sinistre : {err}")
                conn.rollback()
                return None

    def update_sinistre_status(self, sinistre_id: int, new_status: str, notes: Optional[str] = None) -> bool:
        """Met à jour le statut d'un sinistre et ajoute éventuellement des notes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                if notes:
                    query = """
                        UPDATE sinistres_artex 
                        SET statut_sinistre_artex = %s, 
                            description_sinistre = CONCAT(IFNULL(description_sinistre, ''), '\n--- NOTE ---', %s)
                        WHERE id_sinistre_artex = %s
                    """
                    cursor.execute(query, (new_status, notes, sinistre_id))
                else:
                    query = "UPDATE sinistres_artex SET statut_sinistre_artex = %s WHERE id_sinistre_artex = %s"
                    cursor.execute(query, (new_status, sinistre_id))
                
                conn.commit()
                return cursor.rowcount > 0
            except mysql.connector.Error as err:
                logger.error(f"Échec de la mise à jour du statut pour le sinistre {sinistre_id} : {err}")
                conn.rollback()
                return False

    # --- Journalisation des Appels pour Tableau de Bord ---

    def enregistrer_debut_appel(self, id_livekit_room: str, numero_appelant: Optional[str]) -> Optional[int]:
        """
        Enregistre le début d'un appel dans la table journal_appels.
        Retourne l'ID de l'appel enregistré (id_appel) ou None en cas d'échec.
        """
        query = """
            INSERT INTO journal_appels (id_livekit_room, timestamp_debut, numero_appelant)
            VALUES (%s, NOW(), %s)
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (id_livekit_room, numero_appelant))
                conn.commit()
                return cursor.lastrowid # Retourne l'ID de la nouvelle ligne insérée
        except mysql.connector.Error as err:
            logger.error(f"Erreur lors de l'enregistrement du début d'appel pour {id_livekit_room}: {err}")
            # Note: The specific error logging is removed, higher level should handle it.
            return None

    def enregistrer_fin_appel(self, id_appel: int, resume_appel: Optional[str] = None, 
                              transcription: Optional[str] = None, statut: str = 'Terminé',
                              chemin_enregistrement_audio: Optional[str] = None) -> bool:
        """
        Met à jour l'enregistrement d'un appel avec toutes les données finales.
        """
        query = """
            UPDATE journal_appels
            SET 
                timestamp_fin = NOW(),
                resume_appel = %s,
                transcription_complete = %s,
                statut_appel = %s,
                duree_appel_secondes = TIMESTAMPDIFF(SECOND, timestamp_debut, NOW()),
                chemin_enregistrement_audio = %s
            WHERE id_appel = %s AND timestamp_fin IS NULL
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (resume_appel, transcription, statut, chemin_enregistrement_audio, id_appel))
                conn.commit()
                return cursor.rowcount > 0
        except mysql.connector.Error as err:
            logger.error(f"Erreur lors de l'enregistrement de la fin d'appel pour l'ID {id_appel}: {err}")
            return False
        
    def enregistrer_contexte_adherent_appel(self, id_appel: int, id_adherent: int) -> bool:
        """
        Met à jour l'enregistrement d'un appel avec l'ID de l'adhérent identifié.
        """
        query = "UPDATE journal_appels SET id_adherent_contexte = %s WHERE id_appel = %s"
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (id_adherent, id_appel))
                conn.commit()
                return cursor.rowcount > 0
        except mysql.connector.Error as err:
            logger.error(f"Erreur lors de l'enregistrement du contexte adhérent pour l'appel ID {id_appel}: {err}")
            return False

    def enregistrer_action_agent(self, id_appel_fk: int, type_action: str,
                                 nom_outil: Optional[str] = None, parametres_outil: Optional[dict] = None,
                                 resultat_outil: Optional[str] = None, message_dit: Optional[str] = None,
                                 detail_evenement: Optional[str] = None) -> Optional[int]:
        """
        Enregistre une action de l'agent dans la table actions_agent.
        Retourne l'ID de l'action enregistrée ou None en cas d'échec.
        """
        query = """
            INSERT INTO actions_agent
            (id_appel_fk, timestamp_action, type_action, nom_outil, parametres_outil, resultat_outil, message_dit, detail_evenement)
            VALUES (%s, NOW(), %s, %s, %s, %s, %s, %s)
        """
        parametres_outil_json = json.dumps(parametres_outil) if isinstance(parametres_outil, dict) else parametres_outil

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (id_appel_fk, type_action, nom_outil, parametres_outil_json,
                                       resultat_outil, message_dit, detail_evenement))
                conn.commit()
                return cursor.lastrowid
        except (mysql.connector.Error, TypeError) as err:
            logger.error(f"Erreur lors de l'enregistrement de l'action agent pour l'appel ID {id_appel_fk}: {err} - Action: {type_action}")
            # Fallback for non-serializable params
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(query, (id_appel_fk, type_action, nom_outil, str(parametres_outil),
                                           resultat_outil, message_dit, detail_evenement))
                    conn.commit()
                    return cursor.lastrowid
            except Exception as e_fallback:
                logger.error(f"Échec de la tentative de journalisation de secours pour l'action agent: {e_fallback}")
            return None

    # --- Journalisation des Interactions BD ---
    # The _log_db_interaction method is removed to decouple the data layer.
    # Logging of DB interactions should be handled by the service that calls the data layer.
    
    # --- MÉTHODE CORRIGÉE POUR LA BASE DE CONNAISSANCES ---
    
    def query_knowledge_base(self, product_keyword: str, exact_match: bool = False) -> List[Dict[str, Any]]:
        """
        Interroge la base de connaissances.
        - Si exact_match est False, recherche les produits par mot-clé (catégorie ou nom).
        - Si exact_match est True, recherche un produit par son nom exact pour obtenir ses garanties.
        """
        if exact_match:
            where_clause = "p.nom_produit = %s"
            params = (product_keyword,)
        else:
            where_clause = "p.nom_produit LIKE %s OR p.categorie LIKE %s"
            search_term = f"%{product_keyword}%"
            params = (search_term, search_term)
        
        query = f"""
            SELECT 
                p.nom_produit,
                p.categorie,
                p.description_complete,
                g.nom_garantie,
                pg.description_specifique
            FROM 
                kb_produits p
            LEFT JOIN 
                kb_produit_garanties pg ON p.id = pg.id_produit
            LEFT JOIN 
                kb_garanties g ON pg.id_garantie = g.id
            WHERE 
                {where_clause};
        """
        
        with self._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params)
            return cursor.fetchall()

    # --- NOUVELLES MÉTHODES AJOUTÉES ---

    def get_document_by_product_id(self, product_id: int, doc_type: str = 'Notice d\'Information') -> Optional[Dict[str, Any]]:
        """
        Récupère un document spécifique pour un produit donné (par ex: Notice d'Information).
        """
        query = "SELECT nom_fichier, chemin_fichier FROM kb_documents WHERE id_produit = %s AND type_document LIKE %s LIMIT 1"

        with self._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, (product_id, f"%{doc_type}%"))
            return cursor.fetchone()

    def enregistrer_feedback(self, id_appel_fk: int, note: Optional[int], commentaire: Optional[str]) -> bool:
        """
        Enregistre le feedback d'un utilisateur dans la nouvelle table feedback_appel.
        """
        query = """
            INSERT INTO feedback_appel (id_appel_fk, note_satisfaction, commentaire)
            VALUES (%s, %s, %s)
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (id_appel_fk, note, commentaire))
                conn.commit()
                return cursor.lastrowid is not None
        except mysql.connector.Error as err:
            logger.error(f"Erreur lors de l'enregistrement du feedback pour l'appel ID {id_appel_fk}: {err}")
            return False
        
    def enregistrer_evaluation_appel(self, id_appel: int, resume: str, conformite: str, resolution: str) -> bool:
        """
        Enregistre le résumé et l'évaluation de la performance générés par l'IA post-appel.
        """
        query = """
            UPDATE journal_appels
            SET 
                resume_appel = %s,
                evaluation_conformite = %s,
                evaluation_resolution_appel = %s
            WHERE id_appel = %s
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (resume, conformite, resolution, id_appel))
                conn.commit()
                logger.info(f"Évaluation enregistrée avec succès pour l'appel ID {id_appel}.")
                return cursor.rowcount > 0
        except mysql.connector.Error as err:
            logger.error(f"Erreur lors de l'enregistrement de l'évaluation pour l'appel ID {id_appel}: {err}")
            return False