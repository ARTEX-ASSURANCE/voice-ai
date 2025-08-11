# dashboard/core/db_connector.py
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from dashboard_logger import get_dashboard_logger

# Initialize logger
logger = get_dashboard_logger()

# Utilise st.cache_resource pour ne créer l'engine qu'une seule fois
@st.cache_resource
def init_db_engine():
    """
    Initialise un "engine" SQLAlchemy pour la connexion à la base de données.
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
        logger.info("Database engine created successfully.")
        return engine
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy connection error: {e}", exc_info=True)
        st.error(f"Erreur de connexion à la base de données avec SQLAlchemy : {e}")
        return None
    except (KeyError, FileNotFoundError) as e:
        logger.error(f"DB secrets not configured for Streamlit: {e}", exc_info=True)
        st.error("Les secrets de la base de données ne sont pas correctement configurés.")
        return None
    except Exception as e:
        logger.error(f"Unexpected error creating DB engine: {e}", exc_info=True)
        st.error(f"Une erreur inattendue est survenue lors de la création de l'engine : {e}")
        return None

# Utilise st.cache_data pour mettre en cache les résultats des requêtes
@st.cache_data(ttl=600)
def run_query(query: str) -> pd.DataFrame:
    """
    Exécute une requête SQL en utilisant l'engine SQLAlchemy et retourne les résultats 
    dans un DataFrame Pandas. Les résultats sont mis en cache.
    """
    engine = init_db_engine()
    if engine:
        try:
            logger.info(f"Executing query: {query[:100]}...")
            df = pd.read_sql(query, engine)
            return df
        except SQLAlchemyError as e:
            logger.error(f"Failed to execute query: {query}", exc_info=True)
            st.error(f"Erreur lors de l'exécution de la requête : {e}")
            return pd.DataFrame()
    else:
        logger.warning("DB engine not available, skipping query execution.")
        return pd.DataFrame()