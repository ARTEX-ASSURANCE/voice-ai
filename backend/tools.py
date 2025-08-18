# tools.py (Réfractorié pour le nouveau schéma)

import logging
from typing import Optional, List
from datetime import date, datetime, timedelta
from decimal import Decimal
import os
import json

# Services externes
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Logique de l'agent
from livekit.agents import function_tool, RunContext
from db_driver import ExtranetDatabaseDriver, Client

logger = logging.getLogger("artex_agent.tools")

# --- Aide à la Notification Interne ---
async def _send_notification_email(subject: str, body: str) -> None:
    recipient_email = "s.bouloudn@artex-business.com"
    logger.info(f"Préparation de l'envoi d'un e-mail de notification à {recipient_email}")
    try:
        api_key = os.getenv("SENDGRID_API_KEY")
        sender_email = os.getenv("SENDER_EMAIL")
        if not api_key or not sender_email:
            logger.error("Clé API SendGrid ou e-mail de l'expéditeur non configuré.")
            return

        message = Mail(from_email=sender_email, to_emails=recipient_email, subject=subject, html_content=body.replace('\\n', '<br>'))
        sg = SendGridAPIClient(api_key)
        await sg.send(message)
        logger.info(f"E-mail de notification envoyé avec succès à {recipient_email}.")
    except Exception as e:
        logger.error(f"Erreur inattendue lors de l'envoi de l'e-mail de notification : {e}", exc_info=True)

# --- Aide à la Gestion de Contexte ---

def _handle_lookup_result(context: RunContext, result: Optional[Client] | List[Client], source: str) -> str:
    if not result:
        context.userdata["unconfirmed_client"] = None
        return "Désolé, aucun client correspondant n'a été trouvé avec ces informations."

    if isinstance(result, list):
        if len(result) > 1:
            return "J'ai trouvé plusieurs clients correspondants. Pour vous identifier précisément, pouvez-vous me donner votre adresse e-mail ?"
        if not result:
            context.userdata["unconfirmed_client"] = None
            return "Désolé, aucun client correspondant n'a été trouvé."
        result = result[0]

    context.userdata["unconfirmed_client"] = result
    logger.info(f"Client non confirmé trouvé via {source}: {result.FirstName} {result.LastName} (ID: {result.Id})")
    
    # Invite de confirmation simplifiée
    return f"J'ai trouvé un dossier pour {result.FirstName} {result.LastName}. Pouvez-vous confirmer qu'il s'agit bien de vous pour que je puisse accéder au dossier en toute sécurité ?"

# --- Outils d'Identité et de Contexte (Réfractoriés) ---

@function_tool
async def confirm_identity(context: RunContext, confirmation: bool) -> str:
    """
    Confirme l'identité de l'utilisateur s'il accepte être la personne trouvée.
    Cet outil DOIT être appelé après qu'un outil de recherche a trouvé un client potentiel.
    Après confirmation, vérifie de manière proactive les informations pertinentes comme les rendez-vous à venir.
    """
    unconfirmed: Optional[Client] = context.userdata.get("unconfirmed_client")
    if not unconfirmed:
        return "Veuillez rechercher un client avant de confirmer une identité."

    if confirmation:
        context.userdata["client_context"] = unconfirmed
        context.userdata["unconfirmed_client"] = None
        logger.info(f"Identité confirmée pour : {unconfirmed.FirstName} {unconfirmed.LastName} (ID: {unconfirmed.Id})")

        # Logique proactive
        response_parts = [f"Merci ! Identité confirmée. Le dossier de {unconfirmed.FirstName} {unconfirmed.LastName} est maintenant ouvert."]

        # Vérification proactive des rendez-vous
        db: ExtranetDatabaseDriver = context.userdata["db_driver"]
        appointments = db.get_upcoming_appointments(unconfirmed.Id)
        if appointments:
            appointment_list = [f"- {appt.ForDate.strftime('%d/%m/%Y à %H:%M')} pour : {appt.Comment}" for appt in appointments]
            response_parts.append("D'ailleurs, je vois que vous avez des rendez-vous à venir :\\n" + "\\n".join(appointment_list))

        response_parts.append("Comment puis-je vous aider ?")
        return " ".join(response_parts)
    else:
        context.userdata["unconfirmed_client"] = None
        logger.warning(f"L'utilisateur a refusé la confirmation d'identité pour le client ID : {unconfirmed.Id}")
        return "D'accord, je n'accéderai pas à ce dossier. Comment puis-je vous aider ?"

@function_tool
async def clear_context(context: RunContext) -> str:
    """Efface le client actuellement sélectionné du contexte de l'assistant."""
    context.userdata["client_context"] = None
    context.userdata["unconfirmed_client"] = None
    return "Le contexte a été réinitialisé. Comment puis-je vous aider ?"

