#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Marketplace System - Combos, Logs, ULPs
Inventory management, pricing, and delivery
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from threading import Lock

logger = logging.getLogger(__name__)


class MarketplaceInventory:
    """Manages combo/log/ULP inventory and pricing"""
    
    def __init__(self, inventory_file: str = "marketplace_inventory.json"):
        self.inventory_file = inventory_file
        self.lock = Lock()
        self.MIN_COMBO_PURCHASE = 1000
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
        """Default inventory structure"""
        return {
            "combos": {
                "hotmail": {
                    "stock": 0,
                    "price_per_1k": 7.00,
                    "description": "Standard Hotmail Combos"
                },
                "netflix": {
                    "stock": 0,
                    "price_per_1k": 10.00,
                    "description": "Netflix Service Combos"
                },
                "spotify": {
                    "stock": 0,
                    "price_per_1k": 8.50,
                    "description": "Spotify Service Combos"
                },
                "disney": {
                    "stock": 0,
                    "price_per_1k": 9.00,
                    "description": "Disney+ Service Combos"
                },
                "hulu": {
                    "stock": 0,
                    "price_per_1k": 8.00,
                    "description": "Hulu Service Combos"
                },
                "amazon": {
                    "stock": 0,
                    "price_per_1k": 9.50,
                    "description": "Amazon Prime Service Combos"
                },
                "hbo": {
                    "stock": 0,
                    "price_per_1k": 8.50,
                    "description": "HBO Max Service Combos"
                },
                "paramount": {
                    "stock": 0,
                    "price_per_1k": 8.00,
                    "description": "Paramount+ Service Combos"
                },
                "xbox": {
                    "stock": 0,
                    "price_per_1k": 11.00,
                    "description": "Xbox Game Pass Combos"
                },
                "playstation": {
                    "stock": 0,
                    "price_per_1k": 10.50,
                    "description": "PlayStation Combos"
                }
            },
            "logs": {
                "private_logs": {
                    "stock": 0,
                    "price_per_1k": 15.00,
                    "description": "Private Logs (High Quality)"
                },
                "public_logs": {
                    "stock": 0,
                    "price_per_1k": 8.00,
                    "description": "Public Logs"
                },
                "verified_logs": {
                    "stock": 0,
                    "price_per_1k": 20.00,
                    "description": "Verified Fresh Logs"
                }
            },
            "ulps": {
                "high_quality": {
                    "stock": 0,
                    "price_per_1k": 25.00,
                    "description": "High Quality ULPs"
                },
                "medium_quality": {
                    "stock": 0,
                    "price_per_1k": 15.00,
                    "description": "Medium Quality ULPs"
                },
                "low_quality": {
                    "stock": 0,
                    "price_per_1k": 8.00,
                    "description": "Low Quality ULPs"
                }
            },
            "last_updated": datetime.now().isoformat()
        }
    
    def save_inventory(self):
        """Save inventory to JSON file"""
        with self.lock:
            try:
                self.data["last_updated"] = datetime.now().isoformat()
                with open(self.inventory_file, 'w') as f:
                    json.dump(self.data, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save inventory: {e}")
    
    def get_category_items(self, category: str) -> Dict[str, Dict]:
        """Get all items in a category (combos, logs, ulps)"""
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
    
    def calculate_price(self, category: str, item: str, quantity: int) -> float:
        """Calculate total price for quantity combos"""
        if quantity < self.MIN_COMBO_PURCHASE:
            return 0.0
        
        price_per_1k = self.get_item_price(category, item)
        # quantity is in combos, convert to 1k units
        amount_1k = quantity / 1000.0
        return price_per_1k * amount_1k
    
    def can_purchase(self, category: str, item: str, quantity: int) -> tuple[bool, str]:
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
                self.save_inventory()
                return True
            return False
    
    def add_stock(self, category: str, item: str, quantity: int):
        """Add stock (admin function)"""
        with self.lock:
            if category not in self.data:
                self.data[category] = {}
            if item not in self.data[category]:
                self.data[category][item] = {"stock": 0, "price_per_1k": 7.00, "description": item}
            
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


class MarketplacePurchase:
    """Track and manage individual purchases"""
    
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
                "status": "pending",  # pending, paid, delivered, cancelled
                "created_at": datetime.now().isoformat(),
                "paid_at": None,
                "delivered_at": None,
                "file_path": None
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
