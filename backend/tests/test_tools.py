import pytest
import asyncio
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from db_driver import ClientEventHistory
from tools import (
    confirm_identity,
    clear_context,
    lookup_client_by_email,
    get_client_details,
    list_client_contracts,
    get_contract_details,
    get_client_interaction_history,
    check_upcoming_appointments,
    find_employee_for_escalation,
    get_contract_company_info,
    get_contract_formula_details,
    summarize_advisory_duty,
    send_confirmation_email
)
from tests.mocks import MockExtranetDatabaseDriver

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_context():
    """Fixture to create a mock RunContext for tools."""
    context = MagicMock()
    context.userdata = {
        "db_driver": MockExtranetDatabaseDriver(),
        "client_context": None,
        "unconfirmed_client": None,
    }
    return context

async def test_lookup_client_by_email_found(mock_context):
    """Test that lookup_client_by_email finds a client and sets them as unconfirmed."""
    email = "jean.dupont@email.com"
    result = await lookup_client_by_email(mock_context, email=email)

    assert "J'ai trouvé un dossier pour Jean Dupont" in result
    assert mock_context.userdata["unconfirmed_client"] is not None
    assert mock_context.userdata["unconfirmed_client"].Id == 1

async def test_lookup_client_by_email_not_found(mock_context):
    """Test that lookup_client_by_email handles not finding a client."""
    email = "nonexistent@email.com"
    result = await lookup_client_by_email(mock_context, email=email)

    assert "aucun client correspondant" in result
    assert mock_context.userdata["unconfirmed_client"] is None

async def test_confirm_identity_success(mock_context):
    """Test successful identity confirmation without proactive message."""
    await lookup_client_by_email(mock_context, email="jean.dupont@email.com")
    assert mock_context.userdata["unconfirmed_client"] is not None

    result = await confirm_identity(mock_context, confirmation=True)

    assert "Identité confirmée" in result
    assert "rendez-vous à venir" not in result # Ensure no proactive message
    assert mock_context.userdata["client_context"] is not None
    assert mock_context.userdata["unconfirmed_client"] is None

async def test_confirm_identity_success_and_proactive_check(mock_context):
    """Test successful identity confirmation and proactive appointment check."""
    # Add an upcoming appointment to the mock data
    mock_context.userdata["db_driver"].history.setdefault(1, []).append(
        ClientEventHistory(Id=1002, ClientId=1, Comment="Rappel pour discuter du contrat", ForDate=datetime.now() + timedelta(days=1), IsCompleted=False)
    )

    await lookup_client_by_email(mock_context, email="jean.dupont@email.com")
    assert mock_context.userdata["unconfirmed_client"] is not None

    result = await confirm_identity(mock_context, confirmation=True)

    assert "Identité confirmée" in result
    assert "je vois que vous avez des rendez-vous à venir" in result # Check for proactive message
    assert mock_context.userdata["client_context"] is not None
    assert mock_context.userdata["unconfirmed_client"] is None

async def test_confirm_identity_denied(mock_context):
    """Test denied identity confirmation."""
    await lookup_client_by_email(mock_context, email="jean.dupont@email.com")

    result = await confirm_identity(mock_context, confirmation=False)

    assert "n'accéderai pas à ce dossier" in result
    assert mock_context.userdata["client_context"] is None
    assert mock_context.userdata["unconfirmed_client"] is None

async def test_get_client_details_with_confirmed_client(mock_context):
    """Test getting details for a confirmed client."""
    # Confirm identity first
    await lookup_client_by_email(mock_context, email="jean.dupont@email.com")
    await confirm_identity(mock_context, confirmation=True)

    result = await get_client_details(mock_context)

    assert "Détails pour Jean Dupont" in result
    assert "jean.dupont@email.com" in result

async def test_get_client_details_without_confirmed_client(mock_context):
    """Test that get_client_details fails without a confirmed client."""
    result = await get_client_details(mock_context)
    assert "Aucun client n'est actuellement sélectionné" in result