# --- Outils de Recherche de Client (Réfractoriés) ---

@function_tool
async def lookup_client_by_email(context: RunContext, email: str) -> str:
    """Recherche un client en utilisant son adresse e-mail pour démarrer le processus d'identification."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    logger.info(f"Outil : lookup_client_by_email appelé avec l'e-mail : {email}")
    client = db.get_client_by_email(email.strip())
    return _handle_lookup_result(context, client, "email")

@function_tool
async def lookup_client_by_phone(context: RunContext, phone: str) -> str:
    """Recherche un client par son numéro de téléphone."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    logger.info(f"Outil : lookup_client_by_phone appelé avec le téléphone : {phone}")
    clients = db.get_clients_by_phone(phone.strip())
    return _handle_lookup_result(context, clients, "phone")

@function_tool
async def lookup_client_by_fullname(context: RunContext, last_name: str, first_name: str) -> str:
    """Recherche un client en utilisant son nom complet."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    logger.info(f"Outil : lookup_client_by_fullname appelé avec le nom : {first_name} {last_name}")
    clients = db.get_clients_by_fullname(last_name.strip(), first_name.strip())
    return _handle_lookup_result(context, clients, "fullname")

@function_tool
async def get_client_details(context: RunContext) -> str:
    """Obtient les détails personnels du client actuellement chargé et confirmé."""
    client: Optional[Client] = context.userdata.get("client_context")
    if not client:
        return "Aucun client n'est actuellement sélectionné et confirmé. Veuillez d'abord rechercher et confirmer l'identité d'un client."
    
    return (f"Détails pour {client.FirstName} {client.LastName} (ID: {client.Id}): "
            f"Email: {client.Email}, Téléphone: {client.Phone}, "
            f"Adresse: {client.Address}, {client.City}.")

@function_tool
async def update_contact_information(context: RunContext, address: Optional[str] = None, city: Optional[str] = None, phone: Optional[str] = None, email: Optional[str] = None) -> str:
    """Met à jour les informations de contact du client actuellement confirmé."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    client: Optional[Client] = context.userdata.get("client_context")
    if not client:
        return "Action impossible. L'identité du client doit être confirmée avant que les informations puissent être modifiées."

    success = db.update_client_contact_info(client_id=client.Id, address=address, city=city, phone=phone, email=email)

    if success:
        # Rafraîchit le contexte client avec les nouvelles données
        updated_client = db.get_client_by_id(client.Id)
        if updated_client:
            context.userdata["client_context"] = updated_client
        return "Les informations de contact ont été mises à jour avec succès."
    else:
        return "Une erreur s'est produite lors de la mise à jour des informations, ou aucune information n'a été modifiée."

# --- Outils d'Action & Communication (Partiellement Réfractoriés) ---

