import uvicorn
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)


def main():
    try:
        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",
            port=9000,
            reload=False,
        )
    except KeyboardInterrupt:
        # Graceful shutdown path when user stops the server with Ctrl+C.
        logger.info("TruthLens backend stopped by user")

if __name__ == "__main__":
    main()
