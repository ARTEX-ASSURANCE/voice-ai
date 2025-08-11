import logging
import os

def get_dashboard_logger():
    """
    Configures and returns a logger for the Streamlit dashboard.
    It logs to both the console and a file named dashboard.log.
    """
    # Ensure the log file path is correct
    log_file_path = os.path.join(os.path.dirname(__file__), 'dashboard.log')

    # Create logger
    logger = logging.getLogger("dashboard_logger")

    # Prevent adding handlers multiple times in Streamlit's execution model
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # File Handler
        fh = logging.FileHandler(log_file_path)
        fh.setLevel(logging.INFO)

        # Console Handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        # Add handlers
        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger

# Example of how to use it:
# from dashboard_logger import get_dashboard_logger
# logger = get_dashboard_logger()
# logger.info("This is an info message.")
# logger.error("This is an error message.", exc_info=True)