@function_tool
async def list_client_contracts(context: RunContext) -> str:
    """Liste tous les contrats associés au client actuellement confirmé."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    client: Optional[Client] = context.userdata.get("client_context")
    if not client:
        return "Veuillez d'abord confirmer l'identité du client."

    contracts = db.get_contracts_by_client_id(client.Id)
    if not contracts:
        return f"Aucun contrat trouvé pour {client.FirstName} {client.LastName}."
    
    response_lines = [f"Voici les contrats pour {client.FirstName} {client.LastName}:"]
    for c in contracts:
        response_lines.append(f"- Contrat Réf {c.Reference}, Statut: {c.Status}")
    return "\\n".join(response_lines)

@function_tool
async def send_confirmation_email(context: RunContext, subject: str, body: str) -> str:
    """Envoie un e-mail de confirmation au client actuellement identifié."""
    client: Optional[Client] = context.userdata.get("client_context")
    if not client or not client.Email:
        return "Action impossible. L'identité du client doit être confirmée et une adresse e-mail doit être enregistrée."

    logger.info(f"Préparation de l'envoi d'un e-mail via SendGrid à {client.Email}")
    try:
        api_key = os.getenv("SENDGRID_API_KEY")
        sender_email = os.getenv("SENDER_EMAIL")
        if not api_key or not sender_email:
            logger.error("Clé API SendGrid ou e-mail de l'expéditeur non configuré.")
            return "Désolé, le service de messagerie n'est pas correctement configuré."
        
        full_body = f"Bonjour {client.FirstName} {client.LastName},<br><br>{body.replace('\\n', '<br>')}<br><br>Cordialement,<br>L'équipe"
        message = Mail(from_email=sender_email, to_emails=client.Email, subject=subject, html_content=full_body)
        sg = SendGridAPIClient(api_key)
        response = await sg.send(message)
        
        if 200 <= response.status_code < 300:
            logger.info(f"E-mail envoyé avec succès à {client.Email}.")
            return f"Un e-mail de confirmation a été envoyé à {client.Email}."
        else:
            logger.error(f"Erreur de l'API SendGrid. Statut: {response.status_code}, Corps: {response.body}")
            return "Une erreur s'est produite lors de l'envoi de l'e-mail."
    except Exception as e:
        logger.error(f"Erreur inattendue lors de l'envoi de l'e-mail avec SendGrid : {e}")
        return "Désolé, une erreur technique majeure s'est produite lors de l'envoi de l'e-mail. Souhaitez-vous que je planifie un rappel avec un conseiller pour m'assurer que votre demande soit bien prise en compte ?"

@function_tool
async def schedule_callback(context: RunContext, reason: str, datetime_str: str) -> str:
    """
    Planifie un rappel pour le client actuel en créant un événement dans Google Calendar.
    CRITIQUE : Le paramètre 'datetime_str' DOIT être une chaîne au format ISO 8601 exact : 'YYYY-MM-DDTHH:MM:SS'.
    Vous devez convertir toute date ou heure en langage naturel (par exemple, 'demain à 14h') dans ce format de chaîne spécifique avant d'appeler cet outil.
    Exemple : Une demande pour 'le 25 décembre 2024 à 14h30' doit être convertie en '2024-12-25T14:30:00'.
    """
    client: Optional[Client] = context.userdata.get("client_context")
    if not client:
        return "L'identité du client doit être confirmée avant de pouvoir planifier un rappel."

    logger.info(f"Tentative de planification d'un rappel pour le client {client.Id} à {datetime_str}")

    try:
        creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID")

        if not creds_path or not calendar_id:
            logger.error("Les informations d'identification de Google Calendar ou l'ID du calendrier ne sont pas configurés dans les variables d'environnement.")
            return "Le service de calendrier n'est pas configuré. Impossible de planifier un rappel."

        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=['https://www.googleapis.com/auth/calendar'])
        service = build('calendar', 'v3', credentials=creds)

        start_time = datetime.fromisoformat(datetime_str)
        end_time = start_time + timedelta(minutes=30)

        event = {
            'summary': f'Rappel pour : {client.FirstName} {client.LastName} (ID: {client.Id})',
            'description': f'Raison : {reason}',
            'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Europe/Paris'},
            'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Europe/Paris'},
        }

        created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
        logger.info(f"Événement créé : {created_event.get('htmlLink')}")
        return f"J'ai planifié un rappel pour vous le {start_time.strftime('%d/%m/%Y à %H:%M')}. Un conseiller vous appellera."

    except HttpError as error:
        logger.error(f"Une erreur s'est produite avec l'API Google Calendar : {error}")
        return "Une erreur s'est produite lors de la communication avec le service de calendrier."
    except ValueError:
        logger.error(f"Format de date et d'heure invalide pour schedule_callback : {datetime_str}")
        return "Le format de la date et de l'heure est invalide. Veuillez utiliser le format ISO, par exemple, '2024-12-25T14:30:00'."
    except Exception as e:
        logger.error(f"Une erreur inattendue s'est produite dans schedule_callback : {e}", exc_info=True)
        return "Une erreur technique inattendue s'est produite lors de la planification du rappel."

# --- NOUVEAUX OUTILS (Basés sur le nouveau schéma) ---

@function_tool
async def get_contract_details(context: RunContext, contract_reference: str) -> str:
    """Obtient les détails d'un contrat spécifique en utilisant sa référence."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    client: Optional[Client] = context.userdata.get("client_context")
    if not client:
        return "Veuillez d'abord confirmer l'identité du client."

    contract = db.get_contract_by_ref(contract_reference)
    if not contract or contract.ClientId != client.Id:
        return f"Aucun contrat trouvé avec la référence {contract_reference} pour {client.FirstName} {client.LastName}."

    details = (f"Détails du contrat {contract.Reference}: Statut - {contract.Status}, "
               f"Prix - {contract.Price}€, Date d'effet - {contract.EffectiveDate}, "
               f"Date de résiliation - {contract.TerminationDate or 'N/A'}.")
    return details

@function_tool
async def get_client_interaction_history(context: RunContext) -> str:
    """Récupère un résumé des 5 dernières interactions terminées pour le client confirmé."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    client: Optional[Client] = context.userdata.get("client_context")
    if not client:
        return "Veuillez d'abord confirmer l'identité du client."

    history = db.get_client_history(client.Id)
    if not history:
        return "Aucun historique d'interaction trouvé pour ce client."

    response_lines = ["Voici un résumé des dernières interactions :"]
    for event in history:
        response_lines.append(f"- Le {event.ForDate.strftime('%d/%m/%Y')}: {event.Comment} (Réf Événement: {event.EventId})")
    return "\\n".join(response_lines)

@function_tool
async def check_upcoming_appointments(context: RunContext) -> str:
    """Vérifie les rendez-vous ou rappels à venir pour le client confirmé."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    client: Optional[Client] = context.userdata.get("client_context")
    if not client:
        return "Veuillez d'abord confirmer l'identité du client."

    appointments = db.get_upcoming_appointments(client.Id)
    if not appointments:
        return "Il n'y a aucun rendez-vous à venir de prévu pour ce client."

    response_lines = ["Voici les prochains rendez-vous :"]
    for event in appointments:
        response_lines.append(f"- Le {event.ForDate.strftime('%d/%m/%Y à %H:%M')}: {event.Comment}")
    return "\\n".join(response_lines)

