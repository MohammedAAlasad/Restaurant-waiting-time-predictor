import asyncio
import threading

_version = 0
_lock = threading.Lock()


def notify() -> None:
    global _version
    with _lock:
        _version += 1


async def event_stream(request):
    last_seen = _version
    idle = 0.0
    yield "retry: 3000\n\n"                      
    while not await request.is_disconnected():
        await asyncio.sleep(0.5)
        idle += 0.5
        if _version != last_seen:
            last_seen, idle = _version, 0.0
            yield "event: update\ndata: change\n\n"
        elif idle >= 30:                        
            idle = 0.0
            yield "event: update\ndata: tick\n\n"