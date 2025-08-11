# tools.py (Refactored for new schema)

import logging
from typing import Optional, List
from datetime import date, datetime, timedelta
from decimal import Decimal
import os
import json

# External services
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Agent logic
from livekit.agents import function_tool, RunContext
from db_driver import ExtranetDatabaseDriver, Client
# from error_logger import log_system_error # This would need refactoring too

logger = logging.getLogger("artex_agent.tools")

# --- Internal Notification Helper ---
async def _send_notification_email(subject: str, body: str) -> None:
    recipient_email = "s.bouloudn@artex-business.com"
    logger.info(f"Preparing to send notification email to {recipient_email}")
    try:
        api_key = os.getenv("SENDGRID_API_KEY")
        sender_email = os.getenv("SENDER_EMAIL")
        if not api_key or not sender_email:
            logger.error("SendGrid API key or sender email not configured.")
            return

        message = Mail(from_email=sender_email, to_emails=recipient_email, subject=subject, html_content=body.replace('\\n', '<br>'))
        sg = SendGridAPIClient(api_key)
        await sg.send(message)
        logger.info(f"Notification email sent successfully to {recipient_email}.")
    except Exception as e:
        logger.error(f"Unexpected error sending notification email: {e}", exc_info=True)

# --- Context Management Helper ---

def _handle_lookup_result(context: RunContext, result: Optional[Client] | List[Client], source: str) -> str:
    if not result:
        context.userdata["unconfirmed_client"] = None
        return "Sorry, no matching client was found with that information."

    if isinstance(result, list):
        if len(result) > 1:
            return "I found multiple matching clients. To identify you precisely, can you please provide your email address?"
        if not result:
            context.userdata["unconfirmed_client"] = None
            return "Sorry, no matching client was found."
        result = result[0]

    context.userdata["unconfirmed_client"] = result
    logger.info(f"Unconfirmed client found via {source}: {result.FirstName} {result.LastName} (ID: {result.Id})")
    
    # Simplified confirmation prompt
    return f"I found a file for {result.FirstName} {result.LastName}. Can you please confirm this is you so I can access the file securely?"

# --- Identity and Context Tools (Refactored) ---

@function_tool
async def confirm_identity(context: RunContext, confirmation: bool) -> str:
    """
    Confirms the identity of the user if they agree they are the person found.
    This tool MUST be called after a lookup tool has found a potential client.
    """
    unconfirmed: Optional[Client] = context.userdata.get("unconfirmed_client")
    if not unconfirmed:
        return "Please search for a client before confirming an identity."

    if confirmation:
        context.userdata["client_context"] = unconfirmed
        context.userdata["unconfirmed_client"] = None
        logger.info(f"Identity confirmed for: {unconfirmed.FirstName} {unconfirmed.LastName} (ID: {unconfirmed.Id})")
        return f"Thank you! Identity confirmed. The file for {unconfirmed.FirstName} {unconfirmed.LastName} is now open. How can I help you?"
    else:
        context.userdata["unconfirmed_client"] = None
        logger.warning(f"User denied identity confirmation for client ID: {unconfirmed.Id}")
        return "Okay, I will not access that file. How can I help you?"

@function_tool
async def clear_context(context: RunContext) -> str:
    """Clears the currently selected client from the assistant's context."""
    context.userdata["client_context"] = None
    context.userdata["unconfirmed_client"] = None
    return "The context has been reset. How can I help you?"

# --- Client Lookup Tools (Refactored) ---

@function_tool
async def lookup_client_by_email(context: RunContext, email: str) -> str:
    """Looks up a client using their email address to start the identification process."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    logger.info(f"Tool: lookup_client_by_email called with email: {email}")
    client = db.get_client_by_email(email.strip())
    return _handle_lookup_result(context, client, "email")

@function_tool
async def lookup_client_by_phone(context: RunContext, phone: str) -> str:
    """Looks up a client by their phone number."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    logger.info(f"Tool: lookup_client_by_phone called with phone: {phone}")
    clients = db.get_clients_by_phone(phone.strip())
    return _handle_lookup_result(context, clients, "phone")

@function_tool
async def lookup_client_by_fullname(context: RunContext, last_name: str, first_name: str) -> str:
    """Looks up a client using their full name."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    logger.info(f"Tool: lookup_client_by_fullname called with name: {first_name} {last_name}")
    clients = db.get_clients_by_fullname(last_name.strip(), first_name.strip())
    return _handle_lookup_result(context, clients, "fullname")

@function_tool
async def get_client_details(context: RunContext) -> str:
    """Gets the personal details of the currently loaded and confirmed client."""
    client: Optional[Client] = context.userdata.get("client_context")
    if not client:
        return "No client is currently selected and confirmed. Please search for and confirm a client's identity first."
    
    return (f"Details for {client.FirstName} {client.LastName} (ID: {client.Id}): "
            f"Email: {client.Email}, Phone: {client.Phone}, "
            f"Address: {client.Address}, {client.City}.")

@function_tool
async def update_contact_information(context: RunContext, address: Optional[str] = None, city: Optional[str] = None, phone: Optional[str] = None, email: Optional[str] = None) -> str:
    """Updates the contact information of the currently confirmed client."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    client: Optional[Client] = context.userdata.get("client_context")
    if not client:
        return "Action impossible. The client's identity must be confirmed before information can be modified."

    success = db.update_client_contact_info(client_id=client.Id, address=address, city=city, phone=phone, email=email)

    if success:
        # Refresh client context with new data
        updated_client = db.get_client_by_id(client.Id)
        if updated_client:
            context.userdata["client_context"] = updated_client
        return "Contact information has been successfully updated."
    else:
        return "An error occurred while updating the information, or no information was changed."

