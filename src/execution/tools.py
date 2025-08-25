# tools.py

import logging
from typing import Optional, List
from datetime import date
from decimal import Decimal
import os
import json

# Imports pour les services externes (e-mail, etc.)
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# Imports pour la logique de l'agent
from livekit.agents import function_tool, RunContext
from src.data_access.driver import ExtranetDatabaseDriver, Adherent
from src.shared.memory import MemoryManager
# from error_logger import log_system_error # Deprecated

logger = logging.getLogger("artex_agent.tools")

# --- NOUVEL ASSISTANT DE NOTIFICATION INTERNE ---
async def _send_notification_email(subject: str, body: str) -> None:
    """
    Utilitaire interne pour envoyer des e-mails de notification à une adresse fixe.
    """
    recipient_email = "s.bouloudn@artex-business.com"
    logger.info(f"Préparation de l'envoi d'une notification par e-mail à {recipient_email}")
    try:
        api_key = os.getenv("SENDGRID_API_KEY")
        sender_email = os.getenv("SENDER_EMAIL")
        if not api_key or not sender_email:
            logger.error("La clé d'API SendGrid ou l'e-mail de l'expéditeur ne sont pas configurés. Notification non envoyée.")
            return

        message = Mail(
            from_email=sender_email,
            to_emails=recipient_email,
            subject=subject,
            html_content=body.replace('\\n', '<br>')
        )
        sg = SendGridAPIClient(api_key)
        response = sg.send(message) # Utilisation de l'envoi asynchrone

        if 200 <= response.status_code < 300:
            logger.info(f"Notification par e-mail envoyée avec succès à {recipient_email}.")
        else:
            logger.error(f"Erreur de l'API SendGrid lors de l'envoi de la notification. Statut : {response.status_code}")
    except Exception as e:
        logger.error(f"Erreur inattendue lors de l'envoi de l'e-mail de notification : {e}", exc_info=True)


# --- Assistants de Gestion de Contexte (Inchangé) ---

def _handle_lookup_result(context: RunContext, result: Optional[Adherent] | List[Adherent], source: str) -> str:
    """
    Utilitaire pour gérer le résultat d'une recherche d'adhérent. NE confirme PAS l'identité.
    Stocke les correspondances potentielles dans une variable de contexte temporaire pour confirmation.
    """
    memory: MemoryManager = context.userdata["memory"]
    if not result:
        memory.set_unconfirmed_adherent(None)
        return "Désolé, aucun adhérent correspondant n'a été trouvé avec ces informations."

    if isinstance(result, list):
        if len(result) > 1:
            return "J'ai trouvé plusieurs adhérents correspondants. Pour vous identifier précisément, pouvez-vous me donner votre adresse e-mail ou votre numéro de contrat ?"
        if not result:
            memory.set_unconfirmed_adherent(None)
            return "Désolé, aucun adhérent correspondant n'a été trouvé."
        result = result[0]

    memory.set_unconfirmed_adherent(result)
    logger.info(f"Adhérent non confirmé trouvé via {source}: {result.prenom} {result.nom} (ID: {result.id_adherent})")
    
    if source == "phone":
        return f"Bonjour, je m'adresse bien à {result.prenom} {result.nom} ?"
    
    return (f"J'ai trouvé un dossier au nom de {result.prenom} {result.nom}. "
            "Pour sécuriser l'accès, pouvez-vous me confirmer votre date de naissance et votre code postal ?")


# --- Outils d'Identité et de Contexte (Inchangé) ---

