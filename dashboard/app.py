# dashboard/app.py
import streamlit as st
import plotly.express as px
from core.db_connector import run_query
from PIL import Image
import pandas as pd
import os
from dashboard_logger import get_dashboard_logger

# --- INITIALIZATION ---
logger = get_dashboard_logger()
st.set_page_config(
    page_title="Dashboard KPIs | ARTEX",
    page_icon="📊",
    layout="wide"
)

def load_css(file_name):
    """Loads a CSS file and injects it into the Streamlit app."""
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"CSS file not found: {file_name}")

# Load custom CSS
load_css("dashboard/style.css")

# --- DATA LOADING FUNCTIONS ---
@st.cache_data(ttl=300)
def load_kpis_for_period(day_offset=1):
    """
    Loads key KPIs for a specific day.
    day_offset=1 means today, day_offset=2 means yesterday.
    """
    kpis = {}
    query_date = f"CURDATE() - INTERVAL {day_offset - 1} DAY"

    calls_df = run_query(f"SELECT COUNT(*) as total FROM journal_appels WHERE DATE(timestamp_debut) = {query_date};")
    kpis['total_calls'] = calls_df['total'].iloc[0] if not calls_df.empty else 0

    avg_duration_df = run_query(f"SELECT AVG(COALESCE(duree_appel_secondes, TIMESTAMPDIFF(SECOND, timestamp_debut, timestamp_fin))) as avg_duration FROM journal_appels WHERE timestamp_fin IS NOT NULL AND DATE(timestamp_debut) = {query_date};")
    kpis['avg_duration'] = avg_duration_df['avg_duration'].iloc[0] if not avg_duration_df.empty and pd.notna(avg_duration_df['avg_duration'].iloc[0]) else 0

    feedback_df = run_query(f"SELECT AVG(note_satisfaction) as avg_rating FROM feedback_appel WHERE timestamp_feedback IS NOT NULL AND DATE(timestamp_feedback) = {query_date};")
    kpis['avg_satisfaction'] = feedback_df['avg_rating'].iloc[0] if not feedback_df.empty and pd.notna(feedback_df['avg_rating'].iloc[0]) else 0

    return kpis

