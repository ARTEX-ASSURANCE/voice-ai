# dashboard/core/db_connector.py
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from dashboard_logger import get_dashboard_logger

# Initialise le logger
logger = get_dashboard_logger()

# Utilise st.cache_resource pour ne créer le moteur qu'une seule fois
@st.cache_resource
def init_db_engine():
    """
    Initialise un moteur SQLAlchemy pour la connexion à la base de données.
    """
    try:
        db_secrets = st.secrets['mysql']
        db_url = (
            f"mysql+mysqlconnector://{db_secrets['user']}:{db_secrets['password']}"
            f"@{db_secrets['host']}/{db_secrets['database']}"
        )
        engine = create_engine(db_url)
        connection = engine.connect()
        connection.close()
        logger.info("Moteur de base de données créé avec succès.")
        return engine
    except SQLAlchemyError as e:
        logger.error(f"Erreur de connexion SQLAlchemy : {e}", exc_info=True)
        st.error(f"Erreur de connexion à la base de données avec SQLAlchemy : {e}")
        return None
    except (KeyError, FileNotFoundError) as e:
        logger.error(f"Les secrets de la BD ne sont pas configurés pour Streamlit : {e}", exc_info=True)
        st.error("Les secrets de la base de données ne sont pas correctement configurés.")
        return None
    except Exception as e:
        logger.error(f"Erreur inattendue lors de la création du moteur de BD : {e}", exc_info=True)
        st.error(f"Une erreur inattendue est survenue lors de la création du moteur : {e}")
        return None

# Utilise st.cache_data pour mettre en cache les résultats des requêtes
@st.cache_data(ttl=600)
def run_query(query: str) -> pd.DataFrame:
    """
    Exécute une requête SQL en utilisant le moteur SQLAlchemy et retourne les résultats
    dans un DataFrame Pandas. Les résultats sont mis en cache.
    """
    engine = init_db_engine()
    if engine:
        try:
            logger.info(f"Exécution de la requête : {query[:100]}...")
            df = pd.read_sql(query, engine)
            return df
        except SQLAlchemyError as e:
            logger.error(f"Échec de l'exécution de la requête : {query}", exc_info=True)
            st.error(f"Erreur lors de l'exécution de la requête : {e}")
            return pd.DataFrame()
    else:
        logger.warning("Moteur de BD non disponible, exécution de la requête annulée.")
        return pd.DataFrame()