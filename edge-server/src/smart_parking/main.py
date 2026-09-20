"""Main entry point for Edge Server."""
import logging
from smart_parking.bootstrap import bootstrap_system

def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("smart_parking")
    logger.info("Starting Smart Parking Edge Server...")
    app_context = bootstrap_system()
    logger.info("System initialized successfully.")

if __name__ == "__main__":
    main()