@st.cache_data(ttl=300)
def load_static_kpis():
    logger.info("Loading static KPIs.")
    try:
        kpis = {}
        # --- KPIs sur le volume d'appels ---
        total_calls_df = run_query("SELECT COUNT(*) as total FROM journal_appels;")
        kpis['Nombre Total d\'Appels'] = total_calls_df['total'].iloc[0] if not total_calls_df.empty else 0

        calls_today_df = run_query("SELECT COUNT(*) as total FROM journal_appels WHERE DATE(timestamp_debut) = CURDATE();")
        kpis['Appels Aujourd\'hui'] = calls_today_df['total'].iloc[0] if not calls_today_df.empty else 0

        # --- KPIs sur la durée et la performance ---
        avg_duration_query = "SELECT AVG(COALESCE(duree_appel_secondes, TIMESTAMPDIFF(SECOND, timestamp_debut, timestamp_fin))) as avg_duration FROM journal_appels WHERE timestamp_fin IS NOT NULL;"
        avg_duration_df = run_query(avg_duration_query)
        kpis['Durée Moyenne des Appels (sec)'] = f"{avg_duration_df['avg_duration'].iloc[0]:.0f}" if not avg_duration_df.empty and pd.notna(avg_duration_df['avg_duration'].iloc[0]) else 0

        # ... (rest of the KPI logic is the same)
        identity_df = run_query("SELECT COUNT(id_adherent_contexte) as confirmed, COUNT(*) as total FROM journal_appels;")
        if not identity_df.empty and identity_df['total'].iloc[0] > 0:
            confirmed_count = identity_df['confirmed'].iloc[0]
            total_for_rate = identity_df['total'].iloc[0]
            kpis['Taux d\'Identification Réussie'] = f"{(confirmed_count / total_for_rate) * 100:.2f}%"
            kpis['Appels Non Identifiés'] = total_for_rate - confirmed_count
        else:
            kpis['Taux d\'Identification Réussie'] = "0.00%"
            kpis['Appels Non Identifiés'] = 0
        feedback_df = run_query("SELECT AVG(note_satisfaction) as avg_rating, COUNT(*) as total_ratings FROM feedback_appel WHERE note_satisfaction IS NOT NULL;")
        if not feedback_df.empty and pd.notna(feedback_df['avg_rating'].iloc[0]):
            kpis['Satisfaction Client Moyenne'] = f"{feedback_df['avg_rating'].iloc[0]:.2f}/5 ⭐"
            kpis['Nombre de Feedbacks Reçus'] = feedback_df['total_ratings'].iloc[0]
        else:
            kpis['Satisfaction Client Moyenne'] = "N/A"
            kpis['Nombre de Feedbacks Reçus'] = 0
        errors_df = run_query("SELECT COUNT(*) as total FROM erreurs_systeme;")
        kpis['Nombre Total d\'Erreurs'] = errors_df['total'].iloc[0] if not errors_df.empty else 0
        tool_usage_df = run_query("SELECT COUNT(*) as total FROM actions_agent WHERE type_action = 'TOOL_CALL';")
        kpis['Nombre d\'Appels aux Outils'] = tool_usage_df['total'].iloc[0] if not tool_usage_df.empty else 0
        most_used_tool_df = run_query("""
            SELECT nom_outil, COUNT(*) as count FROM actions_agent
            WHERE type_action = 'TOOL_CALL' AND nom_outil IS NOT NULL
            GROUP BY nom_outil ORDER BY count DESC LIMIT 1;
        """)
        kpis['Outil le Plus Utilisé'] = most_used_tool_df['nom_outil'].iloc[0] if not most_used_tool_df.empty else "N/A"

        logger.info("KPIs loaded successfully.")
        return kpis
    except Exception as e:
        logger.error("Failed to load static KPIs.", exc_info=True)
        st.error(f"Erreur critique lors du chargement des KPIs: {e}")
        return {} # Return empty dict to prevent crash

# --- CHARTING FUNCTION ---
def create_evolution_chart(title, table, date_col, value_expr, y_axis_title):
    # ... (function is unchanged)
    with st.expander(f"Évolution de : {title}", expanded=True):
        period_options = {"7 derniers jours": 7, "30 derniers jours": 30, "90 derniers jours": 90}
        selected_period_label = st.selectbox("Choisir la période :", options=list(period_options.keys()), key=f"select_{title}")
        days = period_options[selected_period_label]

        query = f"""
            SELECT DATE({date_col}) as jour, {value_expr} as valeur
            FROM {table}
            WHERE {date_col} >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)
            GROUP BY jour ORDER BY jour ASC;
        """
        data = run_query(query)
        if not data.empty:
            fig = px.line(data, x='jour', y='valeur', title=title, markers=True, labels={"jour": "Date", "valeur": y_axis_title})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"Aucune donnée disponible pour les {days} derniers jours.")

