import streamlit as st
import subprocess
import os
import time
import json
import pandas as pd
import sys

# --- Configuration de la page ---
st.set_page_config(
    page_title="Contrôle & Logs | Dashboard ARTEX",
    page_icon="⚙️",
    layout="wide"
)

st.title("⚙️ Contrôle & Logs du Système")

# --- Définition des Chemins (Corrigé) ---
# Ce script suppose une structure de projet comme:
# /ai-voice/  (PROJECT_ROOT)
#  ├── backend/
#  │   ├── server.py
#  │   └── agent.py
#  ├── dashboard/
#  │   └── pages/
#  │       └── control_page.py (ou un nom similaire pour ce fichier)
#  └── venv/

# Chemin du script actuel
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Remonter DEUX FOIS pour atteindre la racine du projet (ai-voice)
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
BACKEND_DIR = os.path.join(PROJECT_ROOT, 'backend')

# Déterminer le nom du dossier de l'environnement virtuel et le chemin de l'exécutable Python
VENV_FOLDER = 'venv'
if sys.platform == "win32":
    PYTHON_EXEC = os.path.join(PROJECT_ROOT, VENV_FOLDER, 'Scripts', 'python.exe')
else: # Linux, macOS, etc.
    PYTHON_EXEC = os.path.join(PROJECT_ROOT, VENV_FOLDER, 'bin', 'python')

# Fichiers cibles
SERVER_SCRIPT_PATH = os.path.join(BACKEND_DIR, 'server.py')
AGENT_SCRIPT_PATH = os.path.join(BACKEND_DIR, 'agent.py')
AGENT_LOG_FILE = os.path.join(BACKEND_DIR, 'agent.log')
SERVER_PID_FILE = os.path.join(BACKEND_DIR, 'server.pid')
AGENT_PID_FILE = os.path.join(BACKEND_DIR, 'agent.pid')


# --- Section de Diagnostic ---
with st.expander("🔍 Vérification de la Configuration & Diagnostics"):
    st.write(f"**Racine du Projet Détectée :** `{PROJECT_ROOT}`")
    st.write(f"**Dossier Backend Détecté :** `{BACKEND_DIR}`")
    
    diagnostics = {
        "Python Executable": (PYTHON_EXEC, os.path.exists(PYTHON_EXEC)),
        "Script Serveur (server.py)": (SERVER_SCRIPT_PATH, os.path.exists(SERVER_SCRIPT_PATH)),
        "Script Agent (agent.py)": (AGENT_SCRIPT_PATH, os.path.exists(AGENT_SCRIPT_PATH)),
        "Dossier Backend": (BACKEND_DIR, os.path.isdir(BACKEND_DIR))
    }
    
    for name, (path, exists) in diagnostics.items():
        status = "✅ Trouvé" if exists else "❌ NON TROUVÉ"
        st.text(f"{name.ljust(25)}: {status} -> {path}")

    st.info("Si un chemin est marqué '❌ NON TROUVÉ', veuillez vérifier votre structure de dossiers ou ajuster les chemins dans ce script.")
    st.info("Note : Le serveur Uvicorn est maintenant lancé via `python -m uvicorn`, ce qui ne nécessite pas de trouver `uvicorn.exe` directement.")


# --- Section de Contrôle des Processus ---
st.header("Contrôle des Processus")

