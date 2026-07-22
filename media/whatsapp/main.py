"""Entry point: `python main.py` starts the WhatsApp bot."""
from __future__ import annotations

import signal
import sys
import threading

from media.whatsapp.observability.logging_setup import setup_logging, get_logger

# Initialize logging FIRST so all subsequent imports log correctly
setup_logging()
logger = get_logger("main")


def main() -> None:
    """Start the bot and handle graceful shutdown on SIGINT/SIGTERM."""
    # Lazy import so logging is set up first
    from media.whatsapp.core.bot import Bot
    from media.whatsapp.config import settings

    bot = Bot()

    def _signal_handler(sig, frame):
        logger.info(f"[Main] Received signal {sig}, shutting down...")
        bot.stop()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        bot.start()
    except KeyboardInterrupt:
        logger.info("[Main] Keyboard interrupt, shutting down...")
        bot.stop()
    except Exception as e:
        logger.error(f"[Main] Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
