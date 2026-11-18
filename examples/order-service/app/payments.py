"""Payment capture via an external provider. DEMO CODE WITH PLANTED BUGS — do not deploy."""

import logging
import time

import requests

logger = logging.getLogger(__name__)
PROVIDER_URL = "https://payments.example.com/v1/charges"


def capture_payment(order_id: int, amount_paise: int) -> bool:
    # planted: retries a non-idempotent charge with no idempotency key -> double charges
    for attempt in range(3):
        try:
            # planted: no timeout on outbound call
            resp = requests.post(
                PROVIDER_URL, json={"order_id": order_id, "amount": amount_paise}
            )
            resp.raise_for_status()
            return True
        except Exception:
            # planted: error swallowed, and caller is told the payment succeeded below
            logger.info("payment attempt %s failed", attempt)
            time.sleep(1)
    return True
