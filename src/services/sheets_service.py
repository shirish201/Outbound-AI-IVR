import logging
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from config.settings import settings
from src.core.models import Contact

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

_client: Optional[gspread.Client] = None


def _get_client() -> gspread.Client:
    global _client
    if _client is None:
        creds = Credentials.from_service_account_file(
            settings.google_sheets_credentials_file, scopes=SCOPES
        )
        _client = gspread.authorize(creds)
    return _client


def read_contacts(sheet_url: str) -> list[Contact]:
    """Read contacts from a Google Sheet.

    Expected columns: Name, Phone, Email, Company, Notes
    First row is headers.
    """
    client = _get_client()
    sheet = client.open_by_url(sheet_url).sheet1
    records = sheet.get_all_records()

    contacts = []
    for i, row in enumerate(records, start=2):  # Row 2 is first data row
        name = str(row.get("Name", "")).strip()
        phone = str(row.get("Phone", "")).strip()
        if not phone:
            continue
        contacts.append(Contact(
            name=name,
            phone=phone,
            email=str(row.get("Email", "")).strip(),
            company=str(row.get("Company", "")).strip(),
            notes=str(row.get("Notes", "")).strip(),
            row_number=i,
        ))
    logger.info("Read %d contacts from sheet", len(contacts))
    return contacts


def write_result(sheet_url: str, row_number: int, outcome: str, summary: str) -> None:
    """Write call result back to the Google Sheet.

    Writes to columns F (Outcome) and G (Summary).
    """
    client = _get_client()
    sheet = client.open_by_url(sheet_url).sheet1

    # Update header if needed
    headers = sheet.row_values(1)
    if len(headers) < 6 or headers[5] != "Outcome":
        sheet.update_cell(1, 6, "Outcome")
    if len(headers) < 7 or headers[6] != "Summary":
        sheet.update_cell(1, 7, "Summary")

    sheet.update_cell(row_number, 6, outcome)
    sheet.update_cell(row_number, 7, summary)
    logger.info("Wrote result to sheet row %d: %s", row_number, outcome)