@function_tool
async def confirm_identity(context: RunContext, date_of_birth: str, postal_code: str) -> str:
    """
    Confirme l'identité de l'utilisateur en utilisant sa date de naissance ET son code postal.
    Cet outil DOIT être appelé après qu'un outil de recherche a trouvé un adhérent potentiel.
    """
    memory: MemoryManager = context.userdata["memory"]
    db: ExtranetDatabaseDriver = memory.db_driver
    unconfirmed = memory.get_unconfirmed_adherent()

    current_call_id: Optional[int] = memory.get_session_data("current_call_journal_id")
    tool_name = "confirm_identity"
    params = {"date_of_birth": date_of_birth, "postal_code": postal_code}
    result_str = ""

    if current_call_id:
        db.enregistrer_action_agent(id_appel_fk=current_call_id, type_action='TOOL_CALL', nom_outil=tool_name, parametres_outil=params)
    logger.info(f"Outil : {tool_name} appelé pour l'appel ID {current_call_id}")

    if not unconfirmed:
        result_str = "Veuillez d'abord rechercher un adhérent avant de confirmer une identité."
    else:
        try:
            dob = date.fromisoformat(date_of_birth)
            if unconfirmed.date_naissance == dob and unconfirmed.code_postal == postal_code:
                memory.set_adherent_context(unconfirmed)
                memory.set_session_data("unconfirmed_adherent", None)

                if current_call_id:
                    db.enregistrer_contexte_adherent_appel(current_call_id, unconfirmed.id_adherent)
                    logger.info(f"Contexte adhérent {unconfirmed.id_adherent} enregistré pour l'appel ID {current_call_id}.")

                logger.info(f"Identité confirmée pour : {unconfirmed.prenom} {unconfirmed.nom} (ID: {unconfirmed.id_adherent}) pour l'appel ID {current_call_id}")
                result_str = f"Merci ! Identité confirmée. Le dossier de {unconfirmed.prenom} {unconfirmed.nom} est maintenant ouvert. Comment puis-je vous aider ?"
            else:
                logger.warning(f"Échec de la confirmation d'identité pour l'ID adhérent : {unconfirmed.id_adherent} pour l'appel ID {current_call_id}")
                result_str = "Les informations ne correspondent pas. Pour votre sécurité, je ne peux pas accéder à ce dossier."
        except (ValueError, TypeError):
            logger.warning(f"Format de date de naissance invalide fourni: {date_of_birth} pour l'appel ID {current_call_id}")
            result_str = "Format de date de naissance invalide. Veuillez utiliser le format AAAA-MM-JJ, par exemple 2001-05-28."

    if current_call_id:
        db.enregistrer_action_agent(id_appel_fk=current_call_id, type_action='TOOL_RESULT', nom_outil=tool_name, resultat_outil=result_str)
    return result_str

@function_tool
async def clear_context(context: RunContext) -> str:
    """
    Efface l'adhérent actuellement sélectionné du contexte de l'assistant. À utiliser si la mauvaise personne a été identifiée ou pour terminer la session.
    """
    memory: MemoryManager = context.userdata["memory"]
    db: Optional[ExtranetDatabaseDriver] = memory.db_driver
    current_call_id: Optional[int] = memory.get_session_data("current_call_journal_id")
    tool_name = "clear_context"

    if current_call_id and db:
        db.enregistrer_action_agent(id_appel_fk=current_call_id, type_action='TOOL_CALL', nom_outil=tool_name, parametres_outil={})
    
    logger.info(f"Outil : {tool_name} appelé pour l'appel ID {current_call_id}")
    memory.set_adherent_context(None)
    memory.set_unconfirmed_adherent(None)
    result_str = "Le contexte a été réinitialisé. Comment puis-je vous aider ?"

    if current_call_id and db:
        db.enregistrer_action_agent(id_appel_fk=current_call_id, type_action='TOOL_RESULT', nom_outil=tool_name, resultat_outil=result_str)
    
    return result_str

# --- Outils de Recherche et de Gestion des Adhérents (Inchangé) ---

