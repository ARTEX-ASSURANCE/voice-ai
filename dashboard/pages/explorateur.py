# ai/dashboard/pages/explorateur.py (Version Finale avec N° Appelant)

import streamlit as st
import pandas as pd
import json
from core.db_connector import run_query
import datetime

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Explorateur d'appels | Dashboard ARTEX",
    page_icon="🔎",
    layout="wide"
)

# --- CHARGEMENT DES DONNÉES (avec la colonne numero_appelant) ---
@st.cache_data(ttl=60)
def load_call_data():
    """
    Charge les données des appels en y joignant les feedbacks et en agrégeant les outils utilisés.
    """
    query = """
    SELECT 
        ja.id_appel, 
        ANY_VALUE(ja.timestamp_debut) as timestamp_debut, 
        ANY_VALUE(ja.numero_appelant) as numero_appelant, -- Ajout de la colonne manquante
        ANY_VALUE(ja.id_adherent_contexte) as id_adherent_contexte, 
        ANY_VALUE(ja.resume_appel) as resume_appel,
        ANY_VALUE(COALESCE(ja.duree_appel_secondes, TIMESTAMPDIFF(SECOND, ja.timestamp_debut, ja.timestamp_fin))) as duree_appel_secondes,
        ANY_VALUE(COALESCE(ja.statut_appel, 'TERMINÉ')) as statut_appel,
        ANY_VALUE(COALESCE(ja.transcription_complete, '[]')) as transcription_complete,
        ANY_VALUE(ja.chemin_enregistrement_audio) as chemin_enregistrement_audio,
        ANY_VALUE(COALESCE(ja.evaluation_conformite, 'Non évalué')) as evaluation_conformite,
        ANY_VALUE(COALESCE(ja.evaluation_resolution_appel, 'Non évalué')) as evaluation_resolution_appel,
        ANY_VALUE(CASE WHEN ja.id_adherent_contexte IS NOT NULL THEN 'Confirmé' ELSE 'Non confirmé' END) as identite_confirmee,
        ANY_VALUE(fb.note_satisfaction) as note_satisfaction,
        ANY_VALUE(fb.commentaire) as commentaire,
        GROUP_CONCAT(DISTINCT aa.nom_outil SEPARATOR ', ') as outils_appeles
    FROM 
        journal_appels ja
    LEFT JOIN 
        feedback_appel fb ON ja.id_appel = fb.id_appel_fk
    LEFT JOIN 
        actions_agent aa ON ja.id_appel = aa.id_appel_fk AND aa.type_action = 'TOOL_CALL'
    GROUP BY
        ja.id_appel
    ORDER BY 
        ANY_VALUE(ja.timestamp_debut) DESC;
    """
    try:
        df = run_query(query)
        if not df.empty:
            df['timestamp_debut'] = pd.to_datetime(df['timestamp_debut'])
        return df
    except Exception as e:
        st.error(f"Erreur lors du chargement des données des appels: {e}")
        return pd.DataFrame()

# --- INTERFACE UTILISATEUR ---
st.title("🔎 Explorateur d'Appels")
st.markdown("Filtrez et explorez les enregistrements de chaque appel traité par l'agent IA.")

calls_df_raw = load_call_data()

# --- BARRE LATÉRALE DE FILTRES ---
st.sidebar.header("Filtres")
if calls_df_raw.empty:
    st.sidebar.warning("Aucune donnée d'appel à filtrer.")
    filtered_df = pd.DataFrame()
else:
    min_date = calls_df_raw['timestamp_debut'].min().date()
    max_date = calls_df_raw['timestamp_debut'].max().date()
    date_range = st.sidebar.date_input(
        "Plage de dates", (min_date, max_date), min_value=min_date, max_value=max_date
    )
    search_term = st.sidebar.text_input("Rechercher dans la transcription")
    available_statuses = calls_df_raw['statut_appel'].unique()
    selected_statuses = st.sidebar.multiselect("Statut de l'appel", options=available_statuses, default=list(available_statuses))
    identity_options = ["Tous", "Confirmé", "Non confirmé"]
    selected_identity = st.sidebar.selectbox("Confirmation d'identité", options=identity_options)

    # --- APPLICATION DES FILTRES ---
    filtered_df = calls_df_raw.copy()
    if len(date_range) == 2:
        start_date = datetime.datetime.combine(date_range[0], datetime.time.min)
        end_date = datetime.datetime.combine(date_range[1], datetime.time.max)
        filtered_df = filtered_df[(filtered_df['timestamp_debut'] >= start_date) & (filtered_df['timestamp_debut'] <= end_date)]
    if search_term:
        filtered_df = filtered_df[filtered_df['transcription_complete'].str.contains(search_term, case=False, na=False)]
    if selected_statuses:
        filtered_df = filtered_df[filtered_df['statut_appel'].isin(selected_statuses)]
    if selected_identity != "Tous":
        filtered_df = filtered_df[filtered_df['identite_confirmee'] == selected_identity]

