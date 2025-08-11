import logging
import os

def get_dashboard_logger():
    """
    Configure et retourne un logger pour le tableau de bord Streamlit.
    Il journalise à la fois dans la console et dans un fichier nommé dashboard.log.
    """
    # S'assure que le chemin du fichier de log est correct
    log_file_path = os.path.join(os.path.dirname(__file__), 'dashboard.log')

    # Crée le logger
    logger = logging.getLogger("dashboard_logger")

    # Empêche l'ajout de gestionnaires plusieurs fois dans le modèle d'exécution de Streamlit
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Gestionnaire de Fichier
        fh = logging.FileHandler(log_file_path, encoding='utf-8')
        fh.setLevel(logging.INFO)

        # Gestionnaire de Console
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # Formatteur
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        # Ajoute les gestionnaires
        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger

# Exemple d'utilisation :
# from dashboard_logger import get_dashboard_logger
# logger = get_dashboard_logger()
# logger.info("Ceci est un message d'information.")
# logger.error("Ceci est un message d'erreur.", exc_info=True)
