"""
payment_provider.py — Payment gateway abstraction for the Ekhaya FC Fan Hub.

Membership must ONLY be activated after the backend has verified a payment as
SUCCESSFUL — never on the fan's word. Each provider implements:

    create_payment(amount, phone, email, reference, description)
        -> initiates a payment, returns a dict with a provider transaction id

    verify_payment(provider_txn_id)
        -> queries the gateway for the real transaction status
        -> returns {"status": "SUCCESSFUL"|"PENDING"|"FAILED", "txn_id": ...}

Providers read their credentials from site_settings / environment so they can
be configured at runtime without hard-coding. To go live, an admin sets the
active provider and its credentials via the admin settings page.
"""

import uuid

from membership_db import get_setting


def _money(amount):
    """Amount in MWK, rounded to 2 dp for consistency across providers."""
    return round(float(amount), 2)


def list_providers():
    """Providers available to the system (id -> display name)."""
    return {
        "sandbox": "Sandbox / Test Gateway",
        "paychangu": "PayChangu (Airtel Money, TNM Mpamba & cards)",
    }


def get_active_provider():
    """The configured active provider id (from database settings)."""
    return get_setting("active_payment_provider", "sandbox")


class PaymentProviderError(Exception):
    """Raised for any provider-level failure (network, credentials, etc.)."""


class BaseProvider:
    id = "base"
    name = "Base"

    def create_payment(self, amount, phone=None, email=None,
                       reference=None, description=None):
        raise NotImplementedError

    def verify_payment(self, txn_id):
        raise NotImplementedError


class SandboxProvider(BaseProvider):
    """A clearly-labelled development/test gateway.

    Used to exercise the full flow (initiate -> verify -> activate) with no
    external credentials. Verification still runs through the backend, and
    membership only activates on a SUCCESSFUL verified status — same rules as
    a live gateway.
    """

    id = "sandbox"
    name = "Sandbox / Test Gateway"

    def create_payment(self, amount, phone=None, email=None,
                       reference=None, description=None):
        # Simulates the gateway returning a transaction id. In "fail" mode we
        # still return a txn id; verification decides the outcome.
        return {
            "txn_id": "SANDBOX-%s" % uuid.uuid4().hex[:12].upper(),
            "reference": reference,
            "amount": _money(amount),
            "status": "created",
        }

    def verify_payment(self, txn_id):
        # Test knob: an admin can set sandbox_auto_success=0 to test failures.
        if get_setting("sandbox_auto_success", "1") != "1":
            return {"status": "FAILED", "txn_id": txn_id,
                    "message": "Sandbox forced failure"}
        return {"status": "SUCCESSFUL", "txn_id": txn_id,
                "message": "Sandbox payment verified as successful"}


class PayChanguProvider(BaseProvider):
    """Adapter for the PayChangu Malawi aggregator.

    Supports Airtel Money, TNM Mpamba, mobile money and cards. Requires a live
    merchant token (paid onboarding). Configuration is read from site_settings
    so it can be enabled later without code changes:
        paychangu_token     - merchant bearer token
        paychangu_base_url  - default https://api.paychangu.com
    """

    id = "paychangu"
    name = "PayChangu"

    def _base_url(self):
        return get_setting("paychangu_base_url", "https://api.paychangu.com")

    def _token(self):
        return get_setting("paychangu_token", "")

    def _headers(self):
        return {
            "Authorization": "Bearer %s" % self._token(),
            "Content-Type": "application/json",
        }

    def create_payment(self, amount, phone=None, email=None,
                       reference=None, description=None):
        import requests, json

        token = self._token()
        if not token:
            raise PaymentProviderError(
                "PayChangu is not configured. Set a paychangu_token in "
                "admin settings before enabling this gateway.")

        payload = {
            "amount": _money(amount),
            "phone": phone,
            "email": email,
            "currency": "MWK",
            "reference": reference,
            "description": description or "Ekhaya FC membership",
            "callback_url": get_setting(
                "paychangu_callback_url",
                "https://your-app.example/payment/webhook/paychangu"),
            "return_url": get_setting(
                "paychangu_return_url", "https://your-app.example/fan/payments"),
        }
        resp = requests.post(
            self._base_url() + "/v1/payments/initialize",
            json=payload, headers=self._headers(), timeout=30)
        data = resp.json() if resp.headers.get("content-type", "").startswith(
            "application/json") else {}
        if not resp.ok:
            raise PaymentProviderError("PayChangu init failed: %s"
                                       % (data.get("message") or resp.text))
        info = data.get("paymentInfo") or data.get("data") or {}
        return {"txn_id": info.get("transactionId") or info.get("chargeId"),
                "reference": reference,
                "amount": _money(amount),
                "status": (info.get("status") or "pending").lower()}

    def verify_payment(self, txn_id):
        import requests
        resp = requests.get(
            self._base_url() + "/v1/payment/" + txn_id,
            headers=self._headers(), timeout=30)
        data = resp.json() if resp.headers.get("content-type", "").startswith(
            "application/json") else {}
        status = (data.get("paymentInfo") or data.get("data") or {}).get(
            "status", "")
        status = (status or "").lower()
        mapped = {"successful": "SUCCESSFUL", "completed": "SUCCESSFUL",
                  "paid": "SUCCESSFUL", "pending": "PENDING", "initiated": "PENDING",
                  "failed": "FAILED", "cancelled": "FAILED"}.get(status, "PENDING")
        return {"status": mapped, "txn_id": txn_id}