@function_tool
async def lookup_adherent_by_email(context: RunContext, email: str) -> str:
    """Recherche un adhérent en utilisant son adresse e-mail pour commencer le processus d'identification."""
    memory: MemoryManager = context.userdata["memory"]
    db: ExtranetDatabaseDriver = memory.db_driver
    current_call_id: Optional[int] = memory.get_session_data("current_call_journal_id")
    tool_name = "lookup_adherent_by_email"
    params = {"email": email}

    if current_call_id:
        db.enregistrer_action_agent(id_appel_fk=current_call_id, type_action='TOOL_CALL', nom_outil=tool_name, parametres_outil=params)
    
    logger.info(f"Outil : {tool_name} appelé avec email : {email} pour l'appel ID {current_call_id}")
    adherent = db.get_adherent_by_email(email.strip())
    result_str = _handle_lookup_result(context, adherent, "email")

    if current_call_id:
        db.enregistrer_action_agent(id_appel_fk=current_call_id, type_action='TOOL_RESULT', nom_outil=tool_name, resultat_outil=result_str)
    
    return result_str

@function_tool
async def lookup_adherent_by_telephone(context: RunContext, telephone: str) -> str:
    """Recherche un adhérent par son numéro de téléphone. Destiné à la recherche automatique au début d'un appel."""
    memory: MemoryManager = context.userdata["memory"]
    db: ExtranetDatabaseDriver = memory.db_driver
    current_call_id: Optional[int] = memory.get_session_data("current_call_journal_id")
    tool_name = "lookup_adherent_by_telephone"
    params = {"telephone": telephone}
    result_str = ""

    if current_call_id and db:
        db.enregistrer_action_agent(id_appel_fk=current_call_id, type_action='TOOL_CALL', nom_outil=tool_name, parametres_outil=params)
    
    logger.info(f"Outil : {tool_name} appelé avec téléphone : {telephone} pour l'appel ID {current_call_id}")
    adherents = db.get_adherents_by_telephone(telephone.strip())
    result_str = _handle_lookup_result(context, adherents, "phone")

    if current_call_id and db:
        db.enregistrer_action_agent(id_appel_fk=current_call_id, type_action='TOOL_RESULT', nom_outil=tool_name, resultat_outil=result_str)
    
    return result_str

@function_tool
async def lookup_adherent_by_fullname(context: RunContext, nom: str, prenom: str) -> str:
    """Recherche un adhérent en utilisant son nom complet pour commencer le processus d'identification."""
    memory: MemoryManager = context.userdata["memory"]
    db: ExtranetDatabaseDriver = memory.db_driver
    current_call_id: Optional[int] = memory.get_session_data("current_call_journal_id")
    tool_name = "lookup_adherent_by_fullname"
    params = {"nom": nom, "prenom": prenom}
    
    if current_call_id and db:
        db.enregistrer_action_agent(id_appel_fk=current_call_id, type_action='TOOL_CALL', nom_outil=tool_name, parametres_outil=params)
    
    logger.info(f"Outil : {tool_name} appelé avec nom : {nom}, prénom : {prenom} pour l'appel ID {current_call_id}")
    adherents = db.get_adherents_by_fullname(nom.strip(), prenom.strip())
    result_str = _handle_lookup_result(context, adherents, "fullname")

    if current_call_id and db:
        db.enregistrer_action_agent(id_appel_fk=current_call_id, type_action='TOOL_RESULT', nom_outil=tool_name, resultat_outil=result_str)

    return result_str

@function_tool
async def get_adherent_details(context: RunContext) -> str:
    """Obtient les détails personnels de l'adhérent actuellement chargé et confirmé dans le contexte de l'assistant."""
    memory: MemoryManager = context.userdata["memory"]
    adherent = memory.get_adherent_context()
    if not adherent:
        return "Aucun adhérent n'est actuellement sélectionné et confirmé. Veuillez d'abord rechercher et confirmer l'identité d'un adhérent."
    
    return (f"Détails pour {adherent.prenom} {adherent.nom} (ID: {adherent.id_adherent}): "
            f"Email: {adherent.email}, Téléphone: {adherent.telephone}, "
            f"Adresse: {adherent.adresse}, {adherent.code_postal} {adherent.ville}.")

