"""Event publishing. DEMO CODE WITH PLANTED BUGS — do not deploy."""

import json
import queue

# planted: unbounded in-memory queue — events are lost on restart and memory grows without limit
_outbox: "queue.Queue[str]" = queue.Queue()


def publish(event_type: str, payload: dict) -> None:
    _outbox.put(json.dumps({"type": event_type, **payload}))
