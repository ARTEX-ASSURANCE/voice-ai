# dashboard/app.py
import streamlit as st
import plotly.express as px
from core.db_connector import run_query
from PIL import Image
import pandas as pd
import os
from dashboard_logger import get_dashboard_logger

# dashboard/app.py
import streamlit as st
import plotly.express as px
from core.db_connector import run_query
from PIL import Image
import pandas as pd
import os
from dashboard_logger import get_dashboard_logger

# --- INITIALISATION ---
logger = get_dashboard_logger()
st.set_page_config(
    page_title="Dashboard KPIs | ARTEX",
    page_icon="📊",
    layout="wide"
)

def load_css(file_name):
    """Charge un fichier CSS et l'injecte dans l'application Streamlit."""
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"Fichier CSS non trouvé : {file_name}")

# Charge le CSS personnalisé
load_css("dashboard/style.css")

# --- FONCTIONS DE CHARGEMENT DES DONNÉES ---
@st.cache_data(ttl=300)
def load_kpis_for_period(day_offset=1):
    """
    Charge les KPIs clés pour un jour spécifique.
    day_offset=1 signifie aujourd'hui, day_offset=2 signifie hier.
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
    """Charge les KPIs statiques qui ne dépendent pas de la date."""
    logger.info("Chargement des KPIs statiques.")
    try:
        kpis = {}
        total_calls_df = run_query("SELECT COUNT(*) as total FROM journal_appels;")
        kpis['Nombre Total d\'Appels'] = total_calls_df['total'].iloc[0] if not total_calls_df.empty else 0

        errors_df = run_query("SELECT COUNT(*) as total FROM erreurs_systeme;")
        kpis['Nombre Total d\'Erreurs'] = errors_df['total'].iloc[0] if not errors_df.empty else 0

        logger.info("KPIs statiques chargés avec succès.")
        return kpis
    except Exception as e:
        logger.error("Échec du chargement des KPIs statiques.", exc_info=True)
        st.error(f"Erreur critique lors du chargement des KPIs: {e}")
        return {}

# --- FONCTION DE CRÉATION DE GRAPHIQUE ---
def create_evolution_chart(title, table, date_col, value_expr, y_axis_title):
    """Crée un graphique d'évolution pour une métrique donnée."""
    with st.expander(f"Évolution de : {title}", expanded=True):
        period_options = {"7 derniers jours": 7, "30 derniers jours": 30, "90 derniers jours": 90}
        selected_period_label = st.selectbox("Choisir la période :", options=list(period_options.keys()), key=f"select_{title}")
        days = period_options[selected_period_label]

        query = f"SELECT DATE({date_col}) as jour, {value_expr} as valeur FROM {table} WHERE {date_col} >= DATE_SUB(CURDATE(), INTERVAL {days} DAY) GROUP BY jour ORDER BY jour ASC;"
        data = run_query(query)
        if not data.empty:
            fig = px.line(data, x='jour', y='valeur', title=title, markers=True, labels={"jour": "Date", "valeur": y_axis_title})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"Aucune donnée disponible pour les {days} derniers jours.")

# --- INTERFACE UTILISATEUR PRINCIPALE ---
def main():
    logger.info("Rendu de l'interface principale du dashboard démarré.")
    try:
        logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'logo.png')
        st.image(Image.open(logo_path), width=200)
    except FileNotFoundError:
        logger.warning("Fichier logo.png non trouvé au chemin : assets/logo.png")
        st.warning("Fichier logo.png non trouvé.")

    st.title("📊 Dashboard de Performance ARTEX")
    st.markdown("Vue d'ensemble de la performance du système et de l'agent conversationnel.")

    if st.button("🔄 Rafraîchir les données"):
        logger.info("L'utilisateur a cliqué sur le bouton de rafraîchissement.")
        st.cache_data.clear()
        st.rerun()

    all_kpis = load_static_kpis()
    if not all_kpis:
        st.error("Impossible d'afficher les KPIs car les données n'ont pas pu être chargées.")
        return

    tab1, tab2, tab3 = st.tabs(["📈 Vue d'Ensemble", "📞 Tendances des Appels", "🤖 Analyse de l'Agent"])

    with tab1:
        st.header("Indicateurs Clés de Performance (KPIs)")
        kpis_today = load_kpis_for_period(1)
        kpis_yesterday = load_kpis_for_period(2)

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
            st.subheader("Utilisation des Outils par l'Agent")
            tool_usage_df = run_query("SELECT nom_outil, COUNT(*) as count FROM actions_agent WHERE type_action = 'TOOL_CALL' AND nom_outil IS NOT NULL GROUP BY nom_outil ORDER BY count DESC")
            if not tool_usage_df.empty:
                fig = px.bar(tool_usage_df, x='count', y='nom_outil', orientation='h', title="Nombre d'appels par outil", labels={'count':"Nombre d'utilisations", 'nom_outil': "Outil"})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucune donnée sur l'utilisation des outils disponible.")
        with col2:
            st.subheader("Résolution des Appels")
            resolution_df = run_query("SELECT COALESCE(evaluation_resolution_appel, 'Non évalué') as resolution, COUNT(*) as count FROM journal_appels GROUP BY resolution")
            if not resolution_df.empty:
                fig = px.pie(resolution_df, names='resolution', values='count', title="Répartition des statuts de résolution d'appel")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucune donnée sur la résolution des appels disponible.")

    logger.info("Rendu de l'interface du dashboard terminé.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error("Une exception non gérée est survenue dans l'exécution principale du dashboard.", exc_info=True)
        st.error("Une erreur majeure et inattendue est survenue. L'incident a été enregistré.")