@function_tool
async def update_contact_information(context: RunContext, address: Optional[str] = None, postal_code: Optional[str] = None, 
                                     city: Optional[str] = None, phone: Optional[str] = None, email: Optional[str] = None) -> str:
    """Met à jour les informations de contact (adresse, téléphone, e-mail) de l'adhérent actuellement confirmé."""
    memory: MemoryManager = context.userdata["memory"]
    db: ExtranetDatabaseDriver = memory.db_driver
    current_call_id: Optional[int] = memory.get_session_data("current_call_journal_id")
    tool_name = "update_contact_information"
    params = {k: v for k, v in locals().items() if k not in ['context', 'db', 'current_call_id', 'tool_name', 'memory'] and v is not None}
    
    adherent = memory.get_adherent_context()
    if not adherent:
        return "Action impossible. L'identité de l'adhérent doit être confirmée avant de pouvoir modifier des informations."

    if current_call_id and db:
        db.enregistrer_action_agent(id_appel_fk=current_call_id, type_action='TOOL_CALL', nom_outil=tool_name, parametres_outil=params)

    success = db.update_adherent_contact_info(
        adherent_id=adherent.id_adherent, address=address, code_postal=postal_code,
        ville=city, telephone=phone, email=email
    )

    if success:
        updated_adherent_data = db.get_adherent_by_id(adherent.id_adherent)
        if updated_adherent_data:
            memory.set_adherent_context(updated_adherent_data)
        result_str = "Les informations de contact ont été mises à jour avec succès."
    else:
        result_str = "Une erreur s'est produite lors de la mise à jour des informations, ou aucune information n'a été modifiée."

    if current_call_id and db:
        db.enregistrer_action_agent(id_appel_fk=current_call_id, type_action='TOOL_RESULT', nom_outil=tool_name, resultat_outil=result_str)

    return result_str

# --- OUTILS KB & Transactionnels (Inchangé) ---

@function_tool
async def list_available_products(context: RunContext, product_keyword: str) -> str:
    """
    Étape 1 : Recherche les noms des produits disponibles correspondant à un mot-clé 
    (ex: "emprunteur", "animaux") et les présente sous forme de liste pour que l'utilisateur choisisse.
    """
    memory: MemoryManager = context.userdata["memory"]
    db: ExtranetDatabaseDriver = memory.db_driver
    tool_name = "list_available_products"
    logger.info(f"Outil KB: '{tool_name}' appelé avec le mot-clé: '{product_keyword}'")

    try:
        results = db.query_knowledge_base(product_keyword=product_keyword)
        if not results:
            return f"Désolé, je n'ai trouvé aucun produit correspondant à '{product_keyword}'."

        # Extraire les noms de produits uniques
        product_names = sorted(list(set(row['nom_produit'] for row in results)))
        
        if len(product_names) == 1:
            # S'il n'y a qu'un seul produit, on demande directement si on veut les détails
            return f"J'ai trouvé un produit correspondant : {product_names[0]}. Souhaitez-vous que je vous liste ses garanties ?"
        else:
            # S'il y en a plusieurs, on les liste
            response = f"J'ai trouvé plusieurs produits de type '{product_keyword}':\\n" + "\\n".join(f"- {name}" for name in product_names)
            response += "\\n\\Lequel vous intéresse ?"
            return response

    except Exception as e:
        logger.error(f"Erreur dans {tool_name}: {e}", exc_info=True)
        return "Une erreur technique est survenue lors de la recherche des produits."


