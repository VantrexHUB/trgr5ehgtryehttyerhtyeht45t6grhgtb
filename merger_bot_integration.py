"""
Bot Integration for File Merger & Combined Cracker System
Telegram commands for merging multiple files and starting checks
"""

import os
import asyncio
from typing import List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram.constants import ParseMode

from bot_handlers import MergerManager

# States for conversation
SELECT_ENGINE = 1
SELECT_FILES = 2
CONFIRM_MERGE = 3
SET_THREADS = 4


class MergerBotIntegration:
    """Bot integration for file merger system"""
    
    def __init__(self):
        self.manager = MergerManager() if MergerManager else None
        self.user_sessions = {}  # Track user file selections
    
    async def cmd_merge_files(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start merge and crack workflow"""
        if not self.manager:
            await update.message.reply_text("❌ Merger system not available")
            return
        
        user_id = update.effective_user.id
        self.user_sessions[user_id] = {
            "files": [],
            "engine": None,
            "threads": 50
        }
        
        # Show engine selection
        keyboard = [
            [InlineKeyboardButton("🎮 Supercell", callback_data="merge_supercell")],
            [InlineKeyboardButton("🎮 Xbox Game Pass", callback_data="merge_xbox")],
            [InlineKeyboardButton("🔀 Both Engines", callback_data="merge_both")],
            [InlineKeyboardButton("📁 Just Merge (No Crack)", callback_data="merge_only")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔀 **FILE MERGER & CRACKER**\n\n"
            "Select engine for checking:\n"
            "_Or choose 'Just Merge' to only consolidate files_",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SELECT_ENGINE
    
    async def select_engine(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle engine selection"""
        query = update.callback_query
        user_id = query.from_user.id
        
        await query.answer()
        
        if user_id not in self.user_sessions:
            await query.edit_message_text("❌ Session expired")
            return
        
        engine_map = {
            "merge_supercell": "supercell",
            "merge_xbox": "xbox",
            "merge_both": "both",
            "merge_only": "none"
        }
        
        self.user_sessions[user_id]["engine"] = engine_map.get(query.data, "none")
        
        await query.edit_message_text(
            "📁 **SELECT FILES TO MERGE**\n\n"
            "Send combo files (one at a time or comma-separated filenames):\n"
            "Examples:\n"
            "  • `combo1.txt combo2.txt combo3.txt`\n"
            "  • `file1.txt, file2.txt`\n"
            "  • Browse - to auto-find combo files\n\n"
            "_Send 'done' when finished_",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SELECT_FILES
    
    async def receive_files(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive file list from user"""
        user_id = update.effective_user.id
        user_input = update.message.text.strip()
        
        if not user_input:
            return SELECT_FILES
        
        if user_input.lower() == "done":
            if not self.user_sessions[user_id]["files"]:
                await update.message.reply_text("❌ No files selected. Please send files first.")
                return SELECT_FILES
            
            # Show confirmation
            files = self.user_sessions[user_id]["files"]
            engine = self.user_sessions[user_id]["engine"]
            
            keyboard = [
                [InlineKeyboardButton("✅ Confirm & Start", callback_data="confirm_merge")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_merge")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            files_text = "\n".join([f"• {os.path.basename(f)}" for f in files[:10]])
            if len(files) > 10:
                files_text += f"\n... and {len(files) - 10} more"
            
            engine_name = {
                "supercell": "🎮 Supercell",
                "xbox": "🎮 Xbox Game Pass",
                "both": "🔀 Both Engines",
                "none": "📁 Just Merge"
            }.get(engine, "Unknown")
            
            await update.message.reply_text(
                f"📋 **CONFIRMATION**\n\n"
                f"Files ({len(files)}):\n{files_text}\n\n"
                f"Engine: {engine_name}\n"
                f"Threads: {self.user_sessions[user_id]['threads']}\n\n"
                "Ready to start?",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
            return CONFIRM_MERGE
        
        elif user_input.lower() == "browse":
            # Auto-find combo files
            combo_files = [f for f in os.listdir(".") 
                          if f.endswith(".txt") and ("combo" in f.lower() or "hits" in f.lower())]
            
            if not combo_files:
                await update.message.reply_text("❌ No combo files found in current directory")
                return SELECT_FILES
            
            self.user_sessions[user_id]["files"] = combo_files
            
            keyboard = [
                [InlineKeyboardButton("✅ Use Found Files", callback_data="use_found_files")],
                [InlineKeyboardButton("❌ Enter Manually", callback_data="enter_manually")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            files_text = "\n".join([f"• {f}" for f in combo_files[:15]])
            if len(combo_files) > 15:
                files_text += f"\n... and {len(combo_files) - 15} more"
            
            await update.message.reply_text(
                f"📁 **FOUND {len(combo_files)} COMBO FILE(S)**\n\n{files_text}",
                reply_markup=reply_markup
            )
            
            return SELECT_FILES
        
        else:
            # Parse file list
            new_files = [f.strip() for f in user_input.split() if f.strip()]
            new_files = [f for f in new_files if os.path.exists(f)]
            
            if not new_files:
                await update.message.reply_text("❌ No valid files found. Try again or type 'browse'")
                return SELECT_FILES
            
            self.user_sessions[user_id]["files"].extend(new_files)
            
            await update.message.reply_text(
                f"✅ Added {len(new_files)} file(s)\n"
                f"📊 Total: {len(self.user_sessions[user_id]['files'])} files\n\n"
                "Send more files or type 'done' to proceed"
            )
        
        return SELECT_FILES
    
    async def handle_auto_files(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle auto-found files confirmation"""
        query = update.callback_query
        user_id = query.from_user.id
        
        await query.answer()
        
        if query.data == "enter_manually":
            self.user_sessions[user_id]["files"] = []
            await query.edit_message_text(
                "📁 Send combo files manually:\n"
                "_Type 'done' when finished_"
            )
            return SELECT_FILES
        
        # Show thread selection
        keyboard = [
            [InlineKeyboardButton("50 threads", callback_data="threads_50")],
            [InlineKeyboardButton("100 threads", callback_data="threads_100")],
            [InlineKeyboardButton("200 threads", callback_data="threads_200")],
            [InlineKeyboardButton("Custom", callback_data="threads_custom")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🧵 **SELECT THREAD COUNT**",
            reply_markup=reply_markup
        )
        
        return SET_THREADS
    
    async def set_threads(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set thread count"""
        query = update.callback_query
        user_id = query.from_user.id
        
        await query.answer()
        
        if query.data == "threads_custom":
            await query.edit_message_text("🧵 Enter thread count (1-500):")
            context.user_data["waiting_for_threads"] = True
            return SET_THREADS
        
        thread_map = {
            "threads_50": 50,
            "threads_100": 100,
            "threads_200": 200
        }
        
        self.user_sessions[user_id]["threads"] = thread_map.get(query.data, 50)
        
        # Start merging
        await self.start_merge(user_id, query)
        return ConversationHandler.END
    
    async def receive_custom_threads(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive custom thread count"""
        if context.user_data.get("waiting_for_threads"):
            user_id = update.effective_user.id
            try:
                threads = int(update.message.text.strip())
                if 1 <= threads <= 500:
                    self.user_sessions[user_id]["threads"] = threads
                    # Start merge
                    await update.message.reply_text(
                        "⏳ Starting merge and crack...",
                        reply_markup=None
                    )
                    await self.start_merge_from_message(user_id, update)
                    return ConversationHandler.END
                else:
                    await update.message.reply_text("❌ Enter value between 1-500")
                    return SET_THREADS
            except ValueError:
                await update.message.reply_text("❌ Invalid number. Try again")
                return SET_THREADS
    
    async def confirm_merge(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle merge confirmation"""
        query = update.callback_query
        user_id = query.from_user.id
        
        await query.answer()
        
        if query.data == "cancel_merge":
            self.user_sessions.pop(user_id, None)
            await query.edit_message_text("❌ Cancelled")
            return ConversationHandler.END
        
        # Show thread selection
        keyboard = [
            [InlineKeyboardButton("50 threads", callback_data="threads_50")],
            [InlineKeyboardButton("100 threads", callback_data="threads_100")],
            [InlineKeyboardButton("200 threads", callback_data="threads_200")],
            [InlineKeyboardButton("Custom", callback_data="threads_custom")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🧵 **SELECT THREAD COUNT**",
            reply_markup=reply_markup
        )
        
        return SET_THREADS
    
    async def start_merge(self, user_id: int, query: CallbackQuery):
        """Start merging and cracking"""
        session = self.user_sessions.get(user_id, {})
        files = session.get("files", [])
        engine = session.get("engine", "none")
        threads = session.get("threads", 50)
        
        if not files:
            await query.edit_message_text("❌ No files selected")
            return
        
        # Verify files exist
        valid_files = [f for f in files if os.path.exists(f)]
        if not valid_files:
            await query.edit_message_text("❌ Files not found")
            return
        
        await query.edit_message_text(
            "⏳ **MERGING FILES...**\n\n"
            f"📁 Files: {len(valid_files)}\n"
            f"🧵 Threads: {threads}\n\n"
            "_This may take a few minutes..._"
        )
        
        try:
            # Merge files
            merge_result = self.manager.merge_files(valid_files)
            
            if merge_result.get("status") != "success":
                await query.edit_message_text(
                    f"❌ Merge failed: {merge_result.get('message', 'Unknown error')}"
                )
                return
            
            # Show merge stats
            merge_stats_text = self.manager.format_merge_stats(merge_result)
            
            if engine == "none":
                await query.edit_message_text(merge_stats_text, parse_mode=ParseMode.MARKDOWN)
            else:
                await query.edit_message_text(
                    f"{merge_stats_text}\n\n"
                    "⏳ **STARTING CHECK...**",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Run cracker
                merged_file = merge_result["output_file"]
                
                if engine == "supercell":
                    result = await asyncio.to_thread(
                        self.manager.merge_and_crack_supercell,
                        [merged_file],
                        threads
                    )
                elif engine == "xbox":
                    result = await asyncio.to_thread(
                        self.manager.merge_and_crack_xbox,
                        [merged_file],
                        threads
                    )
                
                stats = result.get("statistics", {})
                engine_name = "Supercell" if engine == "supercell" else "Xbox"
                
                await query.edit_message_text(
                    f"✅ **{engine_name.upper()} CHECK COMPLETED**\n\n"
                    f"📊 Checked: {result.get('total_checked', 0)}\n"
                    f"🎯 Total Hits: {stats.get('total_hits', 0)}\n"
                    f"✅ Valid: {stats.get('valid_accounts', 0)}\n"
                    f"❌ Bad: {stats.get('bad_accounts', 0)}\n"
                    f"⚠️  Errors: {stats.get('errors', 0)}",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)}")
        
        self.user_sessions.pop(user_id, None)
    
    async def start_merge_from_message(self, user_id: int, update):
        """Start merge from message update"""
        session = self.user_sessions.get(user_id, {})
        files = session.get("files", [])
        engine = session.get("engine", "none")
        threads = session.get("threads", 50)
        
        # Verify files exist
        valid_files = [f for f in files if os.path.exists(f)]
        if not valid_files:
            await update.message.reply_text("❌ Files not found")
            return
        
        try:
            # Merge files
            merge_result = self.manager.merge_files(valid_files)
            
            if merge_result.get("status") != "success":
                await update.message.reply_text(
                    f"❌ Merge failed: {merge_result.get('message', 'Unknown error')}"
                )
                return
            
            # Show merge stats
            merge_stats_text = self.manager.format_merge_stats(merge_result)
            
            if engine == "none":
                await update.message.reply_text(merge_stats_text, parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text(
                    f"{merge_stats_text}\n\n"
                    "⏳ **STARTING CHECK...**",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Run cracker
                merged_file = merge_result["output_file"]
                
                if engine == "supercell":
                    result = await asyncio.to_thread(
                        self.manager.merge_and_crack_supercell,
                        [merged_file],
                        threads
                    )
                elif engine == "xbox":
                    result = await asyncio.to_thread(
                        self.manager.merge_and_crack_xbox,
                        [merged_file],
                        threads
                    )
                
                stats = result.get("statistics", {})
                engine_name = "Supercell" if engine == "supercell" else "Xbox"
                
                await update.message.reply_text(
                    f"✅ **{engine_name.upper()} CHECK COMPLETED**\n\n"
                    f"📊 Checked: {result.get('total_checked', 0)}\n"
                    f"🎯 Total Hits: {stats.get('total_hits', 0)}\n"
                    f"✅ Valid: {stats.get('valid_accounts', 0)}\n"
                    f"❌ Bad: {stats.get('bad_accounts', 0)}\n"
                    f"⚠️  Errors: {stats.get('errors', 0)}",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
        
        self.user_sessions.pop(user_id, None)
    
    def get_merger_handlers(self):
        """Get list of handlers for application"""
        return [
            ConversationHandler(
                entry_points=[CommandHandler("merge", self.cmd_merge_files)],
                states={
                    SELECT_ENGINE: [CallbackQueryHandler(self.select_engine)],
                    SELECT_FILES: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_files),
                        CallbackQueryHandler(self.handle_auto_files)
                    ],
                    CONFIRM_MERGE: [CallbackQueryHandler(self.confirm_merge)],
                    SET_THREADS: [
                        CallbackQueryHandler(self.set_threads),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_custom_threads)
                    ]
                },
                fallbacks=[]
            )
        ]


def get_merger_handlers():
    """Get merger bot handlers for main bot"""
    integration = MergerBotIntegration()
    return integration.get_merger_handlers()