def start_process(command_list, cwd, pid_file, process_name):
    """Démarre un processus et enregistre son PID."""
    if os.path.exists(pid_file):
        st.warning(f"Le processus '{process_name}' semble déjà en cours.")
        return

    # Vérifications avant démarrage
    executable = command_list[0]
    if not os.path.exists(executable):
        st.error(f"Erreur: L'exécutable Python est introuvable au chemin: {executable}")
        return
    if not os.path.isdir(cwd):
        st.error(f"Erreur: Le répertoire de travail pour '{process_name}' est introuvable: {cwd}")
        return

    try:
        # Utiliser Popen pour un contrôle non bloquant
        process = subprocess.Popen(command_list, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        time.sleep(2) # Laisser un peu de temps au processus pour démarrer ou échouer

        # Vérifier si le processus a échoué immédiatement
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            st.error(f"Le processus '{process_name}' a échoué au démarrage. Voici les détails :")
            st.subheader("Sortie Standard (stdout):")
            st.code(stdout, language="bash")
            st.subheader("Sortie d'Erreur (stderr):")
            st.code(stderr, language="bash")
        else:
            with open(pid_file, 'w') as f:
                f.write(str(process.pid))
            st.success(f"Processus '{process_name}' démarré (PID: {process.pid}).")
            st.rerun() 
    except Exception as e:
        st.error(f"Erreur lors du démarrage du processus '{process_name}': {e}")

def stop_process(pid_file, process_name):
    """Arrête un processus en utilisant son fichier PID."""
    if not os.path.exists(pid_file):
        st.info(f"Le processus '{process_name}' n'est pas en cours.")
        return
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        if os.name == 'nt':
            # Forcer l'arrêt du processus et de ses enfants sur Windows
            subprocess.run(f"taskkill /F /PID {pid} /T", shell=True, check=True, capture_output=True)
        else:
            # Forcer l'arrêt du processus sur Linux/macOS
            subprocess.run(f"kill -9 {pid}", shell=True, check=True, capture_output=True)
        
        os.remove(pid_file)
        st.success(f"Processus '{process_name}' (PID: {pid}) arrêté.")
        st.rerun()
    except (subprocess.CalledProcessError, FileNotFoundError):
         st.warning(f"Impossible d'arrêter le processus (PID: {pid}). Il est peut-être déjà terminé.")
         if os.path.exists(pid_file):
            os.remove(pid_file)
         st.rerun()
    except Exception as e:
        st.error(f"Une erreur est survenue lors de l'arrêt du processus '{process_name}': {e}")
        if os.path.exists(pid_file):
            os.remove(pid_file)

# --- Interface Utilisateur pour le Contrôle ---
c1, c2 = st.columns(2)
with c1:
    st.subheader("Serveur API")
    sc1, sc2 = st.columns(2)
    server_running = os.path.exists(SERVER_PID_FILE)
    # **MODIFICATION CLÉ ICI**
    waitress_command = [PYTHON_EXEC, "-m", "waitress", "--host", "0.0.0.0", "--port", "5001", "server:app"]

    sc1.button("🚀 Démarrer", on_click=start_process, args=(waitress_command, BACKEND_DIR, SERVER_PID_FILE, "Serveur API"), key="start_server", use_container_width=True, disabled=server_running)
    sc2.button("🛑 Arrêter", on_click=stop_process, args=(SERVER_PID_FILE, "Serveur API"), key="stop_server", use_container_width=True, disabled=not server_running)
    if server_running:
        st.success("Le serveur API est en cours d'exécution.")
    else:
        st.info("Le serveur API est arrêté.")

with c2:
    st.subheader("Agent Conversationnel")
    ac1, ac2 = st.columns(2)
    agent_running = os.path.exists(AGENT_PID_FILE)
    ac1.button("🤖 Démarrer", on_click=start_process, args=([PYTHON_EXEC, "agent.py", "start"], BACKEND_DIR, AGENT_PID_FILE, "Agent"), key="start_agent", use_container_width=True, disabled=agent_running)
    ac2.button("🛑 Arrêter", on_click=stop_process, args=(AGENT_PID_FILE, "Agent"), key="stop_agent", use_container_width=True, disabled=not agent_running)
    if agent_running:
        st.success("L'agent est en cours d'exécution.")
    else:
        st.info("L'agent est arrêté.")

st.markdown("---")

# --- Visualiseur de Logs Amélioré ---
st.header("Analyseur de Logs de l'Agent")

@st.cache_data(ttl=2)
def parse_logs():
    """Lit et parse les logs JSON depuis le fichier agent.log."""
    logs = []
    if not os.path.exists(AGENT_LOG_FILE):
        return pd.DataFrame()
    try:
        with open(AGENT_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue # Ignorer les lignes mal formées
        return pd.DataFrame(logs)
    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier de log : {e}")
        return pd.DataFrame()

logs_df = parse_logs()

if not logs_df.empty:
    # --- Filtres pour les logs ---
    filter_c1, filter_c2 = st.columns([1, 2])
    
    log_levels = sorted(logs_df['level'].unique())
    selected_levels = filter_c1.multiselect("Filtrer par niveau", options=log_levels, default=log_levels)
    search_term = filter_c2.text_input("Rechercher dans le message")

    # Appliquer les filtres
    filtered_logs = logs_df[logs_df['level'].isin(selected_levels)]
    if search_term:
        filtered_logs = filtered_logs[filtered_logs['message'].str.contains(search_term, case=False, na=False)]

    st.write(f"{len(filtered_logs)} logs trouvés sur {len(logs_df)} au total.")
    
    # --- Affichage des logs formatés ---
    log_container = st.container(height=500)
    
    for _, log in filtered_logs.iloc[::-1].iterrows():
        level = log.get('level', 'UNKNOWN')
        icon = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "CRITICAL": "🔥"}.get(level, "💬")
        
        with log_container:
            message = f"**{icon} {level}** | `{log.get('timestamp')}` | **{log.get('name')}**\n> {log.get('message')}"
            
            # Utiliser des couleurs différentes pour attirer l'attention
            if level in ["ERROR", "CRITICAL"]:
                st.error(message)
            elif level == "WARNING":
                st.warning(message)
            else:
                st.info(message)
            
            # Afficher les détails supplémentaires dans un expander
            extra_details = {k: v for k, v in log.items() if k not in ['level', 'timestamp', 'name', 'message']}
            if extra_details:
                with st.expander("Voir les détails complets du log"):
                    st.json(extra_details)

else:
    st.info("Aucun log à afficher. Démarrez l'agent pour commencer la journalisation.")

# Boutons de gestion
log_c1, log_c2, _ = st.columns([1, 1, 3])

def refresh_logs():
    parse_logs.clear()

if log_c1.button("🔄 Rafraîchir les logs", on_click=refresh_logs, use_container_width=True):
    st.rerun()

def clear_log_file():
    try:
        with open(AGENT_LOG_FILE, "w") as f:
            f.write("")
        parse_logs.clear()
        st.success("Fichier de log vidé.")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Impossible de vider le fichier de log : {e}")

log_c2.button("🗑️ Vider le fichier de log", on_click=clear_log_file, use_container_width=True)