@function_tool
async def get_product_guarantees(context: RunContext, product_name: str) -> str:
    """
    Étape 2 : Récupère et liste les garanties détaillées pour UN SEUL produit spécifique,
    une fois que l'utilisateur a fait son choix.
    """
    memory: MemoryManager = context.userdata["memory"]
    db: ExtranetDatabaseDriver = memory.db_driver
    tool_name = "get_product_guarantees"
    logger.info(f"Outil KB: '{tool_name}' appelé pour le produit: '{product_name}'")

    try:
        # On utilise la recherche exacte cette fois
        results = db.query_knowledge_base(product_keyword=product_name, exact_match=True)
        if not results:
            return f"Désolé, je ne parviens pas à retrouver les détails pour le produit '{product_name}'."

        response_lines = [f"Voici les garanties pour le produit '{product_name}':"]
        for row in results:
            garantie = row.get('nom_garantie')
            if garantie:
                description = row.get('description_specifique') or "Détails non spécifiés"
                response_lines.append(f"- {garantie}: {description}")
        
        if len(response_lines) == 1: # Si on a que le titre
             return f"Aucune garantie spécifique n'est listée pour le produit '{product_name}' dans ma base de données."

        return "\\n".join(response_lines)

    except Exception as e:
        logger.error(f"Erreur dans {tool_name}: {e}", exc_info=True)
        return "Une erreur technique est survenue lors de la récupération des garanties."

@function_tool
async def list_adherent_contracts(context: RunContext) -> str:
    """Liste tous les contrats associés à l'adhérent actuellement confirmé dans le contexte."""
    memory: MemoryManager = context.userdata["memory"]
    db: ExtranetDatabaseDriver = memory.db_driver
    adherent = memory.get_adherent_context()
    if not adherent:
        return "Veuillez d'abord confirmer l'identité d'un adhérent."

    contracts = db.get_contrats_by_adherent_id(adherent.id_adherent)
    if not contracts:
        return f"Aucun contrat trouvé pour {adherent.prenom} {adherent.nom}."
    
    response_lines = [f"Voici les contrats de {adherent.prenom} {adherent.nom}:"]
    for c in contracts:
        code_produit_str = f"(Code Produit: {getattr(c, 'code_produit', 'N/A')})"
        response_lines.append(f"- Contrat N° {c.numero_contrat} {code_produit_str}, Statut: {c.statut_contrat}")
    return "\\n".join(response_lines)

@function_tool
async def create_claim(context: RunContext, contract_id: int, claim_type: str, description: str, incident_date: str) -> str:
    """Crée un nouveau sinistre pour l'adhérent actuellement confirmé."""
    memory: MemoryManager = context.userdata["memory"]
    db: ExtranetDatabaseDriver = memory.db_driver
    adherent = memory.get_adherent_context()
    if not adherent:
        return "Impossible de créer un sinistre. L'identité de l'adhérent doit d'abord être confirmée."

    try:
        parsed_date = date.fromisoformat(incident_date)
        new_claim = db.create_sinistre(
            id_contrat=contract_id, id_adherent=adherent.id_adherent,
            type_sinistre=claim_type, description_sinistre=description,
            date_survenance=parsed_date
        )
        if new_claim:
            return f"Sinistre créé avec succès! Numéro de sinistre: {new_claim.id_sinistre_artex}."
        else:
            return "Erreur lors de la création du sinistre. Vérifiez que le contrat vous appartient."
    except ValueError:
        return "Erreur: La date d'incident doit être au format AAAA-MM-JJ."


@function_tool
async def send_confirmation_email(context: RunContext, subject: str, body: str) -> str:
    """Envoie un e-mail de confirmation à l'adhérent actuellement identifié."""
    memory: MemoryManager = context.userdata["memory"]
    adherent = memory.get_adherent_context()
    if not adherent or not adherent.email:
        return "Action impossible. L'identité de l'adhérent doit être confirmée et une adresse e-mail doit être enregistrée."

    logger.info(f"Préparation de l'envoi d'un e-mail via SendGrid à {adherent.email}")
    try:
        api_key = os.getenv("SENDGRID_API_KEY")
        sender_email = os.getenv("SENDER_EMAIL")
        if not api_key or not sender_email:
            logger.error("La clé d'API SendGrid ou l'e-mail de l'expéditeur ne sont pas configurés.")
            return "Désolé, le service d'envoi d'e-mails n'est pas correctement configuré."
        
        full_body = f"Bonjour {adherent.prenom} {adherent.nom},<br><br>{body.replace('\\n', '<br>')}<br><br>Cordialement,<br>L'équipe d'ARTEX ASSURANCES"
        message = Mail(from_email=sender_email, to_emails=adherent.email, subject=subject, html_content=full_body)
        sg = SendGridAPIClient(api_key)
        response = sg.send(message) # Utilisation de l'envoi asynchrone
        
        if 200 <= response.status_code < 300:
            logger.info(f"E-mail envoyé avec succès à {adherent.email}.")
            return f"Un e-mail de confirmation a bien été envoyé à l'adresse {adherent.email}."
        else:
            logger.error(f"Erreur de l'API SendGrid. Statut : {response.status_code}, Corps : {response.body}")
            return "Une erreur est survenue lors de l'envoi de l'e-mail."
    except Exception as e:
        logger.error(f"Erreur inattendue lors de l'envoi de l'e-mail avec SendGrid : {e}")
        return "Désolé, une erreur technique majeure est survenue lors de l'envoi de l'e-mail."