# --- Action & Communication Tools (Partially Refactored) ---

@function_tool
async def list_client_contracts(context: RunContext) -> str:
    """Lists all contracts associated with the currently confirmed client."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    client: Optional[Client] = context.userdata.get("client_context")
    if not client:
        return "Please confirm the client's identity first."

    contracts = db.get_contracts_by_client_id(client.Id)
    if not contracts:
        return f"No contracts found for {client.FirstName} {client.LastName}."
    
    response_lines = [f"Here are the contracts for {client.FirstName} {client.LastName}:"]
    for c in contracts:
        response_lines.append(f"- Contract Ref {c.Reference}, Status: {c.Status}")
    return "\\n".join(response_lines)

@function_tool
async def send_confirmation_email(context: RunContext, subject: str, body: str) -> str:
    """Sends a confirmation email to the currently identified client."""
    client: Optional[Client] = context.userdata.get("client_context")
    if not client or not client.Email:
        return "Action impossible. The client's identity must be confirmed and an email address must be on file."

    logger.info(f"Preparing to send an email via SendGrid to {client.Email}")
    try:
        api_key = os.getenv("SENDGRID_API_KEY")
        sender_email = os.getenv("SENDER_EMAIL")
        if not api_key or not sender_email:
            logger.error("SendGrid API key or sender email not configured.")
            return "Sorry, the email service is not configured correctly."
        
        full_body = f"Hello {client.FirstName} {client.LastName},<br><br>{body.replace('\\n', '<br>')}<br><br>Sincerely,<br>The Team"
        message = Mail(from_email=sender_email, to_emails=client.Email, subject=subject, html_content=full_body)
        sg = SendGridAPIClient(api_key)
        response = await sg.send(message)
        
        if 200 <= response.status_code < 300:
            logger.info(f"Email sent successfully to {client.Email}.")
            return f"A confirmation email has been sent to {client.Email}."
        else:
            logger.error(f"SendGrid API error. Status: {response.status_code}, Body: {response.body}")
            return "An error occurred while sending the email."
    except Exception as e:
        logger.error(f"Unexpected error sending email with SendGrid: {e}")
        return "Sorry, a major technical error occurred while sending the email."

@function_tool
async def schedule_callback(context: RunContext, reason: str, datetime_str: str) -> str:
    """
    Schedules a callback for the current client by creating a Google Calendar event.
    CRITICAL: The 'datetime_str' parameter MUST be a string in the exact ISO 8601 format: 'YYYY-MM-DDTHH:MM:SS'.
    You must convert any natural language date or time (e.g., 'tomorrow at 2pm') into this specific string format before calling this tool.
    Example: A request for 'December 25th, 2024 at 2:30 PM' must be converted to '2024-12-25T14:30:00'.
    """
    client: Optional[Client] = context.userdata.get("client_context")
    if not client:
        return "The client's identity must be confirmed before scheduling a callback."

    logger.info(f"Attempting to schedule a callback for client {client.Id} at {datetime_str}")

    try:
        creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID")

        if not creds_path or not calendar_id:
            logger.error("Google Calendar credentials or Calendar ID are not configured in environment variables.")
            return "The calendar service is not configured. Cannot schedule callback."

        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=['https://www.googleapis.com/auth/calendar'])
        service = build('calendar', 'v3', credentials=creds)

        start_time = datetime.fromisoformat(datetime_str)
        end_time = start_time + timedelta(minutes=30)

        event = {
            'summary': f'Callback for: {client.FirstName} {client.LastName} (ID: {client.Id})',
            'description': f'Reason: {reason}',
            'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Europe/Paris'},
            'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Europe/Paris'},
        }

        created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
        logger.info(f"Event created: {created_event.get('htmlLink')}")
        return f"I have scheduled a callback for you for {start_time.strftime('%d/%m/%Y at %H:%M')}. An advisor will call you."

    except HttpError as error:
        logger.error(f"An error occurred with Google Calendar API: {error}")
        return "An error occurred while communicating with the calendar service."
    except ValueError:
        logger.error(f"Invalid datetime format for schedule_callback: {datetime_str}")
        return "The date and time format is invalid. Please use the ISO format, e.g., '2024-12-25T14:30:00'."
    except Exception as e:
        logger.error(f"An unexpected error occurred in schedule_callback: {e}", exc_info=True)
        return "An unexpected technical error occurred while scheduling the callback."

# --- Deprecated/Removed Tools (Commented Out for Reference) ---
# The following tools depended on the old schema and have been disabled.
# They would need to be re-implemented based on the new schema if their functionality is still required.

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
