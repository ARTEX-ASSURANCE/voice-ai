# ai/dashboard/app.py (Version Corrigée)

import streamlit as st
import plotly.express as px
from core.db_connector import run_query
from PIL import Image
import pandas as pd
import os

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Dashboard KPIs | ARTEX",
    page_icon="📊",
    layout="wide"
)

# --- CHARGEMENT DES KPIS STATIQUES ---
@st.cache_data(ttl=300)
def load_static_kpis():
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

    # --- KPIs sur l'identification ---
    identity_df = run_query("SELECT COUNT(id_adherent_contexte) as confirmed, COUNT(*) as total FROM journal_appels;")
    if not identity_df.empty and identity_df['total'].iloc[0] > 0:
        confirmed_count = identity_df['confirmed'].iloc[0]
        total_for_rate = identity_df['total'].iloc[0]
        kpis['Taux d\'Identification Réussie'] = f"{(confirmed_count / total_for_rate) * 100:.2f}%"
        kpis['Appels Non Identifiés'] = total_for_rate - confirmed_count
    else:
        kpis['Taux d\'Identification Réussie'] = "0.00%"
        kpis['Appels Non Identifiés'] = 0

    # --- KPIs sur la satisfaction client ---
    feedback_df = run_query("SELECT AVG(note_satisfaction) as avg_rating, COUNT(*) as total_ratings FROM feedback_appel WHERE note_satisfaction IS NOT NULL;")
    if not feedback_df.empty and pd.notna(feedback_df['avg_rating'].iloc[0]):
        kpis['Satisfaction Client Moyenne'] = f"{feedback_df['avg_rating'].iloc[0]:.2f}/5 ⭐"
        kpis['Nombre de Feedbacks Reçus'] = feedback_df['total_ratings'].iloc[0]
    else:
        kpis['Satisfaction Client Moyenne'] = "N/A"
        kpis['Nombre de Feedbacks Reçus'] = 0

    # --- KPIs sur la santé du système ---
    errors_df = run_query("SELECT COUNT(*) as total FROM erreurs_systeme;")
    kpis['Nombre Total d\'Erreurs'] = errors_df['total'].iloc[0] if not errors_df.empty else 0
    
    # --- KPIs sur l'utilisation des outils ---
    tool_usage_df = run_query("SELECT COUNT(*) as total FROM actions_agent WHERE type_action = 'TOOL_CALL';")
    kpis['Nombre d\'Appels aux Outils'] = tool_usage_df['total'].iloc[0] if not tool_usage_df.empty else 0
    
    most_used_tool_df = run_query("""
        SELECT nom_outil, COUNT(*) as count FROM actions_agent
        WHERE type_action = 'TOOL_CALL' AND nom_outil IS NOT NULL
        GROUP BY nom_outil ORDER BY count DESC LIMIT 1;
    """)
    kpis['Outil le Plus Utilisé'] = most_used_tool_df['nom_outil'].iloc[0] if not most_used_tool_df.empty else "N/A"

    return kpis

# --- FONCTION POUR LES GRAPHIQUES D'ÉVOLUTION ---
def create_evolution_chart(title, table, date_col, value_expr, y_axis_title):
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

# --- INTERFACE UTILISATEUR ---
try:
    logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'logo.png')
    st.image(Image.open(logo_path), width=200)
except FileNotFoundError:
    st.warning("Fichier logo.png non trouvé.")

st.title("📊 Dashboard de KPIs Dynamique")
if st.button("🔄 Rafraîchir les données"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.header("Filtres des KPIs")
all_kpis = load_static_kpis()
selected_kpis = st.sidebar.multiselect("Choisissez les KPIs à afficher :", options=list(all_kpis.keys()), default=list(all_kpis.keys())[:5])

st.header("Indicateurs Clés de Performance (Vue d'ensemble)")
if selected_kpis:
    cols = st.columns(len(selected_kpis))
    for i, kpi_name in enumerate(selected_kpis):
        cols[i].metric(label=kpi_name, value=all_kpis[kpi_name])
else:
    st.warning("Veuillez sélectionner au moins un KPI à afficher.")

st.markdown("---")
st.header("Évolution des KPIs")
st.info("Chaque graphique dispose de son propre filtre de période.")

col1, col2 = st.columns(2)
with col1:
    create_evolution_chart("Nombre d'Appels par Jour", "journal_appels", "timestamp_debut", "COUNT(id_appel)", "Nombre d'Appels")
    # --- CORRECTION DE LA REQUÊTE SQL ICI ---
    create_evolution_chart("Taux d'Identification Réussie (%) par Jour", "journal_appels", "timestamp_debut", "(COUNT(id_adherent_contexte) / COUNT(id_appel)) * 100", "Taux d'Identification (%)")
with col2:
    create_evolution_chart("Satisfaction Client Moyenne par Jour", "feedback_appel", "timestamp_feedback", "AVG(note_satisfaction)", "Note Moyenne (/5)")
    create_evolution_chart("Nombre d'Erreurs par Jour", "erreurs_systeme", "timestamp_erreur", "COUNT(id_erreur)", "Nombre d'Erreurs")