@function_tool
async def find_employee_for_escalation(context: RunContext, name: Optional[str] = None, function: Optional[str] = None) -> str:
    """
    Trouve un employé actif pour une escalade. Peut chercher par nom et/ou par fonction (ex: 'Support', 'Vente').
    Notifie l'employé trouvé.
    """
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    employees = db.find_active_employee(name=name, function=function)

    if not employees:
        return "Désolé, je n'ai trouvé aucun employé actif correspondant à ces critères."
    if len(employees) > 1:
        return f"J'ai trouvé plusieurs employés correspondants : {', '.join([f'{e.FirstName} {e.LastName}' for e in employees])}. Pouvez-vous être plus spécifique ?"

    employee = employees[0]
    subject = "Escalade d'appel client"
    body = f"Un appel nécessite votre attention. Veuillez consulter le dossier du client."
    await _send_notification_email(subject, body)
    return f"J'ai trouvé {employee.FirstName} {employee.LastName} ({employee.Function}) et lui ai envoyé une notification pour une prise en charge."

@function_tool
async def get_contract_company_info(context: RunContext, contract_reference: str) -> str:
    """Récupère les informations sur la compagnie d'assurance qui gère un contrat spécifique."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    client: Optional[Client] = context.userdata.get("client_context")
    if not client:
        return "Veuillez d'abord confirmer l'identité du client."

    contract = db.get_contract_by_ref(contract_reference)
    if not contract or contract.ClientId != client.Id or not contract.CompanyId:
        return f"Impossible de trouver les informations de la compagnie pour le contrat {contract_reference}."

    company = db.get_company_by_id(contract.CompanyId)
    if not company:
        return "Détails de la compagnie non trouvés."

    return (f"Le contrat {contract.Reference} est géré par {company.Name}. "
            f"Leur contact : Téléphone - {company.PhoneNumber or 'N/A'}, Email - {company.Email or 'N/A'}.")

@function_tool
async def get_contract_formula_details(context: RunContext, contract_reference: str) -> str:
    """Obtient les détails de la formule (offre produit) pour un contrat spécifique."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    client: Optional[Client] = context.userdata.get("client_context")
    if not client:
        return "Veuillez d'abord confirmer l'identité du client."

    contract = db.get_contract_by_ref(contract_reference)
    if not contract or contract.ClientId != client.Id or not contract.FormulaId:
        return f"Impossible de trouver les détails de la formule pour le contrat {contract_reference}."

    formula = db.get_formula_by_id(contract.FormulaId)
    if not formula:
        return "Détails de la formule non trouvés."

    return (f"Le contrat {contract.Reference} est basé sur la formule '{formula.Name}'. "
            f"Description : {formula.Description} Prix standard : {formula.Price}€.")

@function_tool
async def summarize_advisory_duty(context: RunContext) -> str:
    """Fournit un résumé du document 'devoir de conseil' pour rassurer le client sur la pertinence de son contrat."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    client: Optional[Client] = context.userdata.get("client_context")
    if not client:
        return "Veuillez d'abord confirmer l'identité du client."

    duty = db.get_advisory_duty(client.Id)
    if not duty:
        return "Aucun résumé de devoir de conseil n'a été trouvé pour ce client."

    summary = (f"Pour vous rassurer sur le choix de votre contrat, voici un résumé de notre analyse initiale : "
               f"Votre situation était : '{duty.ClientSituation}' avec un budget de '{duty.Budget}'. "
               f"Vos besoins principaux étaient : {duty.Need1}, {duty.Need2}, et {duty.Need3}. "
               f"C'est sur cette base que la compagnie {duty.SelectedCompany} a été recommandée.")
    return summary

# --- Outils Obsolètes/Supprimés (Commentés pour Référence) ---
# Les outils suivants dépendaient de l'ancien schéma et ont été désactivés.
# Ils devraient être ré-implémentés en fonction du nouveau schéma si leur fonctionnalité est toujours requise.

# @function_tool
# async def create_claim(...)
#
# @function_tool
# async def list_available_products(...)
#
# @function_tool
# async def get_product_guarantees(...)
#
# @function_tool
# async def expliquer_garantie_specifique(...)
#
# @function_tool
# async def envoyer_document_adherent(...)
