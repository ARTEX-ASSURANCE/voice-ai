from typing import Optional, List, Dict, Any
from db_driver import Client, Contract, ClientEventHistory, Employee, Company, Formula, AdvisoryDuty
from decimal import Decimal
from datetime import date, datetime

class MockExtranetDatabaseDriver:
    """A mock version of the ExtranetDatabaseDriver for testing purposes."""

    def __init__(self):
        self.clients = {
            1: Client(Id=1, FirstName="Jean", LastName="Dupont", Email="jean.dupont@email.com", Phone="1234567890"),
            2: Client(Id=2, FirstName="Marie", LastName="Durand", Email="marie.durand@email.com", Phone="0987654321")
        }
        self.contracts = {
            1: [Contract(Id=101, ClientId=1, Reference="CONTRAT-A", Status="Actif", CompanyId=1, FormulaId=1)],
            2: [Contract(Id=102, ClientId=2, Reference="CONTRAT-B", Status="Actif", CompanyId=2, FormulaId=2)]
        }
        self.history = {
            1: [ClientEventHistory(Id=1001, ClientId=1, Comment="Premier contact", ForDate=datetime(2023, 1, 15))]
        }
        self.employees = {
            "1": Employee(Id="1", FirstName="Alice", LastName="Martin", Function="Support", IsActive=True)
        }
        self.companies = {
            1: Company(Id=1, Name="Assurance Alpha", PhoneNumber="111-222-3333"),
            2: Company(Id=2, Name="Garantie Gamma", PhoneNumber="444-555-6666")
        }
        self.formulas = {
            1: Formula(Id=1, Name="Formule Essentielle", Description="Couverture de base.", Price=Decimal("29.99")),
            2: Formula(Id=2, Name="Formule Pro", Description="Couverture complète pour les professionnels.", Price=Decimal("79.99"))
        }
        self.advisory_duties = {
            1: AdvisoryDuty(Id=1, ClientId=1, ClientSituation="Recherche une assurance santé.", Budget="50€/mois", Need1="Soins dentaires")
        }


    def get_client_by_id(self, client_id: int) -> Optional[Client]:
        return self.clients.get(client_id)

    def get_client_by_email(self, email: str) -> Optional[Client]:
        for client in self.clients.values():
            if client.Email == email:
                return client
        return None

    def get_clients_by_phone(self, phone: str) -> List[Client]:
        return [client for client in self.clients.values() if client.Phone == phone or client.Mobile == phone]

    def get_clients_by_fullname(self, last_name: str, first_name: str) -> List[Client]:
        return [client for client in self.clients.values() if client.FirstName == first_name and client.LastName == last_name]

    def update_client_contact_info(self, client_id: int, **kwargs) -> bool:
        if client_id in self.clients:
            return True
        return False

    def get_contracts_by_client_id(self, client_id: int) -> List[Contract]:
        return self.contracts.get(client_id, [])

    def get_contract_by_ref(self, reference: str) -> Optional[Contract]:
        for contract_list in self.contracts.values():
            for contract in contract_list:
                if contract.Reference == reference:
                    return contract
        return None

    def get_client_history(self, client_id: int) -> List[ClientEventHistory]:
        return self.history.get(client_id, [])

    def get_upcoming_appointments(self, client_id: int) -> List[ClientEventHistory]:
        # For testing, we can return a mix of completed and upcoming
        return [event for event in self.history.get(client_id, []) if not event.IsCompleted]

    def find_active_employee(self, name: Optional[str] = None, function: Optional[str] = None) -> List[Employee]:
        return list(self.employees.values())

    def get_company_by_id(self, company_id: int) -> Optional[Company]:
        return self.companies.get(company_id)

    def get_formula_by_id(self, formula_id: int) -> Optional[Formula]:
        return self.formulas.get(formula_id)

    def get_advisory_duty(self, client_id: int) -> Optional[AdvisoryDuty]:
        return self.advisory_duties.get(client_id)