# --- OUTILS DE PROSPECTION MIS À JOUR ---

@function_tool
async def request_quote(context: RunContext, product_type: str, user_details: str) -> str:
    """
    À utiliser lorsqu'un prospect demande un devis. Enregistre la demande et envoie une notification interne.
    """
    logger.info(f"Demande de devis pour un produit de type '{product_type}'. Détails fournis: {user_details}")
    
    # --- AJOUT DE LA NOTIFICATION PAR E-MAIL ---
    subject = f"Nouvelle Demande de Devis : {product_type}"
    body = f"""
    Une nouvelle demande de devis a été enregistrée par l'agent IA.
    <br><br>
    <strong>Type de produit :</strong> {product_type}<br>
    <strong>Détails fournis par le prospect :</strong> {user_details}<br>
    """
    await _send_notification_email(subject, body)
    # --- FIN DE L'AJOUT ---
    
    return "J'ai bien noté votre demande de devis. Pour vous fournir une offre précise, un conseiller commercial va vous recontacter très prochainement. Puis-je faire autre chose pour vous ?"

@function_tool
async def log_issue(context: RunContext, issue_type: str, issue_description: str) -> str:
    """Enregistre un problème complexe pour qu'un conseiller puisse le traiter."""
    memory: MemoryManager = context.userdata["memory"]
    adherent = memory.get_adherent_context()
    logger.warning(f"Problème enregistré - Type: {issue_type}, Adhérent: {adherent.id_adherent if adherent else 'N/A'}, Description: {issue_description}")
    return "Je comprends parfaitement votre situation. J'ai enregistré tous les détails de votre problème. Un conseiller spécialisé va examiner votre dossier et vous recontacter dans les plus brefs délais."

@function_tool
async def schedule_callback_with_advisor(context: RunContext, reason: str) -> str:
    """
    Planifie un rappel téléphonique avec un conseiller pour un prospect et envoie une notification interne.
    """
    memory: MemoryManager = context.userdata["memory"]
    adherent = memory.get_adherent_context()
    prospect_info = "Prospect non identifié"
    if adherent:
        prospect_info = f"Adhérent existant : {adherent.prenom} {adherent.nom} (ID: {adherent.id_adherent})"
    
    logger.info(f"Planification d'un rappel pour '{prospect_info}' pour le motif : {reason}")

    # --- AJOUT DE LA NOTIFICATION PAR E-MAIL ---
    subject = "Nouvelle Demande de Rappel Prospect/Client"
    body = f"""
    Une nouvelle demande de rappel a été programmée par l'agent ARIA.
    <br><br>
    <strong>Demandeur :</strong> {prospect_info}<br>
    <strong>Motif du rappel :</strong> {reason}<br>
    """
    await _send_notification_email(subject, body)
    # --- FIN DE L'AJOUT ---

    return "Parfait. J'ai transmis une demande de rappel à un conseiller. Il vous contactera dans les meilleurs délais."

