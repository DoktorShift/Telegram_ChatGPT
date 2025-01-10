import requests
from config import LNBITS_ADMIN_KEY, LNBITS_DOMAIN

def create_invoice(amount: int, memo: str) -> dict:
    """Create an invoice using LNBits API."""
    url = f"{LNBITS_DOMAIN}/api/v1/payments"
    headers = {"X-Api-Key": LNBITS_ADMIN_KEY, "Content-Type": "application/json"}
    data = {"out": False, "amount": amount, "memo": memo}
    response = requests.post(url, json=data, headers=headers)
    return response.json()

def check_payment(payment_hash: str) -> bool:
    """Check invoice payment status using LNBits API."""
    url = f"{LNBITS_DOMAIN}/api/v1/payments/{payment_hash}"
    headers = {"X-Api-Key": LNBITS_ADMIN_KEY}
    response = requests.get(url, headers=headers)
    data = response.json()
    return data.get("paid", False)
