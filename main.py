#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hotmail Checker Pro
Version: 1.0
Author: @vantrexXxx
Description: Advanced Hotmail/Outlook Multi-Tool Telegram Bot
"""

import os
import sys
import logging
import atexit
import signal
import asyncio
from datetime import datetime
from typing import List, Tuple

# Suppress SSL warnings early
import warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Configure logging before imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Suppress urllib3 warnings
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("requests").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)  # Suppress httpx spam
logging.getLogger("telegram").setLevel(logging.WARNING)  # Suppress telegram debug logs

# Configuration Constants
class Config:
    """Bot Configuration"""
    # Bot Token (Get from @BotFather)
    BOT_TOKEN = "7697030798:AAHiTipLyZu7HCjJnCFu5CEgAHYaqP64ha4"
    
    # Admin User IDs (Telegram User IDs)
    ADMIN_IDS: List[int] = [
        8664147577,  # Replace with your actual Telegram ID
    ]
    
    # Required Channels (Users must join these)
    # Format: (invite_url, channel_username)
    # Simply use the @username from the channel (without numeric IDs)
    REQUIRED_CHANNELS: List[Tuple[str, str]] = [
        ("https://t.me/HmVaultBest", "HmVaultBest"),           # HmVaultBest channel
        ("https://t.me/HotmailCrackerv7", "HotmailCrackerv7"),  # HotmailCrackerv7 channel
    ]
    
    # ⚡ FORCE CHANNEL MEMBERSHIP: Users MUST join all channels to use bot
    # If they leave any channel, bot will ask them to rejoin
    # Set to True to REQUIRE channel membership before using bot
    FORCE_CHANNEL_MEMBERSHIP: bool = True  # Channels are REQUIRED
    
    # ==================== RESULTS CHANNEL ====================
    # Channel where ALL cracking hits will be posted automatically
    RESULTS_CHANNEL: tuple = ("https://t.me/+Jh8AvykONMg2YTU8", -1003739339282)
    RESULTS_CHANNEL_ENABLED: bool = False  # Set to True to enable auto-posting
    
    # Bot Settings
    PREMIUM_DAILY_LIMIT: int = 10000
    MAX_THREADS: int = 30
    MAX_FILE_SIZE: int = 20 * 1024 * 1024  # 20MB
    MAX_LINES: int = 10000
    
    # File Paths
    PREMIUM_DB_FILE: str = "premium_db.json"
    RESULTS_FOLDER: str = "results"
    TEMP_FOLDER: str = "temp"
    
    # Scanner Settings
    REQUEST_TIMEOUT: int = 15
    MAX_RETRIES: int = 3
    REQUEST_DELAY: float = 0.2

# Ensure directories exist
def setup_directories():
    """Create necessary directories"""
    for folder in [Config.RESULTS_FOLDER, Config.TEMP_FOLDER, "logs"]:
        if not os.path.exists(folder):
            os.makedirs(folder)
            logger.info(f"Created directory: {folder}")

# PID File Management
PID_FILE = "bot.pid"

def cleanup_pid():
    """Remove PID file on exit"""
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
            logger.info("PID file cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning PID file: {e}")

def check_running():
    """Check if another instance is running"""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            # Check if process exists
            os.kill(old_pid, 0)
            logger.error(f"Another instance is running (PID: {old_pid})")
            sys.exit(1)
        except (OSError, ValueError):
            # Process not running, stale PID file
            os.remove(PID_FILE)
            logger.warning("Removed stale PID file")
    
    # Write current PID
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))
    atexit.register(cleanup_pid)

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down...")
    cleanup_pid()
    sys.exit(0)

def validate_config():
    """Validate configuration settings"""
    if not Config.BOT_TOKEN or Config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ BOT_TOKEN not configured! Please set your bot token in main.py")
        return False
    
    if not Config.ADMIN_IDS or Config.ADMIN_IDS == [123456789]:
        logger.warning("⚠️ ADMIN_IDS not properly configured!")
    
    if len(Config.BOT_TOKEN) < 20:
        logger.error("❌ BOT_TOKEN appears to be invalid (too short)")
        return False
    
    logger.info("[OK] Configuration validated successfully")
    return True

def print_banner():
    """Print startup banner"""
    banner = """
    ======================================================
    
    Hotmail Checker Pro 
    
    Version 1.0 - REAL CHECK
    Author: @vantrexXxx
    
    ======================================================
    """
    print(banner)
    logger.info("Starting Hotmail Checker PRO")

def main():
    """Main entry point"""
    try:
        print_banner()
        setup_directories()
        
        if not validate_config():
            sys.exit(1)
        
        check_running()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Import and start bot
        from bot_handlers import HotmailMasterBot
        
        logger.info("Initializing bot components...")
        bot = HotmailMasterBot(
            token=Config.BOT_TOKEN,
            admin_ids=Config.ADMIN_IDS,
            channels=Config.REQUIRED_CHANNELS
        )
        
        logger.info("[RUNNING] Bot is now running! Press Ctrl+C to stop.")
        bot.run()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error in main: {e}")
        sys.exit(1)
    finally:
        cleanup_pid()

if __name__ == "__main__":
    main()