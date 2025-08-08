# dashboard/core/db_connector.py
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

# Utilise st.cache_resource pour ne créer l'engine qu'une seule fois
@st.cache_resource
def init_db_engine():
    """
    Initialise un "engine" SQLAlchemy pour la connexion à la base de données.
    L'engine est mis en cache pour éviter de le recréer à chaque interaction.
    SQLAlchemy est la méthode recommandée par Pandas pour les connexions BDD.
    """
    try:
        # Construit l'URL de connexion pour SQLAlchemy
        db_url = (
            f"mysql+mysqlconnector://{st.secrets['mysql']['user']}:{st.secrets['mysql']['password']}"
            f"@{st.secrets['mysql']['host']}/{st.secrets['mysql']['database']}"
        )
        engine = create_engine(db_url)

        # Teste la connexion pour s'assurer que l'engine est valide
        # La méthode connect() lève une erreur si les identifiants sont mauvais.
        connection = engine.connect()
        connection.close()
        
        return engine
        
    except SQLAlchemyError as e:
        st.error(f"Erreur de connexion à la base de données avec SQLAlchemy : {e}")
        return None
    except Exception as e:
        # Attrape d'autres erreurs potentielles (ex: secret manquant)
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
            df = pd.read_sql(query, engine)
            return df
        except SQLAlchemyError as e:
            st.error(f"Erreur lors de l'exécution de la requête : {e}")
            return pd.DataFrame()
    return pd.DataFrame()