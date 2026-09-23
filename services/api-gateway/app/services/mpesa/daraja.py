"""
Safaricom M-Pesa Daraja API v2 client.
Handles OAuth token management, STK Push (Lipa Na M-Pesa Online),
C2B registration, transaction status queries, and account balance.

Credentials stored in env vars / Vault. NEVER hardcoded.
"""

from __future__ import annotations

import base64
import os
from datetime import UTC, datetime

import httpx
from pydantic import BaseModel
from structlog import get_logger

logger = get_logger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────


class DarajaConfig(BaseModel):
    """
    M-Pesa Daraja API configuration.

    @param consumer_key: Daraja app consumer key
    @param consumer_secret: Daraja app consumer secret
    @param shortcode: Business shortcode (Paybill or Till)
    @param passkey: STK push passkey (Lipa Na M-Pesa Online)
    @param environment: "sandbox" or "production"
    @param callback_base_url: Public URL for M-Pesa callbacks
    """
    consumer_key: str
    consumer_secret: str
    shortcode: str
    passkey: str = ""
    environment: str = "sandbox"
    callback_base_url: str = ""


def get_daraja_config() -> DarajaConfig | None:
    """
    Load Daraja config from environment variables.

    @returns DarajaConfig or None if not configured
    """
    key = os.getenv("MPESA_CONSUMER_KEY")
    secret = os.getenv("MPESA_CONSUMER_SECRET")
    shortcode = os.getenv("MPESA_SHORTCODE")

    if not all([key, secret, shortcode]):
        return None

    return DarajaConfig(
        consumer_key=key,
        consumer_secret=secret,
        shortcode=shortcode,
        passkey=os.getenv("MPESA_PASSKEY", ""),
        environment=os.getenv("MPESA_ENVIRONMENT", "sandbox"),
        callback_base_url=os.getenv("MPESA_CALLBACK_URL", ""),
    )


# ── Request / Response Models ────────────────────────────────────────────────


class STKPushRequest(BaseModel):
    """
    STK Push (Lipa Na M-Pesa Online) request.

    @param phone_number: Customer phone (254XXXXXXXXX format)
    @param amount: Amount in KES (whole number)
    @param account_reference: Invoice number or patient ID
    @param description: Transaction description
    """
    phone_number: str
    amount: int
    account_reference: str
    description: str = "Aifya Hospital Payment"


class STKPushResponse(BaseModel):
    """
    STK Push API response.

    @param merchant_request_id: Safaricom merchant request ID
    @param checkout_request_id: STK push checkout request ID
    @param response_code: "0" on success
    @param response_description: Human-readable status
    @param customer_message: Message shown to customer
    """
    merchant_request_id: str = ""
    checkout_request_id: str = ""
    response_code: str = ""
    response_description: str = ""
    customer_message: str = ""
    success: bool = False
    error: str | None = None


class STKCallbackData(BaseModel):
    """
    Parsed STK Push callback data from Safaricom.

    @param merchant_request_id: Merchant request ID
    @param checkout_request_id: Checkout request ID
    @param result_code: 0 = success, else failed
    @param result_desc: Human-readable result
    @param amount: Paid amount (KES)
    @param mpesa_receipt: M-Pesa receipt number (e.g. "QH12345678")
    @param phone_number: Paying phone number
    @param transaction_date: Transaction timestamp
    """
    merchant_request_id: str
    checkout_request_id: str
    result_code: int
    result_desc: str
    amount: float | None = None
    mpesa_receipt: str | None = None
    phone_number: str | None = None
    transaction_date: str | None = None


class TransactionStatus(BaseModel):
    """
    Transaction status query result.

    @param result_code: 0 = success
    @param result_desc: Status description
    @param receipt_number: M-Pesa receipt (if completed)
    """
    result_code: int
    result_desc: str
    receipt_number: str | None = None


# ── Daraja Client ────────────────────────────────────────────────────────────