def get_provider(provider_id=None):
    """Return the configured provider instance."""
    provider_id = provider_id or get_active_provider()
    if provider_id == "paychangu":
        return PayChanguProvider()
    return SandboxProvider()


# ---------------------------------------------------------------------------
# High-level helpers used by the app
# ---------------------------------------------------------------------------
def initiate_payment(fan_id, membership_id, package, amount, phone, email,
                     reference):
    """Create a DB payment row and initiate with the active provider.

    Returns (payment_id, provider_txn_id, provider). Raises on init failure.
    """
    from membership_db import create_payment

    provider = get_provider()
    provider_id = provider.id
    payment_id = create_payment(fan_id, membership_id, package["id"], amount,
                                provider_id, reference)
    created = provider.create_payment(
        amount=amount, phone=phone, email=email, reference=reference,
        description="Ekhaya FC %s membership" % package["name"])
    txn_id = created.get("txn_id")
    from membership_db import set_payment_status
    if txn_id:
        set_payment_status(payment_id, "PENDING", provider_txn_id=txn_id)
    return payment_id, txn_id, provider_id


def _verify_status(payment):
    """Query the gateway for a payment's real status.

    Updates the payment row to the verified status and returns
    (status, error_message). status is one of 'SUCCESSFUL', 'PENDING',
    'FAILED', or 'ERROR'.
    """
    from membership_db import set_payment_status

    if payment["status"] == "SUCCESSFUL":
        return "SUCCESSFUL", None

    provider = get_provider(payment["provider"] or get_active_provider())
    try:
        result = provider.verify_payment(payment["provider_txn_id"])
    except Exception as exc:  # noqa: BLE001
        return "ERROR", "Verification error: %s" % exc

    status = result.get("status", "PENDING")
    set_payment_status(payment["id"], status,
                       provider_txn_id=result.get("txn_id")
                       or payment["provider_txn_id"])
    return status, None


