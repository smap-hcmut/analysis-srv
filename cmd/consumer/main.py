from pkg.logger.logger import Logger, LoggerConfig
from config.config import load_config
import asyncio


async def main():
    # Load configuration
    try:
        app_config = load_config()
    except Exception as e:
        raise Exception(f"Error loading configuration: {e}")

    try:
        logger = Logger(
            LoggerConfig(
                level=app_config.logging.level,
                enable_console=app_config.logging.enable_console,
                colorize=app_config.logging.colorize,
                service_name=app_config.logging.service_name,
            )
        )
    except Exception as e:
        raise Exception(f"Error initializing logger: {e}")

    try:
        logger.info("Starting consumer")
    except Exception as e:
        raise Exception(f"Error starting consumer: {e}")


if __name__ == "__main__":
    asyncio.run(main())