# --- MAIN UI ---
def main():
    logger.info("Main dashboard UI rendering started.")
    try:
        logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'logo.png')
        st.image(Image.open(logo_path), width=200)
    except FileNotFoundError:
        logger.warning("Logo file not found at path: assets/logo.png")
        st.warning("Fichier logo.png non trouvé.")

    st.title("📊 Dashboard de Performance ARTEX")
    st.markdown("Vue d'ensemble de la performance du système et de l'agent conversationnel.")

    if st.button("🔄 Rafraîchir les données"):
        logger.info("User clicked refresh data button.")
        st.cache_data.clear()
        st.rerun()

    all_kpis = load_static_kpis()
    if not all_kpis:
        st.error("Impossible d'afficher les KPIs car les données n'ont pas pu être chargées.")
        return

    # --- Tabs Layout ---
    tab1, tab2, tab3 = st.tabs(["📈 Vue d'Ensemble", "📞 Tendances des Appels", "🤖 Analyse de l'Agent"])

    with tab1:
        st.header("Indicateurs Clés de Performance (KPIs)")

        # Enhanced KPI Metrics with Deltas
        kpis_today = load_kpis_for_period(1)
        kpis_yesterday = load_kpis_for_period(2) # Day before today

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            delta_calls = kpis_today.get('total_calls', 0) - kpis_yesterday.get('total_calls', 0)
            st.metric("Appels Aujourd'hui", kpis_today.get('total_calls', 0), f"{delta_calls:+.0f} vs hier")
        with col2:
            delta_duration = kpis_today.get('avg_duration', 0) - kpis_yesterday.get('avg_duration', 0)
            st.metric("Durée Moyenne (sec)", f"{kpis_today.get('avg_duration', 0):.0f}", f"{delta_duration:+.0f}s vs hier")
        with col3:
            delta_satisfaction = kpis_today.get('avg_satisfaction', 0) - kpis_yesterday.get('avg_satisfaction', 0)
            st.metric("Satisfaction Client", f"{kpis_today.get('avg_satisfaction', 0):.2f}/5 ⭐", f"{delta_satisfaction:+.2f} vs hier")
        with col4:
            st.metric("Total Erreurs Système", all_kpis.get('Nombre Total d\'Erreurs', 0))

    with tab2:
        st.header("Évolution Temporelle des Métriques d'Appel")
        col1, col2 = st.columns(2)
        with col1:
            create_evolution_chart("Nombre d'Appels par Jour", "journal_appels", "timestamp_debut", "COUNT(id_appel)", "Nombre d'Appels")
            create_evolution_chart("Satisfaction Client Moyenne par Jour", "feedback_appel", "timestamp_feedback", "AVG(note_satisfaction)", "Note Moyenne (/5)")
        with col2:
            create_evolution_chart("Taux d'Identification Réussie (%) par Jour", "journal_appels", "timestamp_debut", "(COUNT(id_adherent_contexte) / COUNT(id_appel)) * 100", "Taux d'Identification (%)")
            create_evolution_chart("Nombre d'Erreurs par Jour", "erreurs_systeme", "timestamp_erreur", "COUNT(id_erreur)", "Nombre d'Erreurs")

    with tab3:
        st.header("Analyse de la Performance de l'Agent IA")
        col1, col2 = st.columns(2)
        with col1:
            # New Bar Chart for Tool Usage
            st.subheader("Utilisation des Outils par l'Agent")
            tool_usage_df = run_query("""
                SELECT nom_outil, COUNT(*) as count
                FROM actions_agent
                WHERE type_action = 'TOOL_CALL' AND nom_outil IS NOT NULL
                GROUP BY nom_outil
                ORDER BY count DESC
            """)
            if not tool_usage_df.empty:
                fig = px.bar(tool_usage_df, x='count', y='nom_outil', orientation='h', title="Nombre d'appels par outil", labels={'count':"Nombre d'utilisations", 'nom_outil': "Outil"})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucune donnée sur l'utilisation des outils disponible.")

        with col2:
            # New Pie Chart for Call Resolution
            st.subheader("Résolution des Appels")
            resolution_df = run_query("""
                SELECT COALESCE(evaluation_resolution_appel, 'Non évalué') as resolution, COUNT(*) as count
                FROM journal_appels
                GROUP BY resolution
            """)
            if not resolution_df.empty:
                fig = px.pie(resolution_df, names='resolution', values='count', title="Répartition des statuts de résolution d'appel")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucune donnée sur la résolution des appels disponible.")

    logger.info("Dashboard UI rendering finished.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error("An unhandled exception occurred in the main dashboard execution.", exc_info=True)
        st.error("Une erreur majeure et inattendue est survenue. L'incident a été enregistré.")