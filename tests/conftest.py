"""pytest configuration."""

try:
    import uvloop  # type: ignore
except ImportError:
    uvloop = None

if uvloop:
    import asyncio
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
