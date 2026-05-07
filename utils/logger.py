"""
Structured logger for Aanya Sharma Influencer System
"""
import sys
from loguru import logger
from pathlib import Path
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = Path("./logs")
LOG_DIR.mkdir(exist_ok=True)

logger.remove()

# Console — rich colors
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <white>{message}</white>",
    level=LOG_LEVEL,
    colorize=True
)

# File — full detail
logger.add(
    LOG_DIR / "aanya_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    rotation="00:00",
    retention="7 days",
    compression="zip"
)

def get_logger(name: str):
    return logger.bind(name=name)
