#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Key Manager - Hotmail Master Bot
Separate storage: users.json (all users) and premium_keys.json (keys & stats)
"""

import os
import json
import random
import string
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class KeyManager:
    """
    Manages users (users.json) and premium keys (premium_keys.json).
    Thread-safe JSON storage.
    """

    def __init__(self, users_file: str = "users.json", keys_file: str = "premium_keys.json"):
        self.users_file = users_file
        self.keys_file = keys_file
        self.lock = threading.RLock()
        self.users = self._load_users()
        self.keys_data = self._load_keys()
        self._migrate()

    # ------------------------------ LOAD / SAVE ------------------------------
    def _load_users(self) -> Dict:
        """Load users from users.json, create empty if missing."""
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load users: {e}")
        return {}

    def _save_users(self):
        """Save users to users.json."""
        with self.lock:
            try:
                with open(self.users_file, 'w', encoding='utf-8') as f:
                    json.dump(self.users, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Save users error: {e}")

    def _load_keys(self) -> Dict:
        """Load premium keys data from premium_keys.json, create default if missing."""
        if os.path.exists(self.keys_file):
            try:
                with open(self.keys_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if "keys" not in data:
                    data["keys"] = {}
                if "stats" not in data:
                    data["stats"] = {"total_keys": 0, "redeemed": 0, "total_checked": 0, "total_hits": 0}
                return data
            except Exception as e:
                logger.error(f"Failed to load keys: {e}")
        return {"keys": {}, "stats": {"total_keys": 0, "redeemed": 0, "total_checked": 0, "total_hits": 0}}

    def _save_keys(self):
        """Save keys data to premium_keys.json."""
        with self.lock:
            try:
                with open(self.keys_file, 'w', encoding='utf-8') as f:
                    json.dump(self.keys_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Save keys error: {e}")

    # ------------------------------ MIGRATION ------------------------------
    def _migrate(self):
        """Ensure every user has required fields, especially 'banned'."""
        for uid, user_data in self.users.items():
            changed = False
            if "banned" not in user_data:
                user_data["banned"] = False
                changed = True
            if "stats" not in user_data:
                user_data["stats"] = {"total_checked": 0, "total_hits": 0}
                changed = True
            if "daily_used" not in user_data:
                user_data["daily_used"] = 0
                changed = True
            if "daily_reset" not in user_data:
                user_data["daily_reset"] = datetime.now().date().isoformat()
                changed = True
            if "premium_until" not in user_data:
                user_data["premium_until"] = None
                changed = True
            if "redeemed_keys" not in user_data:
                user_data["redeemed_keys"] = []
                changed = True
            if "invite_count" not in user_data:
                user_data["invite_count"] = 0
                changed = True
            if "invite_code" not in user_data:
                user_data["invite_code"] = ""
                changed = True
            if "referrer_id" not in user_data:
                user_data["referrer_id"] = None
                changed = True
            if "claimed_invite_tiers" not in user_data:
                user_data["claimed_invite_tiers"] = []
                changed = True
            if "free_gift_lines" not in user_data:
                user_data["free_gift_lines"] = {"lines": 0, "expiry": None}
                changed = True
            if changed:
                self._save_users()

    # ------------------------------ USER REGISTRATION ------------------------------
    def register_user_if_new(self, user_id: int, username: str = "", first_name: str = "", last_name: str = "", invited_by: Optional[int] = None) -> bool:
        """Register a user if not already in users.json. Can set invited_by referrer."""
        uid = str(user_id)
        with self.lock:
            if uid not in self.users:
                now = datetime.now()
                self.users[uid] = {
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "joined_at": now.isoformat(),
                    "premium_until": None,
                    "daily_used": 0,
                    "daily_reset": now.date().isoformat(),
                    "stats": {"total_checked": 0, "total_hits": 0},
                    "redeemed_keys": [],
                    "banned": False,
                    "invite_count": 0,
                    "invite_code": "",
                    "referrer_id": invited_by,
                    "claimed_invite_tiers": []
                }
                
                # If invited_by set, increment referrer's invite count
                if invited_by:
                    ref_uid = str(invited_by)
                    if ref_uid in self.users:
                        self.users[ref_uid]["invite_count"] = self.users[ref_uid].get("invite_count", 0) + 1
                
                self._save_users()
                return True
            else:
                # Update username if changed
                if username and self.users[uid].get("username") != username:
                    self.users[uid]["username"] = username
                    self._save_users()
                return False

    # ------------------------------ PREMIUM STATUS ------------------------------
    def is_premium(self, user_id: int) -> bool:
        uid = str(user_id)
        user = self.users.get(uid)
        if not user or not user.get("premium_until"):
            return False
        try:
            expiry = datetime.fromisoformat(user["premium_until"])
            return expiry > datetime.now()
        except:
            return False

    def get_premium_expiry(self, user_id: int) -> Optional[datetime]:
        uid = str(user_id)
        user = self.users.get(uid)
        if user and user.get("premium_until"):
            try:
                return datetime.fromisoformat(user["premium_until"])
            except:
                pass
        return None

    def add_premium_manual(self, user_id: int, days: float):
        with self.lock:
            uid = str(user_id)
            if uid not in self.users:
                self.register_user_if_new(user_id)
            user = self.users[uid]
            now = datetime.now()
            if user["premium_until"]:
                current = datetime.fromisoformat(user["premium_until"])
                if current > now:
                    new_expiry = current + timedelta(days=days)
                else:
                    new_expiry = now + timedelta(days=days)
            else:
                new_expiry = now + timedelta(days=days)
            user["premium_until"] = new_expiry.isoformat()
            self._save_users()

    # ------------------------------ DAILY USAGE ------------------------------
    def get_daily_used(self, user_id: int) -> int:
        uid = str(user_id)
        user = self.users.get(uid)
        if not user:
            return 0
        today = datetime.now().date().isoformat()
        if user.get("daily_reset") != today:
            return 0
        return user.get("daily_used", 0)

    def add_daily_used(self, user_id: int, lines: int) -> bool:
        uid = str(user_id)
        with self.lock:
            today = datetime.now().date().isoformat()
            if uid not in self.users:
                self.register_user_if_new(user_id)
            user = self.users[uid]
            if user.get("daily_reset") != today:
                user["daily_used"] =0
                user["daily_reset"] = today
            if not self.is_premium(user_id):
                limit = 10000
                if user["daily_used"] + lines > limit:
                    return False
            user["daily_used"] += lines
            self._save_users()
            return True
    
    def add_daily_used_with_free_lines(self, user_id: int, lines: int) -> Tuple[bool, int, int]:
        """
        Consume lines using free gift lines first, then daily used.
        Returns (success, lines_from_free, lines_from_daily)
        """
        uid = str(user_id)
        with self.lock:
            if uid not in self.users:
                self.register_user_if_new(user_id)
            
            user = self.users[uid]
            
            # First, try to use free gift lines
            free_available = self.get_free_lines_available(user_id)
            lines_from_free = min(lines, free_available)
            remaining_lines = lines - lines_from_free
            
            # Consume from free lines if any
            if lines_from_free > 0:
                user["free_gift_lines"]["lines"] -= lines_from_free
                if user["free_gift_lines"]["lines"] <= 0:
                    user["free_gift_lines"] = {"lines": 0, "expiry": None}
            
            # Then consume from daily limit
            lines_from_daily = remaining_lines
            if lines_from_daily > 0:
                today = datetime.now().date().isoformat()
                if user.get("daily_reset") != today:
                    user["daily_used"] = 0
                    user["daily_reset"] = today
                
                if not self.is_premium(user_id):
                    limit = 10000
                    if user["daily_used"] + lines_from_daily > limit:
                        user["daily_used"] += lines_from_daily
                        self._save_users()
                        return False, lines_from_free, min(lines_from_daily, limit - user["daily_used"] + lines_from_daily)
                
                user["daily_used"] += lines_from_daily
            
            self._save_users()
            return True, lines_from_free, lines_from_daily

    # ------------------------------ STATISTICS ------------------------------
    def update_user_stats(self, user_id: int, checked: int, hits: int):
        uid = str(user_id)
        with self.lock:
            if uid not in self.users:
                self.register_user_if_new(user_id)
            stats = self.users[uid]["stats"]
            stats["total_checked"] += checked
            stats["total_hits"] += hits
            self.keys_data["stats"]["total_checked"] += checked
            self.keys_data["stats"]["total_hits"] += hits
            self._save_users()
            self._save_keys()

    def get_user_stats(self, user_id: int) -> Dict[str, int]:
        uid = str(user_id)
        user = self.users.get(uid, {})
        return user.get("stats", {"total_checked": 0, "total_hits": 0})

    def get_global_stats(self) -> Dict[str, int]:
        return self.keys_data["stats"]

    def get_all_users(self) -> Dict[str, Any]:
        return self.users

    def get_leaderboard(self, limit: int = 100) -> List[Tuple[str, Dict[str, Any], int]]:
        """
        Get leaderboard sorted by total_hits
        Returns: List of (user_id, user_data, total_hits) tuples sorted by hits DESC
        """
        leaderboard = []
        with self.lock:
            for uid_str, user_data in self.users.items():
                try:
                    stats = user_data.get("stats", {})
                    total_hits = stats.get("total_hits", 0)
                    if total_hits > 0:  # Only include users with hits
                        leaderboard.append((uid_str, user_data, total_hits))
                except Exception as e:
                    logger.error(f"Error processing user {uid_str}: {e}")
                    continue
        
        # Sort by total_hits descending
        leaderboard.sort(key=lambda x: x[2], reverse=True)
        return leaderboard[:limit]

    # ------------------------------ BAN / UNBAN (FIXED) ------------------------------
    def is_banned(self, user_id: int) -> bool:
        """Check if user is banned."""
        uid = str(user_id)
        user = self.users.get(uid)
        if not user:
            return False
        return user.get("banned", False)

    def ban_user(self, user_id: int) -> bool:
        """Ban a user. Returns True if successful."""
        uid = str(user_id)
        with self.lock:
            if uid in self.users:
                self.users[uid]["banned"] = True
                self._save_users()
                logger.info(f"User {user_id} has been banned.")
                return True
            else:
                logger.warning(f"User {user_id} not found in users.json, cannot ban.")
                return False

    def unban_user(self, user_id: int) -> bool:
        """Unban a user. Returns True if successful."""
        uid = str(user_id)
        with self.lock:
            if uid in self.users:
                self.users[uid]["banned"] = False
                self._save_users()
                logger.info(f"User {user_id} has been unbanned.")
                return True
            else:
                logger.warning(f"User {user_id} not found in users.json, cannot unban.")
                return False

    # ------------------------------ KEY MANAGEMENT ------------------------------
    def generate_key(self, days: float, prefix: str = "HMB") -> str:
        with self.lock:
            while True:
                random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=20))
                key = f"{prefix}-{random_part}"
                if key not in self.keys_data["keys"]:
                    break
            expiry = datetime.now() + timedelta(days=days)
            self.keys_data["keys"][key] = {
                "expiry": expiry.isoformat(),
                "duration_days": days,
                "redeemed_by": None,
                "redeemed_at": None,
                "generated_at": datetime.now().isoformat(),
                "created_by": "admin"
            }
            self.keys_data["stats"]["total_keys"] += 1
            self._save_keys()
            return key

    def redeem_key(self, user_id: int, key: str) -> Tuple[bool, str]:
        with self.lock:
            key = key.strip().upper()
            if key not in self.keys_data["keys"]:
                return False, "Invalid key! Key not found."
            info = self.keys_data["keys"][key]
            if info.get("redeemed_by") is not None:
                if info["redeemed_by"] == user_id:
                    return False, "You have already redeemed this key!"
                return False, "Key already used by another user."
            expiry = datetime.fromisoformat(info["expiry"])
            if expiry < datetime.now():
                return False, "Key expired!"
            uid = str(user_id)
            if uid not in self.users:
                self.register_user_if_new(user_id)
            user = self.users[uid]
            # Extend premium
            new_expiry = expiry
            if user.get("premium_until"):
                current = datetime.fromisoformat(user["premium_until"])
                if current > datetime.now():
                    new_expiry = current + timedelta(days=info["duration_days"])
            user["premium_until"] = new_expiry.isoformat()
            user["redeemed_keys"].append(key)
            info["redeemed_by"] = user_id
            info["redeemed_at"] = datetime.now().isoformat()
            self.keys_data["stats"]["redeemed"] += 1
            self._save_users()
            self._save_keys()
            return True, f"Premium activated until {new_expiry.strftime('%Y-%m-%d %H:%M:%S')}"

    def delete_key(self, key: str) -> bool:
        with self.lock:
            if key in self.keys_data["keys"]:
                del self.keys_data["keys"][key]
                self.keys_data["stats"]["total_keys"] -= 1
                self._save_keys()
                return True
            return False

    def delete_all_keys(self) -> int:
        with self.lock:
            count = len(self.keys_data["keys"])
            self.keys_data["keys"] = {}
            self.keys_data["stats"]["total_keys"] = 0
            self.keys_data["stats"]["redeemed"] = 0
            self._save_keys()
            return count

    def list_all_keys(self, include_redeemed: bool = True) -> List[Dict]:
        keys = []
        for k, v in self.keys_data["keys"].items():
            if not include_redeemed and v.get("redeemed_by"):
                continue
            keys.append({
                "key": k,
                "expiry": v["expiry"],
                "duration_days": v["duration_days"],
                "redeemed_by": v.get("redeemed_by"),
                "redeemed_at": v.get("redeemed_at"),
                "generated_at": v.get("generated_at")
            })
        return keys

    def get_redeemed_keys(self) -> List[Dict]:
        """Get all redeemed keys with user information"""
        redeemed = []
        for k, v in self.keys_data["keys"].items():
            if v.get("redeemed_by"):
                redeemed_by = v.get("redeemed_by")
                user = self.users.get(str(redeemed_by), {})
                redeemed.append({
                    "key": k,
                    "user_id": redeemed_by,
                    "username": user.get("username", "Unknown"),
                    "redeemed_at": v.get("redeemed_at"),
                    "expiry": v.get("expiry"),
                    "duration_days": v.get("duration_days")
                })
        return redeemed

    def delete_redeemed_key(self, key: str) -> Tuple[bool, str]:
        """Delete a redeemed key and revoke the user's premium access"""
        with self.lock:
            if key not in self.keys_data["keys"]:
                return False, "Key not found"
            
            key_info = self.keys_data["keys"][key]
            redeemed_by = key_info.get("redeemed_by")
            
            if not redeemed_by:
                return False, "This key was not redeemed"
            
            # Get user and revoke premium
            uid = str(redeemed_by)
            if uid in self.users:
                user = self.users[uid]
                
                # Remove the key from user's redeemed_keys list
                if "redeemed_keys" in user and key in user["redeemed_keys"]:
                    user["redeemed_keys"].remove(key)
                
                # Revoke premium access
                user["premium_until"] = None
                
                self._save_users()
            
            # Delete the key
            del self.keys_data["keys"][key]
            self.keys_data["stats"]["total_keys"] -= 1
            if self.keys_data["stats"].get("redeemed", 0) > 0:
                self.keys_data["stats"]["redeemed"] -= 1
            
            self._save_keys()
            return True, f"Key deleted and premium revoked from user {redeemed_by}"

    def get_unused_keys(self) -> List[Dict]:
        """Get all keys that have NOT been redeemed"""
        unused = []
        with self.lock:
            for key_str, key_data in self.keys_data["keys"].items():
                if key_data.get("redeemed_by") is None:
                    unused.append({
                        "key": key_str,
                        "expiry": key_data.get("expiry", "Unknown"),
                        "duration_days": key_data.get("duration_days", 0),
                        "created_at": key_data.get("generated_at", "Unknown")
                    })
        # Sort by creation date (newest first)
        unused.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return unused

    def delete_all_unused_keys(self) -> int:
        """Delete all unused (unredeemed) keys. Returns count of deleted keys"""
        with self.lock:
            deleted_count = 0
            keys_to_delete = []
            
            for key_str, key_data in self.keys_data["keys"].items():
                if key_data.get("redeemed_by") is None:
                    keys_to_delete.append(key_str)
            
            # Delete the unused keys
            for key_str in keys_to_delete:
                del self.keys_data["keys"][key_str]
                deleted_count += 1
            
            # Update stats
            self.keys_data["stats"]["total_keys"] = len(self.keys_data["keys"])
            self._save_keys()
            
            logger.info(f"Deleted {deleted_count} unused keys")
            return deleted_count

    def get_stats(self) -> Dict[str, Any]:
        premium_count = 0
        for uid, user in self.users.items():
            if self.is_premium(int(uid)):
                premium_count += 1
        return {
            "total_users": len(self.users),
            "current_premium_users": premium_count,
            "total_keys": self.keys_data["stats"].get("total_keys", 0),
            "redeemed": self.keys_data["stats"].get("redeemed", 0)
        }

    # ------------------------------ INVITE SYSTEM ------------------------------
    def get_invite_stats(self, user_id: int) -> Dict[str, Any]:
        """Get invite stats for a user"""
        uid = str(user_id)
        user = self.users.get(uid, {})
        invite_count = user.get("invite_count", 0)
        claimed_tiers = user.get("claimed_invite_tiers", [])
        
        return {
            "invite_count": invite_count,
            "claimed_tiers": claimed_tiers,
            "referrer_id": user.get("referrer_id"),
            "invite_code": user.get("invite_code", "")
        }

    def set_referrer(self, user_id: int, referrer_id: int) -> bool:
        """Set referrer for a new user"""
        uid = str(user_id)
        ref_uid = str(referrer_id)
        
        with self.lock:
            # Register user if new
            if uid not in self.users:
                self.register_user_if_new(user_id)
            
            user = self.users[uid]
            
            # Don't allow changing referrer
            if user.get("referrer_id"):
                return False
            
            user["referrer_id"] = referrer_id
            
            # Increment referrer's invite count
            if ref_uid in self.users:
                if "invite_count" not in self.users[ref_uid]:
                    self.users[ref_uid]["invite_count"] = 0
                self.users[ref_uid]["invite_count"] += 1
                self._save_users()
                return True
            
            return False

    def generate_invite_code(self, user_id: int) -> str:
        """Generate unique invite code for user"""
        uid = str(user_id)
        
        with self.lock:
            if uid not in self.users:
                self.register_user_if_new(user_id)
            
            user = self.users[uid]
            
            # Return existing code if exists
            if user.get("invite_code"):
                return user["invite_code"]
            
            # Generate new code
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            user["invite_code"] = code
            self._save_users()
            return code

    def claim_invite_reward(self, user_id: int, tier: int) -> Tuple[bool, str, Optional[str]]:
        """Claim invite reward at specific tier. Returns (success, message, generated_key)"""
        uid = str(user_id)
        user = self.users.get(uid)
        
        if not user:
            return False, "User not found", None
        
        invite_count = user.get("invite_count", 0)
        claimed_tiers = user.get("claimed_invite_tiers", [])
        
        # Define reward tiers
        tiers = {
            1: {"invites": 5, "days": 1, "label": "5 Invites"},
            2: {"invites": 10, "days": 3, "label": "10 Invites"},
            3: {"invites": 25, "days": 7, "label": "25 Invites"},
            4: {"invites": 50, "days": 30, "label": "50 Invites (1/50 slots)"}
        }
        
        if tier not in tiers:
            return False, "Invalid tier", None
        
        if tier in claimed_tiers:
            return False, "Reward already claimed", None
        
        tier_info = tiers[tier]
        if invite_count < tier_info["invites"]:
            return False, f"Need {tier_info['invites']} invites, you have {invite_count}", None
        
        # For 50 invites tier, check if slot is available
        if tier == 4:
            # Count how many have claimed this tier
            month_key_limit = 50
            claimed_month_keys = 0
            for u in self.users.values():
                if 4 in u.get("claimed_invite_tiers", []):
                    claimed_month_keys += 1
            
            if claimed_month_keys >= month_key_limit:
                return False, f"Monthly reward slot is full ({claimed_month_keys}/{month_key_limit})", None
        
        # Generate key
        key = self.generate_key(tier_info["days"])
        
        # Mark tier as claimed
        with self.lock:
            user["claimed_invite_tiers"].append(tier)
            self._save_users()
        
        return True, f"Reward claimed! {tier} days key generated", key
    
    def get_user_by_invite_code(self, invite_code: str) -> Optional[int]:
        """Find user ID by their invite code"""
        for uid_str, user_data in self.users.items():
            if user_data.get("invite_code") == invite_code:
                return int(uid_str)
        return None
    
    def get_user_invite_code(self, user_id: int) -> str:
        """Get user's invite code"""
        uid = str(user_id)
        user = self.users.get(uid, {})
        return user.get("invite_code", "")
    
    def get_invite_count(self, user_id: int) -> int:
        """Get user's invite count"""
        uid = str(user_id)
        user = self.users.get(uid, {})
        return user.get("invite_count", 0)
    
    def get_invite_rewards_claimed(self, user_id: int) -> List[int]:
        """Get list of claimed reward tiers"""
        uid = str(user_id)
        user = self.users.get(uid, {})
        return user.get("claimed_invite_tiers", [])
    
    def _increment_invite_count(self, user_id: int) -> int:
        """Increment invite count for user"""
        uid = str(user_id)
        with self.lock:
            if uid not in self.users:
                self.register_user_if_new(user_id)
            self.users[uid]["invite_count"] = self.users[uid].get("invite_count", 0) + 1
            self._save_users()
            return self.users[uid]["invite_count"]
    
    def _generate_unique_code(self) -> str:
        """Generate unique invite code"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            # Check if code already exists
            if not any(u.get("invite_code") == code for u in self.users.values()):
                return code

    # ------------------------------ FREE GIFT LINES SYSTEM ------------------------------
    def give_free_lines_to_all_users(self, lines: int, days: int) -> int:
        """Give free lines to all users. Returns count of users updated."""
        with self.lock:
            expiry = datetime.now() + timedelta(days=days)
            expiry_iso = expiry.isoformat()
            updated_count = 0
            
            for uid, user_data in self.users.items():
                user_data["free_gift_lines"] = {
                    "lines": lines,
                    "expiry": expiry_iso
                }
                updated_count += 1
            
            self._save_users()
            logger.info(f"Gave {lines} free lines to {updated_count} users, expiry: {expiry_iso}")
            return updated_count

    def get_free_lines_available(self, user_id: int) -> int:
        """Get available free gift lines. Returns 0 if expired or none available."""
        uid = str(user_id)
        user = self.users.get(uid)
        
        if not user:
            return 0
        
        gift_data = user.get("free_gift_lines", {"lines": 0, "expiry": None})
        if not gift_data.get("expiry"):
            return 0
        
        try:
            expiry = datetime.fromisoformat(gift_data["expiry"])
            if expiry > datetime.now():
                return gift_data.get("lines", 0)
        except:
            pass
        
        return 0

    def consume_free_lines(self, user_id: int, lines: int) -> int:
        """Consume free lines for a user. Returns actual lines consumed."""
        with self.lock:
            uid = str(user_id)
            user = self.users.get(uid)
            
            if not user:
                return 0
            
            gift_data = user.get("free_gift_lines", {"lines": 0, "expiry": None})
            available = self.get_free_lines_available(user_id)
            
            lines_to_consume = min(lines, available)
            
            if lines_to_consume > 0:
                user["free_gift_lines"]["lines"] -= lines_to_consume
                if user["free_gift_lines"]["lines"] <= 0:
                    user["free_gift_lines"] = {"lines": 0, "expiry": None}
                self._save_users()
            
            return lines_to_consume