async def test_clear_context(mock_context):
    """Test that clear_context resets the client context."""
    # Set some context first
    await lookup_client_by_email(mock_context, email="jean.dupont@email.com")
    await confirm_identity(mock_context, confirmation=True)
    assert mock_context.userdata["client_context"] is not None

    result = await clear_context(mock_context)

    assert "contexte a été réinitialisé" in result
    assert mock_context.userdata["client_context"] is None
    assert mock_context.userdata["unconfirmed_client"] is None

async def test_list_client_contracts_found(mock_context):
    """Test listing contracts for a confirmed client."""
    await lookup_client_by_email(mock_context, email="jean.dupont@email.com")
    await confirm_identity(mock_context, confirmation=True)

    result = await list_client_contracts(mock_context)
    assert "Voici les contrats pour Jean Dupont" in result
    assert "CONTRAT-A" in result

async def test_get_contract_details_found(mock_context):
    """Test getting details for a specific contract."""
    await lookup_client_by_email(mock_context, email="jean.dupont@email.com")
    await confirm_identity(mock_context, confirmation=True)

    result = await get_contract_details(mock_context, contract_reference="CONTRAT-A")
    assert "Détails du contrat CONTRAT-A" in result
    assert "Actif" in result

async def test_get_client_interaction_history_found(mock_context):
    """Test retrieving client interaction history."""
    await lookup_client_by_email(mock_context, email="jean.dupont@email.com")
    await confirm_identity(mock_context, confirmation=True)

    result = await get_client_interaction_history(mock_context)
    assert "Voici un résumé des dernières interactions" in result
    assert "Premier contact" in result

async def test_find_employee_for_escalation_found(mock_context):
    """Test finding an employee for escalation."""
    # This tool does not require client confirmation
    result = await find_employee_for_escalation(mock_context, function="Support")
    assert "J'ai trouvé Alice Martin (Support)" in result

async def test_get_contract_company_info_found(mock_context):
    """Test getting company info for a contract."""
    await lookup_client_by_email(mock_context, email="jean.dupont@email.com")
    await confirm_identity(mock_context, confirmation=True)

    result = await get_contract_company_info(mock_context, contract_reference="CONTRAT-A")
    assert "géré par Assurance Alpha" in result

async def test_get_contract_formula_details_found(mock_context):
    """Test getting formula details for a contract."""
    await lookup_client_by_email(mock_context, email="jean.dupont@email.com")
    await confirm_identity(mock_context, confirmation=True)

    result = await get_contract_formula_details(mock_context, contract_reference="CONTRAT-A")
    assert "basé sur la formule 'Formule Essentielle'" in result

async def test_summarize_advisory_duty_found(mock_context):
    """Test summarizing the advisory duty document."""
    await lookup_client_by_email(mock_context, email="jean.dupont@email.com")
    await confirm_identity(mock_context, confirmation=True)

    result = await summarize_advisory_duty(mock_context)
    assert "Pour vous rassurer sur le choix de votre contrat" in result
    assert "Soins dentaires" in result

async def test_send_confirmation_email_failure(mock_context, monkeypatch):
    """Test the fallback mechanism when sending an email fails."""
    # Set environment variables for the test
    monkeypatch.setenv("SENDGRID_API_KEY", "test_key")
    monkeypatch.setenv("SENDER_EMAIL", "test@sender.com")

    # Confirm identity
    await lookup_client_by_email(mock_context, email="jean.dupont@email.com")
    # Use the simple confirmation to avoid proactive message interference
    await confirm_identity(mock_context, confirmation=True)

    # Mock the SendGridAPIClient to raise an exception
    async def mock_send(*args, **kwargs):
        raise Exception("Simulated SendGrid API failure")

    monkeypatch.setattr("sendgrid.SendGridAPIClient.send", mock_send)

    result = await send_confirmation_email(mock_context, subject="Test", body="Test")

    assert "erreur technique majeure" in result
    assert "planifie un rappel" in result