@function_tool
async def expliquer_garantie_specifique(context: RunContext, nom_garantie: str) -> str:
    """
    Fournit les détails (plafond, taux, franchise, conditions) d'une garantie spécifique
    pour le contrat actuellement en contexte. Doit être utilisé APRÈS avoir listé les garanties.
    """
    memory: MemoryManager = context.userdata["memory"]
    db: ExtranetDatabaseDriver = memory.db_driver
    adherent = memory.get_adherent_context()
    current_call_id: Optional[int] = memory.get_session_data("current_call_journal_id")

    if not adherent:
        return "L'identité de l'adhérent doit être confirmée pour consulter les détails d'une garantie."

    # On suppose qu'un contrat est déjà dans le contexte ou qu'on peut le récupérer
    # Pour cet exemple, on prend le premier contrat actif. Une version plus avancée
    # pourrait demander de quel contrat il s'agit si l'adhérent en a plusieurs.
    contrats = db.get_contrats_by_adherent_id(adherent.id_adherent)
    contrat_actif = next((c for c in contrats if c.statut_contrat == 'Actif'), None)

    if not contrat_actif:
        return "Je n'ai pas trouvé de contrat actif pour cet adhérent pour vérifier la garantie."

    details = db.get_specific_guarantee_detail(contrat_actif.id_formule, nom_garantie)

    if not details:
        return f"Je n'ai pas trouvé de détails pour la garantie '{nom_garantie}' dans le contrat actuel."

    response = (f"Voici les détails pour la garantie '{details['libelle']}' sur votre contrat N°{contrat_actif.numero_contrat}:\\n"
                f"- Taux de remboursement : {details.get('taux_remboursement_pourcentage', 'N/A')} %\\n"
                f"- Plafond : {details.get('plafond_remboursement', 'N/A')} €\\n"
                f"- Franchise : {details.get('franchise', 'N/A')} €\\n"
                f"- Conditions spécifiques : {details.get('conditions_specifiques') or 'Aucune'}")
    return response

@function_tool
async def envoyer_document_adherent(context: RunContext, type_document: str) -> str:
    """
    Envoie un document standard (comme les Conditions Générales ou une Notice d'Information)
    par e-mail à l'adhérent actuellement identifié, concernant son contrat actif.
    """
    memory: MemoryManager = context.userdata["memory"]
    db: ExtranetDatabaseDriver = memory.db_driver
    adherent = memory.get_adherent_context()
    current_call_id: Optional[int] = memory.get_session_data("current_call_journal_id")

    if not adherent or not adherent.email:
        return "Action impossible. L'identité de l'adhérent doit être confirmée et une adresse e-mail doit être enregistrée."

    contrats = db.get_contrats_by_adherent_id(adherent.id_adherent)
    contrat_actif = next((c for c in contrats if c.statut_contrat == 'Actif'), None)

    if not contrat_actif:
        return "Je n'ai pas trouvé de contrat actif pour cet adhérent pour envoyer le document."

    # On a besoin de l'ID du produit, qui n'est pas directement dans le contrat.
    # On va chercher le produit via la formule. C'est une simplification.
    # L'idéal serait d'avoir un id_produit dans la table contrats.
    # Pour l'instant, on ne peut pas implémenter la recherche de document sans refactoriser la BDD.
    # On va donc simuler l'envoi pour l'instant.
    # NOTE: La logique de recherche de document est complexe sans lien direct contrat <-> produit.
    # Pour l'instant, on se contente d'envoyer un e-mail de confirmation.

    subject = f"Votre document : {type_document}"
    body = f"Comme demandé, veuillez trouver en pièce jointe le document '{type_document}'. (Note: la pièce jointe n'est pas gérée par cet outil pour le moment)."
    
    # On utilise l'outil existant pour envoyer l'email
    return await send_confirmation_email(context, subject=subject, body=body)