class DarajaClient:
    """
    Safaricom M-Pesa Daraja API v2 async client.
    Manages OAuth tokens and provides STK Push, C2B, and query methods.
    """

    SANDBOX_URL = "https://sandbox.safaricom.co.ke"
    PRODUCTION_URL = "https://api.safaricom.co.ke"

    def __init__(self, config: DarajaConfig) -> None:
        """
        Initialize Daraja client.

        @param config: Daraja API configuration
        """
        self.config = config
        self.base_url = (
            self.PRODUCTION_URL
            if config.environment == "production"
            else self.SANDBOX_URL
        )
        self._token: str | None = None
        self._token_expiry: datetime | None = None

    async def _get_token(self) -> str:
        """
        Get OAuth access token from Daraja. Caches until expiry.

        @returns OAuth access token string
        """
        if self._token and self._token_expiry and datetime.now(UTC) < self._token_expiry:
            return self._token

        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        credentials = base64.b64encode(
            f"{self.config.consumer_key}:{self.config.consumer_secret}".encode()
        ).decode()

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Basic {credentials}"},
            )
            response.raise_for_status()
            data = response.json()

        self._token = data["access_token"]
        # Token valid for ~3600s, refresh at 3000s
        from datetime import timedelta
        self._token_expiry = datetime.now(UTC) + timedelta(seconds=3000)
        return self._token

    def _generate_password(self) -> tuple[str, str]:
        """
        Generate STK Push password = base64(shortcode + passkey + timestamp).

        @returns Tuple of (password, timestamp)
        """
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        raw = f"{self.config.shortcode}{self.config.passkey}{timestamp}"
        password = base64.b64encode(raw.encode()).decode()
        return password, timestamp

    def _normalize_phone(self, phone: str) -> str:
        """
        Normalize Kenyan phone number to 254XXXXXXXXX format.

        @param phone: Phone number in any Kenyan format
        @returns Normalized phone number
        """
        phone = phone.strip().replace(" ", "").replace("-", "").replace("+", "")
        if phone.startswith("0"):
            phone = "254" + phone[1:]
        elif phone.startswith("7") or phone.startswith("1"):
            phone = "254" + phone
        return phone

    # ── STK Push ─────────────────────────────────────────────────────────

    async def stk_push(self, request: STKPushRequest) -> STKPushResponse:
        """
        Initiate Lipa Na M-Pesa Online (STK Push) payment.
        Sends USSD prompt to customer phone.

        @param request: STK push payment request
        @returns STK push response with checkout request ID
        """
        try:
            token = await self._get_token()
            password, timestamp = self._generate_password()
            phone = self._normalize_phone(request.phone_number)

            url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
            callback_url = f"{self.config.callback_base_url}/api/v1/mpesa/callback/stk"

            payload = {
                "BusinessShortCode": self.config.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": request.amount,
                "PartyA": phone,
                "PartyB": self.config.shortcode,
                "PhoneNumber": phone,
                "CallBackURL": callback_url,
                "AccountReference": request.account_reference[:12],
                "TransactionDesc": request.description[:13],
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                )

            data = response.json()

            if response.status_code == 200 and data.get("ResponseCode") == "0":
                return STKPushResponse(
                    merchant_request_id=data.get("MerchantRequestID", ""),
                    checkout_request_id=data.get("CheckoutRequestID", ""),
                    response_code=data.get("ResponseCode", ""),
                    response_description=data.get("ResponseDescription", ""),
                    customer_message=data.get("CustomerMessage", ""),
                    success=True,
                )
            else:
                logger.warning("stk_push_failed", data=data)
                return STKPushResponse(
                    response_code=data.get("ResponseCode", str(response.status_code)),
                    response_description=data.get("ResponseDescription", ""),
                    error=data.get("errorMessage", response.text[:200]),
                )

        except Exception as exc:
            logger.error("stk_push_error", error=str(exc))
            return STKPushResponse(error=str(exc))

    # ── STK Query ────────────────────────────────────────────────────────

    async def stk_query(self, checkout_request_id: str) -> TransactionStatus:
        """
        Query status of an STK Push transaction.

        @param checkout_request_id: Checkout request ID from STK Push response
        @returns Transaction status
        """
        try:
            token = await self._get_token()
            password, timestamp = self._generate_password()

            url = f"{self.base_url}/mpesa/stkpushquery/v1/query"
            payload = {
                "BusinessShortCode": self.config.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id,
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                )

            data = response.json()
            return TransactionStatus(
                result_code=int(data.get("ResultCode", -1)),
                result_desc=data.get("ResultDesc", "Unknown"),
                receipt_number=data.get("ReceiptNumber"),
            )

        except Exception as exc:
            logger.error("stk_query_error", error=str(exc))
            return TransactionStatus(result_code=-1, result_desc=str(exc))

    # ── C2B Registration ─────────────────────────────────────────────────

    async def register_c2b_urls(self) -> bool:
        """
        Register C2B validation and confirmation URLs with Safaricom.
        Must be called once during setup for Paybill/Till integration.

        @returns True if registration was successful
        """
        try:
            token = await self._get_token()
            url = f"{self.base_url}/mpesa/c2b/v1/registerurl"
            payload = {
                "ShortCode": self.config.shortcode,
                "ResponseType": "Completed",
                "ConfirmationURL": f"{self.config.callback_base_url}/api/v1/mpesa/callback/c2b/confirm",
                "ValidationURL": f"{self.config.callback_base_url}/api/v1/mpesa/callback/c2b/validate",
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                )

            return response.status_code == 200
        except Exception as exc:
            logger.error("c2b_register_error", error=str(exc))
            return False

    # ── Parse STK Callback ───────────────────────────────────────────────

    @staticmethod
    def parse_stk_callback(body: dict) -> STKCallbackData:
        """
        Parse Safaricom STK Push callback JSON into structured data.

        @param body: Raw callback JSON body from Safaricom
        @returns Parsed STK callback data
        """
        stk_cb = body.get("Body", {}).get("stkCallback", {})

        result = STKCallbackData(
            merchant_request_id=stk_cb.get("MerchantRequestID", ""),
            checkout_request_id=stk_cb.get("CheckoutRequestID", ""),
            result_code=stk_cb.get("ResultCode", -1),
            result_desc=stk_cb.get("ResultDesc", ""),
        )

        # Extract metadata items on success
        if result.result_code == 0:
            items = stk_cb.get("CallbackMetadata", {}).get("Item", [])
            for item in items:
                name = item.get("Name", "")
                value = item.get("Value")
                if name == "Amount":
                    result.amount = float(value)
                elif name == "MpesaReceiptNumber":
                    result.mpesa_receipt = str(value)
                elif name == "PhoneNumber":
                    result.phone_number = str(value)
                elif name == "TransactionDate":
                    result.transaction_date = str(value)

        return result