def verify_and_activate(payment_id):
    """Query the provider for the real status and, only on SUCCESSFUL,
    activate the membership and generate the card.

    Returns a dict describing the outcome. This is the single trusted point
    that authorises membership activation.
    """
    from membership_db import (get_payment, set_payment_status,
                               get_package, get_memberships_for_fan,
                               activate_membership, create_card,
                               add_notification, get_fan_by_id)
    import uuid
    from datetime import datetime, timedelta
    from database import get_connection

    payment = get_payment(payment_id)
    if payment is None:
        return {"ok": False, "message": "Payment not found"}

    if payment["status"] == "SUCCESSFUL":
        return {"ok": True, "payment": payment, "already": True}

    status, verr = _verify_status(payment)
    if verr:
        return {"ok": False, "message": verr}
    if status != "SUCCESSFUL":
        return {"ok": False, "message": "Payment is %s" % status.lower(),
                "payment": payment}

    # ---- Payment verified: activate membership and issue a card ----
    membership_id = payment["membership_id"]
    package_id = payment["package_id"]
    package = get_package(package_id) if package_id else None
    fan_id = payment["fan_id"]
    fan = get_fan_by_id(fan_id)

    # Expire any other ACTIVE memberships this fan holds, then activate this one.
    conn = get_connection()
    conn.execute("UPDATE fan_memberships SET status='EXPIRED' "
                 "WHERE fan_id=? AND status='ACTIVE'", (fan_id,))
    conn.commit()
    conn.close()

    if membership_id:
        activate_membership(membership_id)
        mrows = get_memberships_for_fan(fan_id)
        m = next((r for r in mrows if r["id"] == membership_id), None)
    else:
        m = None

    # (Re)generate the digital card.
    from membership_db import create_card as _create_card
    card_number = payment["reference"]
    qr_secret = "QR-%s" % uuid.uuid4().hex[:20].upper()
    expiry = None
    if package:
        duration = int(package["duration_days"] or 365)
        base = datetime.utcnow()
        expiry = (base + timedelta(days=duration)).strftime("%Y-%m-%d")
        # Keep stored membership expiry in sync with the package duration.
        start = base.strftime("%Y-%m-%d")
        conn = get_connection()
        conn.execute("UPDATE fan_memberships SET start_date=?, expiry_date=? "
                     "WHERE id=?", (start, expiry, membership_id))
        conn.commit()
        conn.close()
    _create_card(fan_id, membership_id, card_number, qr_secret)

    if membership_id and package:
        package_label = package["name"]
    else:
        package_label = "FAN"
    add_notification(fan_id, "Membership Activated",
                     "Your Ekhaya FC %s membership is now ACTIVE. Your digital "
                     "membership card has been issued." % package_label)

    return {"ok": True, "payment": payment, "membership": m,
            "package": package, "expiry": expiry, "card_number": card_number,
            "qr_secret": qr_secret}


def verify_and_issue_tickets(payment_id):
    """Ticket path: on a verified SUCCESSFUL payment, confirm the booking and
    issue the e-tickets (one QR-scannable ticket per seat)."""
    from membership_db import (get_payment, get_booking, get_tickets_for_booking,
                               set_booking_status, create_tickets_for_booking,
                               get_fan_by_id, add_notification)

    payment = get_payment(payment_id)
    if payment is None:
        return {"ok": False, "message": "Payment not found"}
    payment = dict(payment)
    if (payment.get("item_type") or "membership") != "ticket":
        return {"ok": False, "message": "Not a ticket payment"}

    if payment["status"] == "SUCCESSFUL":
        tickets = get_tickets_for_booking(payment["booking_id"])
        return {"ok": True, "payment": payment, "already": True,
                "tickets": tickets}

    status, verr = _verify_status(payment)
    if verr:
        return {"ok": False, "message": verr}
    if status != "SUCCESSFUL":
        return {"ok": False, "message": "Payment is %s" % status.lower(),
                "payment": payment}

    booking = get_booking(payment["booking_id"]) if payment["booking_id"] else None
    if not booking:
        return {"ok": False, "message": "Booking not found"}

    set_booking_status(booking["id"], "SUCCESSFUL")
    tickets = create_tickets_for_booking(booking)

    opponent = (booking["away_team"] if booking["home_team"] == "Ekhaya FC"
                else booking["home_team"]) or "?"
    add_notification(booking["fan_id"], "Matchday Tickets Issued",
                     "Your %d ticket(s) for Ekhaya FC vs %s on %s are ready "
                     "in the Tickets section." % (booking["qty"], opponent,
                                                  booking["match_date"]))

    return {"ok": True, "payment": payment, "booking": booking,
            "tickets": tickets}


def verify_and_fulfil(payment_id):
    """Single entry point for admin/cron verification — dispatch by item type.

    Membership payments activate the membership + card; ticket payments mark
    the booking paid and issue the e-tickets. Nothing is authorised until the
    gateway returns SUCCESSFUL.
    """
    from membership_db import get_payment

    payment = get_payment(payment_id)
    if payment is None:
        return {"ok": False, "message": "Payment not found"}
    payment = dict(payment)
    if (payment.get("item_type") or "membership") == "ticket":
        return verify_and_issue_tickets(payment_id)
    return verify_and_activate(payment_id)
