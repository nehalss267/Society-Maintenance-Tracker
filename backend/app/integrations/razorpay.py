import hashlib
import hmac
import logging
import uuid

from app.core.config import settings

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    """True when real Razorpay credentials are present."""
    return bool(
        settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET
    )


def get_public_key() -> str:
    return settings.RAZORPAY_KEY_ID


def create_order(amount: float, receipt: str) -> dict:
    """Create a Razorpay order. Returns provider order payload."""
    import razorpay

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    order = client.order.create(
        {
            "amount": int(amount * 100),  # paise
            "currency": "INR",
            "receipt": receipt,
        }
    )

    return {
        "order_id": order["id"],
        "amount": order["amount"] / 100,
        "currency": order["currency"],
    }


def verify_payment_signature(
    *,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> bool:
    """HMAC-SHA256 verification of checkout callback (server-side only)."""
    if not is_configured():
        return False

    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, razorpay_signature)


def verify_webhook_signature(body: bytes, signature: str | None) -> bool:
    """HMAC-SHA256 verification of the X-Razorpay-Signature webhook header."""
    if not signature or not settings.RAZORPAY_WEBHOOK_SECRET:
        return False

    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Simulated flow (no credentials) - deterministic, clearly-marked fake IDs so
# the full payment lifecycle can run end-to-end without a Razorpay account.
# ---------------------------------------------------------------------------


def simulated_order(amount: float, receipt: str) -> dict:
    return {
        "order_id": f"order_sim_{uuid.uuid4().hex[:14]}",
        "amount": amount,
        "currency": "INR",
    }


def is_simulated_order(order_id: str) -> bool:
    return order_id.startswith("order_sim_")