@function_tool
async def qualifier_prospect_pour_conseiller(context: RunContext, produit_interesse: str, nombre_personnes: int, budget_approximatif: str, details_supplementaires: str) -> str:
    """
    Qualifie un prospect avec des questions précises avant de planifier un rappel
    avec un conseiller et envoie une notification interne détaillée.
    """
    logger.info(f"Qualification d'un prospect pour le produit '{produit_interesse}'.")
    
    subject = f"Nouveau Prospect Qualifié : {produit_interesse}"
    body = f"""
    Un prospect a été qualifié par l'agent IA pour un rappel commercial.
    <br><br>
    <strong>Produit d'intérêt :</strong> {produit_interesse}<br>
    <strong>Nombre de personnes à assurer :</strong> {nombre_personnes}<br>
    <strong>Budget mensuel approximatif :</strong> {budget_approximatif}<br>
    <strong>Détails supplémentaires / Besoins spécifiques :</strong><br>
    <p>{details_supplementaires}</p>
    """
    await _send_notification_email(subject, body)
    
    return "Merci pour ces précisions. J'ai transmis toutes ces informations à un conseiller qui vous recontactera très prochainement avec une offre adaptée. Puis-je faire autre chose pour vous ?"

@function_tool
async def enregistrer_feedback_appel(context: RunContext, note: int, commentaire: Optional[str] = None) -> str:
    """
    Enregistre le feedback de l'utilisateur sur la qualité de l'appel à la fin de la conversation.
    La note doit être un entier entre 1 (très insatisfait) et 5 (très satisfait).
    """
    memory: MemoryManager = context.userdata["memory"]
    db: ExtranetDatabaseDriver = memory.db_driver
    current_call_id: Optional[int] = memory.get_session_data("current_call_journal_id")

    if not current_call_id:
        return "Je ne peux pas enregistrer de feedback car je n'ai pas d'identifiant d'appel."

    if not 1 <= note <= 5:
        return "La note doit être comprise entre 1 et 5."

    success = db.enregistrer_feedback(id_appel_fk=current_call_id, note=note, commentaire=commentaire)

    if success:
        return "Merci beaucoup pour votre retour, il nous est précieux pour nous améliorer."
    else:
        return "Je suis désolée, une erreur technique est survenue et je n'ai pas pu enregistrer votre retour."

@function_tool
async def transfer_call(context: RunContext, reason: str, phone_number: Optional[str] = None) -> str:
    """
    Initiates a transfer to a human agent. This tool should be used when the user
    explicitly asks to speak to a person or when the agent cannot handle the request.
    It sends a notification to a human agent and informs the user.
    """
    memory: MemoryManager = context.userdata["memory"]
    adherent = memory.get_adherent_context()

    prospect_info = "Prospect non identifié"
    contact_number = phone_number

    if adherent:
        prospect_info = f"Adhérent existant : {adherent.prenom} {adherent.nom} (ID: {adherent.id_adherent})"
        if not contact_number:
            contact_number = adherent.telephone

    if not contact_number:
        return "Je ne peux pas transférer l'appel car je n'ai pas de numéro de téléphone. Veuillez fournir un numéro."

    logger.info(f"Demande de transfert pour '{prospect_info}' au numéro {contact_number} pour le motif : {reason}")

    subject = f"Demande de Transfert Agent IA pour {prospect_info}"
    body = f"""
    Une demande de rappel/transfert a été initiée par l'agent IA.
    <br><br>
    <strong>Demandeur:</strong> {prospect_info}<br>
    <strong>Numéro de téléphone à contacter:</strong> {contact_number}<br>
    <strong>Motif du transfert:</strong> {reason}<br>
    """
    await _send_notification_email(subject, body)

    return f"Je comprends. Je notifie un conseiller qui vous rappellera au {contact_number} dans les plus brefs délais. Y a-t-il autre chose que je puisse noter pour le conseiller avant de terminer ?"

@function_tool
async def hangup_call(context: RunContext) -> str:
    """
    Ends the current call. This tool should be used after a task is completed
    or after a transfer to a human agent has been initiated.
    """
    logger.info("Fin de l'appel initiée par l'outil hangup_call.")

    # context is the AgentSession, which has a close() method.
    await context.close()

    return "Au revoir."