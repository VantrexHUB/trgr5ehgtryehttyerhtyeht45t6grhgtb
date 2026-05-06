#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LUXURY MARKETPLACE SYSTEM v2.0
Premium combos, logs, ULPs with VIP tiers, flash sales, bundles & more
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from threading import Lock
import random

logger = logging.getLogger(__name__)


class LuxuryMarketplaceInventory:
    """Premium marketplace with VIP tiers, flash sales, bundles & luxury features"""
    
    def __init__(self, inventory_file: str = "marketplace_inventory.json"):
        self.inventory_file = inventory_file
        self.lock = Lock()
        self.MIN_COMBO_PURCHASE = 1000
        
        # VIP Tier benefits
        self.VIP_TIERS = {
            "bronze": {"discount": 0.05, "emoji": "🥉", "min_spend": 50},
            "silver": {"discount": 0.10, "emoji": "🥈", "min_spend": 250},
            "gold": {"discount": 0.15, "emoji": "🥇", "min_spend": 1000},
            "platinum": {"discount": 0.25, "emoji": "💎", "min_spend": 5000},
        }
        
        # Flash sale window (in hours)
        self.FLASH_SALE_DURATION = 24
        
        self.load_inventory()
    
    def load_inventory(self):
        """Load inventory from JSON file"""
        if os.path.exists(self.inventory_file):
            try:
                with open(self.inventory_file, 'r') as f:
                    self.data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load inventory: {e}")
                self.data = self._default_inventory()
        else:
            self.data = self._default_inventory()
            self.save_inventory()
    
    def _default_inventory(self) -> Dict:
        """Premium inventory with quality ratings, trends, limited editions"""
        return {
            "combos": {
                # ===== PREMIUM STREAMING =====
                "netflix": {
                    "stock": 0,
                    "price_per_1k": 10.00,
                    "quality_rating": 4.9,
                    "trending": True,
                    "limited_edition": False,
                    "description": "Premium Netflix Accounts",
                    "category": "Streaming Services",
                    "icon": "🎬"
                },
                "spotify": {
                    "stock": 0,
                    "price_per_1k": 8.50,
                    "quality_rating": 4.8,
                    "trending": True,
                    "limited_edition": False,
                    "description": "Spotify Family Combos",
                    "category": "Streaming Services",
                    "icon": "🎵"
                },
                "disney": {
                    "stock": 0,
                    "price_per_1k": 9.00,
                    "quality_rating": 4.7,
                    "trending": True,
                    "limited_edition": False,
                    "description": "Disney+ Bundle Combos",
                    "category": "Streaming Services",
                    "icon": "🏰"
                },
                
                # ===== GAMING =====
                "xbox": {
                    "stock": 0,
                    "price_per_1k": 11.00,
                    "quality_rating": 5.0,
                    "trending": True,
                    "limited_edition": False,
                    "description": "Xbox Game Pass Ultimate",
                    "category": "Gaming",
                    "icon": "🎮"
                },
                "playstation": {
                    "stock": 0,
                    "price_per_1k": 10.50,
                    "quality_rating": 4.9,
                    "trending": True,
                    "limited_edition": False,
                    "description": "PlayStation Plus Premium",
                    "category": "Gaming",
                    "icon": "👾"
                },
                "steam": {
                    "stock": 0,
                    "price_per_1k": 12.00,
                    "quality_rating": 5.0,
                    "trending": False,
                    "limited_edition": False,
                    "description": "Steam Premium Accounts",
                    "category": "Gaming",
                    "icon": "💻"
                },
                
                # ===== ENTERTAINMENT =====
                "hbo": {
                    "stock": 0,
                    "price_per_1k": 8.50,
                    "quality_rating": 4.6,
                    "trending": False,
                    "limited_edition": False,
                    "description": "HBO Max with Extras",
                    "category": "Entertainment",
                    "icon": "🎭"
                },
                "hulu": {
                    "stock": 0,
                    "price_per_1k": 8.00,
                    "quality_rating": 4.5,
                    "trending": False,
                    "limited_edition": False,
                    "description": "Hulu + Live TV",
                    "category": "Entertainment",
                    "icon": "📺"
                },
                "paramount": {
                    "stock": 0,
                    "price_per_1k": 8.00,
                    "quality_rating": 4.4,
                    "trending": False,
                    "limited_edition": False,
                    "description": "Paramount+ Combos",
                    "category": "Entertainment",
                    "icon": "⭐"
                },
                
                # ===== SHOPPING =====
                "amazon": {
                    "stock": 0,
                    "price_per_1k": 9.50,
                    "quality_rating": 4.8,
                    "trending": True,
                    "limited_edition": False,
                    "description": "Amazon Prime + Prime Video",
                    "category": "Shopping",
                    "icon": "📦"
                },
                "ebay": {
                    "stock": 0,
                    "price_per_1k": 7.50,
                    "quality_rating": 4.3,
                    "trending": False,
                    "limited_edition": False,
                    "description": "eBay Premium Accounts",
                    "category": "Shopping",
                    "icon": "🛒"
                },
                
                # ===== HOTMAIL =====
                "hotmail": {
                    "stock": 0,
                    "price_per_1k": 7.00,
                    "quality_rating": 4.9,
                    "trending": True,
                    "limited_edition": False,
                    "description": "Fresh Hotmail Combos",
                    "category": "Email",
                    "icon": "📧"
                },
                
                # ===== LIMITED EDITION (Higher prices) =====
                "crunchyroll_vip": {
                    "stock": 0,
                    "price_per_1k": 14.00,
                    "quality_rating": 5.0,
                    "trending": False,
                    "limited_edition": True,
                    "description": "Crunchyroll VIP (LIMITED)",
                    "category": "Anime",
                    "icon": "🔥"
                },
                "nordvpn_premium": {
                    "stock": 0,
                    "price_per_1k": 15.00,
                    "quality_rating": 5.0,
                    "trending": False,
                    "limited_edition": True,
                    "description": "NordVPN Premium (LIMITED)",
                    "category": "VPN",
                    "icon": "🔒"
                },
            },
            
            "logs": {
                # ===== HIGH QUALITY LOGS =====
                "private_logs_verified": {
                    "stock": 0,
                    "price_per_1k": 20.00,
                    "quality_rating": 5.0,
                    "trending": True,
                    "limited_edition": False,
                    "description": "💎 Private Verified Logs",
                    "category": "Premium Logs",
                    "icon": "🔐"
                },
                "public_logs_fresh": {
                    "stock": 0,
                    "price_per_1k": 8.00,
                    "quality_rating": 4.5,
                    "trending": False,
                    "limited_edition": False,
                    "description": "Fresh Public Logs",
                    "category": "Public Logs",
                    "icon": "📋"
                },
                "verified_2024": {
                    "stock": 0,
                    "price_per_1k": 25.00,
                    "quality_rating": 5.0,
                    "trending": True,
                    "limited_edition": True,
                    "description": "2024 Verified Logs (RARE)",
                    "category": "Premium Logs",
                    "icon": "✨"
                },
            },
            
            "ulps": {
                # ===== ULTRA LEGITIMATE PERSONALS =====
                "high_quality_premium": {
                    "stock": 0,
                    "price_per_1k": 30.00,
                    "quality_rating": 5.0,
                    "trending": True,
                    "limited_edition": False,
                    "description": "🏆 Premium Quality ULPs",
                    "category": "Ultra Premium",
                    "icon": "💎"
                },
                "high_quality": {
                    "stock": 0,
                    "price_per_1k": 25.00,
                    "quality_rating": 4.9,
                    "trending": False,
                    "limited_edition": False,
                    "description": "High Quality ULPs",
                    "category": "Premium",
                    "icon": "🥇"
                },
                "medium_quality": {
                    "stock": 0,
                    "price_per_1k": 15.00,
                    "quality_rating": 4.5,
                    "trending": False,
                    "limited_edition": False,
                    "description": "Medium Quality ULPs",
                    "category": "Standard",
                    "icon": "🥈"
                },
                "low_quality_budget": {
                    "stock": 0,
                    "price_per_1k": 8.00,
                    "quality_rating": 4.0,
                    "trending": False,
                    "limited_edition": False,
                    "description": "Budget ULPs",
                    "category": "Budget",
                    "icon": "💰"
                },
            },
            
            "bundles": {
                "streaming_ultimate": {
                    "items": ["netflix", "spotify", "disney", "hbo"],
                    "price": 199.99,
                    "discount_percent": 40,
                    "description": "🎬 ULTIMATE STREAMING BUNDLE",
                    "icon": "🌟"
                },
                "gaming_powerhouse": {
                    "items": ["xbox", "playstation", "steam"],
                    "price": 249.99,
                    "discount_percent": 35,
                    "description": "🎮 ULTIMATE GAMING BUNDLE",
                    "icon": "🎯"
                },
                "vip_collection": {
                    "items": ["crunchyroll_vip", "nordvpn_premium", "high_quality_premium"],
                    "price": 399.99,
                    "discount_percent": 50,
                    "description": "💎 VIP EXCLUSIVE COLLECTION",
                    "icon": "👑"
                },
            },
            
            "flash_sales": [
                {"item": "netflix", "discount": 0.30, "start": datetime.now().isoformat(), "duration_hours": 24},
                {"item": "xbox", "discount": 0.25, "start": datetime.now().isoformat(), "duration_hours": 12},
            ],
            
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "total_sales": 0,
                "customer_satisfaction": 4.8,
            }
        }
    
    def save_inventory(self):
        """Save inventory to JSON file"""
        with self.lock:
            try:
                self.data["metadata"]["last_updated"] = datetime.now().isoformat()
                with open(self.inventory_file, 'w') as f:
                    json.dump(self.data, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save inventory: {e}")
    
    def get_trending_items(self) -> Dict[str, Any]:
        """Get trending products"""
        trending = {}
        for category in ["combos", "logs", "ulps"]:
            items = self.data.get(category, {})
            for name, data in items.items():
                if data.get("trending"):
                    trending[f"{category}/{name}"] = data
        return trending
    
    def get_limited_editions(self) -> Dict[str, Any]:
        """Get limited edition items"""
        limited = {}
        for category in ["combos", "logs", "ulps"]:
            items = self.data.get(category, {})
            for name, data in items.items():
                if data.get("limited_edition"):
                    limited[f"{category}/{name}"] = data
        return limited
    
    def get_bundles(self) -> Dict[str, Any]:
        """Get available bundles"""
        return self.data.get("bundles", {})
    
    def get_category_items(self, category: str) -> Dict[str, Dict]:
        """Get all items in a category"""
        return self.data.get(category, {})
    
    def get_item_stock(self, category: str, item: str) -> int:
        """Get stock for specific item"""
        try:
            return self.data[category][item]["stock"]
        except KeyError:
            return 0
    
    def get_item_price(self, category: str, item: str) -> float:
        """Get price per 1000 for item"""
        try:
            return self.data[category][item]["price_per_1k"]
        except KeyError:
            return 0.0
    
    def get_item_quality(self, category: str, item: str) -> float:
        """Get quality rating for item"""
        try:
            return self.data[category][item].get("quality_rating", 4.5)
        except KeyError:
            return 0.0
    
    def calculate_price(self, category: str, item: str, quantity: int, vip_tier: str = None) -> float:
        """Calculate price with VIP discounts"""
        if quantity < self.MIN_COMBO_PURCHASE:
            return 0.0
        
        price_per_1k = self.get_item_price(category, item)
        base_amount = (quantity / 1000.0) * price_per_1k
        
        # Apply VIP discount
        vip_discount = 0
        if vip_tier and vip_tier in self.VIP_TIERS:
            vip_discount = self.VIP_TIERS[vip_tier]["discount"]
        
        # Check flash sales
        flash_discount = self._get_flash_sale_discount(category, item)
        
        # Apply largest discount
        total_discount = max(vip_discount, flash_discount)
        final_price = base_amount * (1 - total_discount)
        
        return round(final_price, 2)
    
    def _get_flash_sale_discount(self, category: str, item: str) -> float:
        """Check if item is on flash sale"""
        flash_sales = self.data.get("flash_sales", [])
        for sale in flash_sales:
            if sale.get("item") == item:
                try:
                    start = datetime.fromisoformat(sale["start"])
                    duration = timedelta(hours=sale.get("duration_hours", 24))
                    if start <= datetime.now() <= start + duration:
                        return sale.get("discount", 0)
                except:
                    pass
        return 0.0
    
    def can_purchase(self, category: str, item: str, quantity: int) -> Tuple[bool, str]:
        """Check if purchase is possible"""
        if quantity < self.MIN_COMBO_PURCHASE:
            return False, f"❌ Minimum purchase: {self.MIN_COMBO_PURCHASE} combos"
        
        stock = self.get_item_stock(category, item)
        if stock <= 0:
            return False, f"❌ Out of stock: {item}"
        
        if stock < quantity:
            return False, f"❌ Only {stock:,} available, you requested {quantity:,}"
        
        return True, "✅ Available for purchase"
    
    def deduct_stock(self, category: str, item: str, quantity: int) -> bool:
        """Deduct stock after purchase"""
        with self.lock:
            stock = self.get_item_stock(category, item)
            if stock >= quantity:
                self.data[category][item]["stock"] -= quantity
                self.data["metadata"]["total_sales"] = self.data["metadata"].get("total_sales", 0) + 1
                self.save_inventory()
                return True
            return False
    
    def add_stock(self, category: str, item: str, quantity: int):
        """Add stock (admin function)"""
        with self.lock:
            if category not in self.data:
                self.data[category] = {}
            if item not in self.data[category]:
                self.data[category][item] = {
                    "stock": 0,
                    "price_per_1k": 10.00,
                    "quality_rating": 4.5,
                    "trending": False,
                    "limited_edition": False,
                    "description": item,
                    "category": "Custom",
                    "icon": "📦"
                }
            
            self.data[category][item]["stock"] += quantity
            self.save_inventory()
            logger.info(f"Added {quantity} to {category}/{item}")
    
    def set_price(self, category: str, item: str, price: float):
        """Set price per 1000 (admin function)"""
        with self.lock:
            if category in self.data and item in self.data[category]:
                self.data[category][item]["price_per_1k"] = price
                self.save_inventory()
                logger.info(f"Set price for {category}/{item} to ${price} per 1k")
    
    def set_stock(self, category: str, item: str, quantity: int):
        """Set exact stock amount (admin function)"""
        with self.lock:
            if category in self.data and item in self.data[category]:
                self.data[category][item]["stock"] = quantity
                self.save_inventory()
                logger.info(f"Set stock for {category}/{item} to {quantity}")


class LuxuryMarketplacePurchase:
    """Track premium purchases with loyalty & rewards"""
    
    def __init__(self, purchase_file: str = "marketplace_purchases.json"):
        self.purchase_file = purchase_file
        self.lock = Lock()
        self.load_purchases()
    
    def load_purchases(self):
        """Load purchase history"""
        if os.path.exists(self.purchase_file):
            try:
                with open(self.purchase_file, 'r') as f:
                    self.purchases = json.load(f)
            except Exception:
                self.purchases = {}
        else:
            self.purchases = {}
    
    def save_purchases(self):
        """Save purchase history"""
        with self.lock:
            try:
                with open(self.purchase_file, 'w') as f:
                    json.dump(self.purchases, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save purchases: {e}")
    
    def create_purchase(self, user_id: int, category: str, item: str, 
                       quantity: int, price: float) -> str:
        """Create new purchase record - returns purchase_id"""
        purchase_id = f"MKT_{user_id}_{int(datetime.now().timestamp())}"
        
        with self.lock:
            self.purchases[purchase_id] = {
                "user_id": user_id,
                "category": category,
                "item": item,
                "quantity": quantity,
                "price": price,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "paid_at": None,
                "delivered_at": None,
                "file_path": None,
                "rating": 0,
                "review": None
            }
            self.save_purchases()
        
        return purchase_id
    
    def mark_paid(self, purchase_id: str):
        """Mark purchase as paid"""
        with self.lock:
            if purchase_id in self.purchases:
                self.purchases[purchase_id]["status"] = "paid"
                self.purchases[purchase_id]["paid_at"] = datetime.now().isoformat()
                self.save_purchases()
    
    def mark_delivered(self, purchase_id: str, file_path: str):
        """Mark purchase as delivered"""
        with self.lock:
            if purchase_id in self.purchases:
                self.purchases[purchase_id]["status"] = "delivered"
                self.purchases[purchase_id]["delivered_at"] = datetime.now().isoformat()
                self.purchases[purchase_id]["file_path"] = file_path
                self.save_purchases()
    
    def get_purchase(self, purchase_id: str) -> Optional[Dict]:
        """Get purchase details"""
        return self.purchases.get(purchase_id)
    
    def get_user_purchases(self, user_id: int) -> List[Dict]:
        """Get all purchases by user"""
        return [p for p in self.purchases.values() if p["user_id"] == user_id]
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Get user statistics for VIP tier"""
        purchases = self.get_user_purchases(user_id)
        
        total_spent = sum(p["price"] for p in purchases if p["status"] == "delivered")
        total_purchases = len([p for p in purchases if p["status"] == "delivered"])
        
        return {
            "total_spent": total_spent,
            "total_purchases": total_purchases,
            "last_purchase": purchases[-1]["created_at"] if purchases else None
        }
    
    def get_vip_tier(self, user_id: int) -> str:
        """Determine user's VIP tier based on spending"""
        stats = self.get_user_stats(user_id)
        spent = stats["total_spent"]
        
        if spent >= 5000:
            return "platinum"
        elif spent >= 1000:
            return "gold"
        elif spent >= 250:
            return "silver"
        elif spent >= 50:
            return "bronze"
        return None
