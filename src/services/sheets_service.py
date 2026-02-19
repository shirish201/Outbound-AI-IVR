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

    Expected columns: customer_id, first_name, phone_number, age, income,
    nationality, tenure_months, transactions_last_month, spends_last_month,
    previous_products, is_cross_sale_target, prediction_score, shap_features,
    shap_values, triggerCols.
    First row is headers.
    """
    client = _get_client()
    sheet = client.open_by_url(sheet_url).sheet1
    records = sheet.get_all_records()

    contacts = []
    for i, row in enumerate(records, start=2):  # Row 2 is first data row
        phone = str(row.get("phone_number", "")).strip()
        if not phone:
            continue
        contacts.append(Contact(
            name=str(row.get("first_name", "")).strip(),
            phone=phone,
            customer_id=str(row.get("customer_id", "")).strip(),
            age=str(row.get("age", "")).strip(),
            income=str(row.get("income", "")).strip(),
            nationality=str(row.get("nationality", "")).strip(),
            tenure_months=str(row.get("tenure_months", "")).strip(),
            transactions_last_month=str(row.get("transactions_last_month", "")).strip(),
            spends_last_month=str(row.get("spends_last_month", "")).strip(),
            previous_products=str(row.get("previous_products", "")).strip(),
            is_cross_sale_target=str(row.get("is_cross_sale_target", "")).strip(),
            prediction_score=str(row.get("prediction_score", "")).strip(),
            shap_features=str(row.get("shap_features", "")).strip(),
            shap_values=str(row.get("shap_values", "")).strip(),
            trigger_cols=str(row.get("triggerCols", "")).strip(),
            row_number=i,
        ))
    logger.info("Read %d contacts from sheet", len(contacts))
    return contacts


def write_result(sheet_url: str, row_number: int, outcome: str, summary: str) -> None:
    """Write call result back to the Google Sheet.

    Appends Outcome and Summary columns after the existing headers.
    """
    client = _get_client()
    sheet = client.open_by_url(sheet_url).sheet1

    headers = sheet.row_values(1)

    # Find or create Outcome column
    if "Outcome" in headers:
        outcome_col = headers.index("Outcome") + 1
    else:
        outcome_col = len(headers) + 1
        sheet.update_cell(1, outcome_col, "Outcome")

    # Find or create Summary column
    if "Summary" in headers:
        summary_col = headers.index("Summary") + 1
    else:
        summary_col = outcome_col + 1
        sheet.update_cell(1, summary_col, "Summary")

    sheet.update_cell(row_number, outcome_col, outcome)
    sheet.update_cell(row_number, summary_col, summary)
    logger.info("Wrote result to sheet row %d: %s", row_number, outcome)
