import os
import re
import asyncio
import logging
import hashlib
import json
import random
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient, events

# ====================== CONFIGURATION ======================
API_ID = 2040
API_HASH = 'b18441a1ff607e10a989891a5462e627'
SESSION_FILE = 'user_session'

# Channel names (exactly as they appear in Telegram)
SOURCE_CHANNEL = "NOIR"      # Channel to watch
DEST_CHANNEL = "Null Shop Cloud"   # Channel to post to

# File naming
HOTMAIL_NAME = "VALID UHQ Hotmail Access @NullShop0X"
MIXED_NAME = "VALID UHQ Mixed Mails Access @NullShop0X"

# Settings
ENABLE_WATERMARKS = False               # Turn on/off watermarking
DUP_CHECK = 0.7                         # 70% similarity = duplicate
HOTMAIL_THRESHOLD = 80                  # 80% hotmail = hotmail file


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Forwarder:
    def __init__(self):
        self.client = None
        self.session = SESSION_FILE
        
        # Channel objects
        self.source = None
        self.dest = None
        
        # Create temp folder if it doesn't exist
        self.temp = Path("temp_files")
        self.temp.mkdir(exist_ok=True)
        
        # Keep track of what we've already posted
        self.seen_files = self.load_seen_files()
        
        # Setup watermark stuff if needed
        if ENABLE_WATERMARKS:
            self.setup_watermarks()
    
    def setup_watermarks(self):
        """Setup watermark lines and generators"""
        # Some random watermark lines
        self.watermarks = [
            "support@ravencloud.com:@re187re",
            "admin@t.me.com:@RE187RE", 
            "contact@protonmail.com:@re187re123",
            "service@outlook.com:@re187re!",
            "@RavenCloudHQ",
            "@Raven07X",
            "SOURCE: @RavenCloudHQ",
            "Premium Database @RavenCloudHQ",
            "Fresh Combo @Raven07X",
        ]
        
        # Common email domains for generating fake emails
        self.domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
        
        # Username patterns
        self.usernames = [
            lambda: ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=random.randint(6, 10))),
            lambda: random.choice(["john", "jane", "mike", "sarah"]) + str(random.randint(1, 99)),
        ]
    
    def fake_email(self):
        """Generate a random looking email"""
        user = random.choice(self.usernames)()
        domain = random.choice(self.domains)
        return f"{user}@{domain}"
    
    def fake_pass(self):
        """Generate a password that looks like @re187re variations"""
        base = "@re187re"
        choices = [base, base.upper(), base + str(random.randint(1, 50)), base + "!"]
        return random.choice(choices)
    
    def add_watermark_lines(self, lines):
        """Add some watermark lines to the file"""
        if not ENABLE_WATERMARKS or len(lines) < 10:
            return lines
        
        result = []
        # Add some watermarks at the beginning
        for i in range(random.randint(2, 4)):
            result.append(random.choice(self.watermarks))
        
        # Add watermarks throughout the file
        interval = random.randint(10, 25)
        for i, line in enumerate(lines):
            result.append(line)
            if i > 0 and i % interval == 0:
                for j in range(random.randint(1, 2)):
                    # Sometimes add a fake combo instead of just watermark
                    if random.random() > 0.7:
                        result.append(f"{self.fake_email()}:{self.fake_pass()}")
                    else:
                        result.append(random.choice(self.watermarks))
        
        # Add some at the end
        for i in range(random.randint(3, 5)):
            result.append(random.choice(self.watermarks))
        
        logger.info(f"Added some watermarks to the file")
        return result
    
    def load_seen_files(self):
        """Load list of files we've already processed"""
        seen_file = self.temp / "seen.json"
        if seen_file.exists():
            try:
                with open(seen_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_seen_files(self):
        """Save list of processed files"""
        try:
            with open(self.temp / "seen.json", 'w') as f:
                json.dump(self.seen_files, f)
        except:
            pass
    
    def hash_content(self, lines):
        """Create a hash of the file content"""
        sorted_lines = sorted(set(lines))
        content = '\n'.join(sorted_lines).encode('utf-8')
        return hashlib.md5(content).hexdigest()
    
    def is_duplicate(self, new_lines):
        """Check if we've seen this file before"""
        if not self.seen_files:
            return False, 0
        
        new_hash = self.hash_content(new_lines)
        
        # Exact duplicate?
        if new_hash in self.seen_files:
            logger.info("Seen this exact file before")
            return True, 100
        
        # Check similarity with old files
        best = 0
        for old_hash, data in self.seen_files.items():
            if 'lines' not in data:
                continue
            
            old_set = set(data.get('sample', []))
            new_set = set(new_lines)
            
            if not old_set or not new_set:
                continue
            
            common = old_set.intersection(new_set)
            overlap = len(common) / min(len(old_set), len(new_set))
            
            if overlap > best:
                best = overlap
            
            if overlap >= DUP_CHECK:
                logger.info(f"Too similar: {overlap:.1%} match")
                return True, overlap * 100
        
        return False, best * 100
    
    def check_hotmail(self, email):
        """Check if email is hotmail/outlook related"""
        if '@' not in email:
            return False
        
        domain = email.split('@')[-1].lower()
        # Check for hotmail, outlook, msn, live domains
        hotmail_domains = ['hotmail', 'outlook', 'msn', 'live']
        for hd in hotmail_domains:
            if hd in domain:
                return True
        return False
    
    def analyze_file(self, lines):
        """Figure out if file is mostly hotmail or mixed"""
        if not lines:
            return 'mixed'
        
        hotmail_count = 0
        total = 0
        
        for line in lines:
            if ':' in line and '@' in line:
                email = line.split(':', 1)[0].strip()
                total += 1
                if self.check_hotmail(email):
                    hotmail_count += 1
        
        if total == 0:
            return 'mixed'
        
        percentage = (hotmail_count / total) * 100
        
        if percentage >= HOTMAIL_THRESHOLD:
            logger.info(f"Hotmail file: {percentage:.1f}% hotmail accounts")
            return 'hotmail'
        else:
            logger.info(f"Mixed file: {percentage:.1f}% hotmail accounts")
            return 'mixed'
    
    def clean_text(self, file_path):
        """Remove spam lines and clean up the file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Remove common spam patterns
            spam = [
                r'-{10,}.*t\.me/ByteEntry.*-{10,}',
                r'BYTE-ENTRY-SOURCE.*@_B_y_t_e_E_n_t_r_y_',
                r'=+.*JOIN THE EXCLUSIVE.*=+',
                r'\*+.*FULL MAIL ACCESS.*\*+',
                r'^https?://t\.me/.*$',
                r'^@.*$',
                r'^Join our.*$',
            ]
            
            for pattern in spam:
                content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE)
            
            lines = content.split('\n')
            valid = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Keep email:password lines
                if ':' in line and '@' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        email = parts[0].strip()
                        pwd = parts[1].strip()
                        if email and pwd and len(pwd) >= 3:
                            valid.append(line)
                # Keep watermark lines if they look legit
                elif any(wm in line.lower() for wm in ['@re187re', '@ravencloudhq']):
                    valid.append(line)
            
            # Remove duplicates
            unique = []
            seen = set()
            for line in valid:
                if line not in seen:
                    seen.add(line)
                    unique.append(line)
            
            logger.info(f"Cleaned up: {len(unique)} good lines")
            return unique
            
        except Exception as e:
            logger.error(f"Error cleaning: {e}")
            return []
    
    def make_filename(self, count, is_hotmail):
        """Create a filename with the count and type"""
        if is_hotmail:
            return f"{count}X {HOTMAIL_NAME}.txt"
        else:
            return f"{count}X {MIXED_NAME}.txt"
    
    def create_temp_file(self, lines, is_hotmail):
        """Create a temp file with the cleaned content"""
        count = len(lines)
        
        # Add watermarks if enabled
        if ENABLE_WATERMARKS:
            final_lines = self.add_watermark_lines(lines)
        else:
            final_lines = lines
        
        # Create filename
        filename = self.make_filename(count, is_hotmail)
        temp_path = self.temp / filename
        
        # Write to file
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(final_lines))
        
        logger.info(f"Created: {filename}")
        return temp_path
    
    async def send_file(self, channel, file_path):
        """Send a file to a channel"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return None
            
            # Just send it
            msg = await self.client.send_file(channel, file_path)
            logger.info(f"Sent to {channel.title if hasattr(channel, 'title') else 'channel'}")
            return msg
            
        except Exception as e:
            logger.error(f"Send error: {e}")
            return None
    
    async def process_file(self, message):
        """Process a new file from the source channel"""
        try:
            if not message.media:
                return
            
            logger.info("Got a new file!")
            
            # Download
            file_path = await message.download_media()
            if not file_path:
                return
            
            # Only process text files
            if not str(file_path).lower().endswith('.txt'):
                # Just forward non-text files
                if self.dest:
                    await self.send_file(self.dest, file_path)
                os.remove(file_path)
                return
            
            # Clean the text file
            cleaned = self.clean_text(file_path)
            if not cleaned:
                logger.warning("No valid lines found")
                os.remove(file_path)
                return
            
            # Check for duplicates
            is_dup, dup_percent = self.is_duplicate(cleaned)
            if is_dup:
                logger.warning(f"Skipping - duplicate ({dup_percent:.1f}% match)")
                os.remove(file_path)
                return
            
            logger.info(f"New file - {dup_percent:.1f}% similar to previous files")
            
            # Figure out what type of file this is
            file_type = self.analyze_file(cleaned)
            is_hotmail = (file_type == 'hotmail')
            
            # Create hash for tracking
            file_hash = self.hash_content(cleaned)
            
            # Send to destination
            if self.dest:
                temp_file = self.create_temp_file(cleaned, is_hotmail)
                if temp_file and os.path.exists(temp_file):
                    await self.send_file(self.dest, temp_file)
                    
                    # Save to seen files
                    self.seen_files[file_hash] = {
                        'timestamp': datetime.now().isoformat(),
                        'count': len(cleaned),
                        'type': file_type,
                        'sample': list(set(cleaned))[:50]  # Store first 50 unique lines for comparison
                    }
                    self.save_seen_files()
                    
                    # Clean up temp file
                    os.remove(temp_file)
            
            # Clean up original
            if os.path.exists(file_path):
                os.remove(file_path)
                
        except Exception as e:
            logger.error(f"Error: {e}")
            if 'file_path' in locals() and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
    
    async def login(self):
        """Login to Telegram"""
        print("\n" + "="*50)
        print("Telegram Login")
        print("="*50)
        
        self.client = TelegramClient(self.session, API_ID, API_HASH)
        await self.client.connect()
        
        if not await self.client.is_user_authorized():
            phone = input("Phone number (with country code): ").strip()
            await self.client.send_code_request(phone)
            code = input("Enter the code you received: ").strip()
            
            try:
                await self.client.sign_in(phone, code=code)
                print("Logged in!")
            except Exception as e:
                if "password" in str(e).lower():
                    pwd = input("2FA password: ").strip()
                    await self.client.sign_in(password=pwd)
                    print("Logged in with 2FA!")
                else:
                    print(f"Login failed: {e}")
                    return False
        else:
            print("Already logged in")
        
        return True
    
    async def find_channels(self):
        """Find the source and destination channels"""
        print("\n" + "="*50)
        print("Finding Channels")
        print("="*50)
        
        # Look for destination
        print(f"\nLooking for destination: {DEST_CHANNEL}")
        async for dialog in self.client.iter_dialogs():
            if dialog.name == DEST_CHANNEL:
                self.dest = dialog.entity
                print(f"Found: {dialog.name}")
                break
        
        if not self.dest:
            print(f"\nCouldn't find '{DEST_CHANNEL}'")
            print("\nAvailable channels:")
            async for dialog in self.client.iter_dialogs():
                if dialog.is_channel:
                    print(f"  - {dialog.name}")
            
            choice = input("\nEnter a different channel name? (y/n): ").strip().lower()
            if choice == 'y':
                name = input("Channel name: ").strip()
                async for dialog in self.client.iter_dialogs():
                    if dialog.name == name:
                        self.dest = dialog.entity
                        print(f"Found: {dialog.name}")
                        break
            
            if not self.dest:
                print("No destination channel found")
                return False
        
        # Look for source
        print(f"\nLooking for source: {SOURCE_CHANNEL}")
        async for dialog in self.client.iter_dialogs():
            if dialog.name == SOURCE_CHANNEL:
                self.source = dialog.entity
                print(f"Found: {dialog.name}")
                break
        
        if not self.source:
            print(f"\nCouldn't find '{SOURCE_CHANNEL}'")
            print("\nAvailable channels:")
            async for dialog in self.client.iter_dialogs():
                if dialog.is_channel:
                    print(f"  - {dialog.name}")
            
            choice = input("\nEnter a different source channel? (y/n): ").strip().lower()
            if choice == 'y':
                name = input("Channel name: ").strip()
                async for dialog in self.client.iter_dialogs():
                    if dialog.name == name:
                        self.source = dialog.entity
                        print(f"Found: {dialog.name}")
                        break
            
            if not self.source:
                print("No source channel found")
                return False
        
        return True
    
    async def run(self):
        """Main loop"""
        try:
            # Login
            if not await self.login():
                return
            
            # Find channels
            if not await self.find_channels():
                return
            
            # Set up event handler for new messages
            @self.client.on(events.NewMessage(chats=self.source))
            async def handler(event):
                if event.message.media:
                    await self.process_file(event.message)
            
            print("\n" + "="*70)
            print("File Forwarder Running")
            print("="*70)
            print(f"Watching: {SOURCE_CHANNEL}")
            print(f"Posting to: {DEST_CHANNEL}")
            print(f"Watermarks: {'On' if ENABLE_WATERMARKS else 'Off'}")
            print(f"Hotmail threshold: {HOTMAIL_THRESHOLD}%")
            print("\nWaiting for files... (Ctrl+C to stop)")
            print("="*70)
            
            # Keep running
            await self.client.run_until_disconnected()
            
        except KeyboardInterrupt:
            print("\n\nStopping...")
        except Exception as e:
            print(f"\nError: {e}")
        finally:
            if self.client:
                await self.client.disconnect()
                print("Disconnected")

def main():
    print("="*70)
    print("Telegram File Forwarder")
    print("="*70)
    print(f"Source: {SOURCE_CHANNEL}")
    print(f"Destination: {DEST_CHANNEL}")
    print(f"Watermarks: {'ON' if ENABLE_WATERMARKS else 'OFF'}")
    print("="*70)
    
    forwarder = Forwarder()
    asyncio.run(forwarder.run())

if __name__ == "__main__":
    main()