# --- AFFICHAGE DU TABLEAU PRINCIPAL ---
st.header(f"Liste des Appels Filtrés ({len(filtered_df)})")
if not filtered_df.empty:
    df_display = filtered_df.copy()
    
    def format_tool_names(tools_string):
        if not tools_string or pd.isna(tools_string): return "—"
        tools_list = tools_string.split(', ')
        formatted_tools = [tool.replace('_', ' ').title() for tool in tools_list]
        return " → ".join(formatted_tools)

    df_display['ID Appel'] = df_display['id_appel']
    df_display['Date'] = df_display['timestamp_debut'].dt.strftime('%d/%m/%Y %H:%M')
    df_display['Appelant'] = df_display['numero_appelant'].fillna('Inconnu')
    df_display['Adhérent ID'] = df_display['id_adherent_contexte'].apply(lambda x: str(int(x)) if pd.notna(x) else 'N/A')
    df_display['Durée (sec)'] = df_display['duree_appel_secondes'].fillna(0).astype(int)
    df_display['Satisfaction'] = df_display['note_satisfaction']
    df_display['S\u00e9quence d\'Outils'] = df_display['outils_appeles'].apply(format_tool_names)

    st.data_editor(
        df_display[['ID Appel', 'Date', 'Appelant', 'Adhérent ID', 'Durée (sec)', 'S\u00e9quence d\'Outils', 'Satisfaction']],
        column_config={
            "ID Appel": st.column_config.NumberColumn("ID Appel", width="small"),
            "Date": st.column_config.TextColumn("Date et Heure", width="medium"),
            "Appelant": st.column_config.TextColumn("N° Appelant", help="Numéro de téléphone de l'appelant", width="medium"),
            "Adhérent ID": st.column_config.TextColumn("ID Adhérent", help="ID de l'adhérent si identifié", width="small"),
            "Durée (sec)": st.column_config.NumberColumn("Durée", help="Durée de l'appel en secondes", width="small"),
            "Séquence d'Outils": st.column_config.TextColumn("Séquence d'Outils", help="Outils déclenchés par l'agent", width="large"),
            "Satisfaction": st.column_config.NumberColumn("Note Client", help="Note du client (1 à 5)", format="⭐ %d"),
        },
        use_container_width=True, hide_index=True, disabled=True
    )
else:
    st.info("Aucun appel ne correspond à vos critères de filtrage.")
# --- VUE DÉTAILLÉE DE L'APPEL ---
st.markdown("---")
st.header("Détails d'un Appel Spécifique")
if not filtered_df.empty:
    call_ids = filtered_df['id_appel'].tolist()
    selected_call_id = st.selectbox("Choisissez un ID d'appel dans la liste ci-dessus pour voir les détails", options=call_ids)

    if selected_call_id:
        call_details = filtered_df[filtered_df['id_appel'] == selected_call_id].iloc[0]
        
        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader(f"Analyse de l'Appel #{selected_call_id}")
            if pd.notna(call_details['chemin_enregistrement_audio']):
                try:
                    st.audio(call_details['chemin_enregistrement_audio'])
                except Exception:
                    st.error("Fichier audio non trouvé.")
            
            st.metric("Note du Client", f"{call_details['note_satisfaction']}/5 ⭐" if pd.notna(call_details['note_satisfaction']) else "Non noté")
            if pd.notna(call_details['commentaire']):
                st.info(f'**Commentaire :** "{call_details["commentaire"]}"')

            st.markdown("**Évaluation de Conformité (IA)**")
            conformite_eval = str(call_details['evaluation_conformite'])
            if "ALERTE" in conformite_eval.upper():
                st.error(conformite_eval)
            else:
                st.success(conformite_eval)

            st.markdown("**Évaluation de Résolution (IA)**")
            resolution_eval = str(call_details['evaluation_resolution_appel'])
            if "erreur" in resolution_eval.lower() or "non déterminée" in resolution_eval.lower():
                st.warning(resolution_eval)
            else:
                st.success(resolution_eval)

        # --- SECTION TRANSCRIPTION CORRIGÉE ---
        with col2:
            st.subheader("Transcription de la Conversation")
            
            raw_transcript = call_details['transcription_complete']
            chat_container = st.container(height=500)

            try:
                transcript_data = json.loads(raw_transcript)
                
                if not isinstance(transcript_data, list) or not transcript_data:
                    chat_container.info("La transcription est vide ou dans un format non supporté pour l'affichage en chat.")
                else:
                    for message in transcript_data:
                        role = message.get("role")
                        content_list = message.get("content", [])
                        
                        # Extrait le texte, qu'il soit une chaîne ou dans une liste
                        text_content = ""
                        if content_list and isinstance(content_list, list):
                            text_content = str(content_list[0])
                        elif isinstance(content_list, str):
                            text_content = content_list

                        if role == "assistant":
                            with chat_container:
                                with st.chat_message("assistant", avatar="🤖"):
                                    st.markdown(text_content)
                        elif role == "user":
                            with chat_container:
                                with st.chat_message("user", avatar="👤"):
                                    st.markdown(text_content)

            except (json.JSONDecodeError, TypeError):
                # Si le JSON est invalide, on affiche le texte brut
                chat_container.text_area("Transcription (format brut)", value=raw_transcript, height=450, disabled=True)
else:
    st.info("Aucun appel à afficher dans la vue détaillée.")







