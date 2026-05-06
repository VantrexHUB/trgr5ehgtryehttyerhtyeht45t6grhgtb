"""
Xbox Cracker Bot Integration - Telegram command handlers for Xbox Cracker
Handles /xbox_cracker_check, /xbox_cracker_stats, /xbox_cracker_merge commands
"""

import os
import asyncio
from typing import List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
from telegram.constants import ParseMode
from concurrent.futures import ThreadPoolExecutor, as_completed

from bot_handlers import XboxCrackerManager, UniversalMerger

# States for conversation
SELECT_FILES_XBC = 1
CONFIRM_XBC = 2
SET_THREADS_XBC = 3


class XboxCrackerBotIntegration:
    """Bot integration for Xbox Cracker checking"""
    
    def __init__(self):
        self.manager = XboxCrackerManager()
        self.merger = UniversalMerger() if UniversalMerger else None
        self.user_data = {}
    
    async def cmd_xbox_cracker_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start Xbox Cracker checking"""
        args = context.args
        
        if len(args) < 1:
            await update.message.reply_text(
                "❌ Usage: `/xbox_cracker_check <combo_file> [threads]`\n\n"
                "Example: `/xbox_cracker_check combos.txt 50`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        combo_file = args[0]
        threads = int(args[1]) if len(args) > 1 else 50
        
        if not os.path.exists(combo_file):
            await update.message.reply_text(f"❌ File not found: {combo_file}")
            return
        
        await update.message.reply_text(
            f"⏳ **XBOX CRACKER - STARTING CHECK**\n\n"
            f"File: `{combo_file}`\n"
            f"Threads: {threads}\n\n"
            "_Processing combos..._",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            # Load combos
            combos = []
            with open(combo_file, 'r', encoding='utf-8') as f:
                combos = [line.strip() for line in f if ':' in line.strip()]
            
            if not combos:
                await update.message.reply_text("❌ No valid combos found in file")
                return
            
            # Start session
            session_id = self.manager.start_session()
            checked = 0
            
            # Check all combos
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = {
                    executor.submit(self.manager.check_account,
                                  email.split(':')[0],
                                  ':'.join(email.split(':')[1:])): email
                    for email in combos
                }
                
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=30)
                    except Exception:
                        pass
                    finally:
                        checked += 1
                        if checked % 100 == 0:
                            stats = self.manager.get_stats()
                            await update.message.reply_text(
                                f"⏳ Progress: {checked}/{len(combos)}\n"
                                f"💾 Total hits: {stats.get('total_hits', 0)}"
                            )
            
            # End session and get final stats
            self.manager.end_session(session_id)
            stats = self.manager.get_stats()
            
            report = self.manager.format_stats_report(stats)
            
            await update.message.reply_text(
                f"✅ **XBOX CRACKER CHECK COMPLETE**\n\n{report}",
                parse_mode=ParseMode.MARKDOWN
            )
        
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def cmd_xbox_cracker_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show Xbox Cracker statistics"""
        if not self.manager:
            await update.message.reply_text("❌ Xbox Cracker not available")
            return
        
        stats = self.manager.get_stats()
        report = self.manager.format_stats_report(stats)
        
        await update.message.reply_text(
            f"📊 {report}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def cmd_xbox_cracker_merge(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start Xbox Cracker merge and check workflow"""
        user_id = update.effective_user.id
        
        self.user_data[user_id] = {
            "files": [],
            "threads": 50
        }
        
        await update.message.reply_text(
            "📁 **XBOX CRACKER - MERGE & CHECK**\n\n"
            "Send combo files (space or comma-separated):\n"
            "  • `combo1.txt combo2.txt combo3.txt`\n"
            "  • `file1.txt, file2.txt`\n"
            "  • Or type `browse` to auto-find\n\n"
            "_Type `done` when finished_",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SELECT_FILES_XBC
    
    async def receive_files_xbc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive file list for Xbox Cracker"""
        user_id = update.effective_user.id
        user_input = update.message.text.strip()
        
        if user_input.lower() == "done":
            if not self.user_data[user_id]["files"]:
                await update.message.reply_text("❌ No files selected")
                return SELECT_FILES_XBC
            
            # Show confirmation
            files = self.user_data[user_id]["files"]
            files_text = "\n".join([f"• {os.path.basename(f)}" for f in files[:10]])
            if len(files) > 10:
                files_text += f"\n... and {len(files) - 10} more"
            
            keyboard = [
                [InlineKeyboardButton("✅ Start", callback_data="xbc_confirm")],
                [InlineKeyboardButton("❌ Cancel", callback_data="xbc_cancel")]
            ]
            
            await update.message.reply_text(
                f"📋 **{len(files)} FILES SELECTED**\n\n{files_text}\n\n"
                "Proceed with merge and check?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CONFIRM_XBC
        
        elif user_input.lower() == "browse":
            # Find combo files
            combo_files = [f for f in os.listdir(".") 
                          if f.endswith(".txt") and ("combo" in f.lower() or "hits" in f.lower())]
            
            if not combo_files:
                await update.message.reply_text("❌ No combo files found")
                return SELECT_FILES_XBC
            
            self.user_data[user_id]["files"] = combo_files
            
            files_text = "\n".join([f"• {f}" for f in combo_files[:15]])
            if len(combo_files) > 15:
                files_text += f"\n... and {len(combo_files) - 15} more"
            
            keyboard = [
                [InlineKeyboardButton("✅ Use These", callback_data="xbc_use_found")],
                [InlineKeyboardButton("❌ Manual Input", callback_data="xbc_manual")]
            ]
            
            await update.message.reply_text(
                f"📁 **FOUND {len(combo_files)} FILES**\n\n{files_text}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return SELECT_FILES_XBC
        
        else:
            # Parse files
            new_files = [f.strip() for f in user_input.replace(",", " ").split() if f.strip()]
            new_files = [f for f in new_files if os.path.exists(f)]
            
            if not new_files:
                await update.message.reply_text("❌ No valid files found")
                return SELECT_FILES_XBC
            
            self.user_data[user_id]["files"].extend(new_files)
            
            await update.message.reply_text(
                f"✅ Added {len(new_files)} file(s)\n"
                f"Total: {len(self.user_data[user_id]['files'])} files\n\n"
                "Send more or type `done`"
            )
        
        return SELECT_FILES_XBC
    
    async def handle_confirm_xbc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Xbox Cracker confirmation"""
        query = update.callback_query
        user_id = query.from_user.id
        
        await query.answer()
        
        if query.data == "xbc_cancel":
            self.user_data.pop(user_id, None)
            await query.edit_message_text("❌ Cancelled")
            return ConversationHandler.END
        
        # Set threads
        keyboard = [
            [InlineKeyboardButton("50", callback_data="xbc_threads_50")],
            [InlineKeyboardButton("100", callback_data="xbc_threads_100")],
            [InlineKeyboardButton("200", callback_data="xbc_threads_200")]
        ]
        
        await query.edit_message_text(
            "🧵 **SELECT THREADS**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return SET_THREADS_XBC
    
    async def handle_use_found_xbc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle auto-found files for Xbox Cracker"""
        query = update.callback_query
        user_id = query.from_user.id
        
        await query.answer()
        
        if query.data == "xbc_manual":
            self.user_data[user_id]["files"] = []
            await query.edit_message_text("📁 Send files manually")
            return SELECT_FILES_XBC
        
        # Show threads
        keyboard = [
            [InlineKeyboardButton("50", callback_data="xbc_threads_50")],
            [InlineKeyboardButton("100", callback_data="xbc_threads_100")],
            [InlineKeyboardButton("200", callback_data="xbc_threads_200")]
        ]
        
        await query.edit_message_text(
            "🧵 **SELECT THREADS**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return SET_THREADS_XBC
    
    async def set_threads_xbc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set thread count and start Xbox Cracker"""
        query = update.callback_query
        user_id = query.from_user.id
        
        await query.answer()
        
        thread_map = {
            "xbc_threads_50": 50,
            "xbc_threads_100": 100,
            "xbc_threads_200": 200
        }
        
        self.user_data[user_id]["threads"] = thread_map.get(query.data, 50)
        
        await query.edit_message_text("⏳ **MERGING FILES...**")
        
        # Start merge and crack
        await self.start_merge_xbox_cracker(user_id, query)
        
        return ConversationHandler.END
    
    async def start_merge_xbox_cracker(self, user_id: int, query):
        """Execute merge and crack for Xbox Cracker"""
        session = self.user_data.get(user_id, {})
        files = session.get("files", [])
        threads = session.get("threads", 50)
        
        valid_files = [f for f in files if os.path.exists(f)]
        if not valid_files:
            await query.edit_message_text("❌ Files not found")
            return
        
        try:
            # Merge files
            merge_result = self.merger.merge_files(valid_files, remove_duplicates=True)
            
            if merge_result.get("status") != "success":
                await query.edit_message_text(f"❌ Merge failed: {merge_result.get('message')}")
                return
            
            stats = merge_result.get("stats", {})
            
            # Show merge stats
            merge_text = (
                "📊 **MERGE COMPLETE**\n\n"
                f"Files: {stats.get('files_merged', 0)}\n"
                f"Total: {stats.get('final_count', 0)} combos\n"
                f"Duplicates removed: {stats.get('duplicates_removed', 0)}\n\n"
                "⏳ **STARTING XBOX CRACKER CHECK...**"
            )
            
            await query.edit_message_text(merge_text, parse_mode=ParseMode.MARKDOWN)
            
            # Crack with Xbox Cracker
            merged_file = merge_result["output_file"]
            
            # Load and check combos
            combos = []
            with open(merged_file, 'r', encoding='utf-8') as f:
                combos = [line.strip() for line in f if ':' in line.strip()]
            
            checked = 0
            
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = {
                    executor.submit(self.manager.check_account,
                                  email.split(':')[0],
                                  ':'.join(email.split(':')[1:])): email
                    for email in combos
                }
                
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=30)
                    except Exception:
                        pass
                    finally:
                        checked += 1
            
            result_stats = self.manager.get_stats()
            
            result_text = self.manager.format_stats_report(result_stats)
            
            await query.edit_message_text(
                f"✅ **XBOX CRACKER MERGE & CHECK DONE**\n\n{result_text}",
                parse_mode=ParseMode.MARKDOWN
            )
        
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)}")
        
        finally:
            self.user_data.pop(user_id, None)
    
    def get_handlers(self):
        """Get all Xbox Cracker handlers for bot"""
        return [
            CommandHandler("xbox_cracker_check", self.cmd_xbox_cracker_check),
            CommandHandler("xbox_cracker_stats", self.cmd_xbox_cracker_stats),
            ConversationHandler(
                entry_points=[CommandHandler("xbox_cracker_merge", self.cmd_xbox_cracker_merge)],
                states={
                    SELECT_FILES_XBC: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_files_xbc),
                        CallbackQueryHandler(self.handle_use_found_xbc)
                    ],
                    CONFIRM_XBC: [CallbackQueryHandler(self.handle_confirm_xbc)],
                    SET_THREADS_XBC: [CallbackQueryHandler(self.set_threads_xbc)]
                },
                fallbacks=[]
            )
        ]


def get_xbox_cracker_handlers():
    """Get Xbox Cracker bot handlers"""
    integration = XboxCrackerBotIntegration()
    return integration.get_handlers()
