#!/usr/bin/env python3
"""
Productivity Guardian - Multi-user website blocker until educational goals are met
Requires: Python 3.6+, sudo privileges (for system-wide blocking) or user-specific blocking
"""

import os
import sys
import time
import json
import signal
import subprocess
import threading
import getpass
import fcntl
from datetime import datetime, timedelta
from pathlib import Path

try:
    import psutil
except ImportError:
    print("❌ psutil module required. Install with: pip3 install psutil")
    sys.exit(1)

class ProductivityGuardian:
    def __init__(self, config_file=None):
        # User identification
        self.username = getpass.getuser()
        self.user_id = os.getuid() if hasattr(os, 'getuid') else str(hash(self.username))
        
        # Setup user-specific directories
        self.setup_user_directories()
        
        # File paths (user-specific)
        self.config_file = config_file or (self.config_dir / "config.json")
        self.data_file = self.config_dir / "guardian_data.json"
        self.lock_file = self.config_dir / "guardian.lock"
        
        # System-wide files (for backward compatibility)
        self.hosts_backup = f"/etc/hosts.guardian_backup_{self.username}"
        self.hosts_file = "/etc/hosts"
        
        # Runtime state
        self.is_running = False
        self.monitor_thread = None
        self.lock_fd = None
        
        # Load configuration and data
        self.load_config()
        self.load_data()
        
        # Signal handlers for clean shutdown
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def setup_user_directories(self):
        """Setup user-specific configuration directories"""
        # Use user's home directory for data storage
        home_dir = Path.home()
        self.config_dir = home_dir / ".productivity_guardian"
        self.config_dir.mkdir(exist_ok=True, mode=0o700)  # Private to user
        
        # Create logs directory
        self.logs_dir = self.config_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True, mode=0o700)
        
        print(f"👤 User: {self.username}")
        print(f"📁 Config directory: {self.config_dir}")
    
    def acquire_lock(self):
        """Acquire file lock to prevent multiple instances per user"""
        try:
            self.lock_fd = open(self.lock_file, 'w')
            fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_fd.write(f"{os.getpid()}\n{datetime.now().isoformat()}\n")
            self.lock_fd.flush()
            return True
        except (IOError, OSError):
            if self.lock_fd:
                self.lock_fd.close()
                self.lock_fd = None
            return False
    
    def release_lock(self):
        """Release file lock"""
        if self.lock_fd:
            try:
                fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_UN)
                self.lock_fd.close()
                self.lock_file.unlink(missing_ok=True)
            except:
                pass
            self.lock_fd = None

    def load_config(self):
        """Load user-specific configuration from JSON file"""
        default_config = {
            "blocked_sites": [
                "youtube.com",
                "www.youtube.com",
                "facebook.com",
                "www.facebook.com",
                "twitter.com",
                "www.twitter.com",
                "instagram.com",
                "www.instagram.com",
                "reddit.com",
                "www.reddit.com",
                "tiktok.com",
                "www.tiktok.com"
            ],
            "educational_sites": [
                "khanacademy.org",
                "www.khanacademy.org",
                "coursera.org",
                "www.coursera.org",
                "edx.org",
                "www.edx.org",
                "codecademy.com",
                "www.codecademy.com"
            ],
            "daily_goal_minutes": 30,
            "check_interval_seconds": 30,
            "redirect_ip": "127.0.0.1",
            "test_mode": False,
            "blocking_method": "auto",  # auto, hosts, browser, proxy
            "user_specific": True
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                # Merge with defaults for missing keys
                for key, value in default_config.items():
                    if key not in self.config:
                        self.config[key] = value
            except Exception as e:
                print(f"Error loading config: {e}")
                self.config = default_config
        else:
            self.config = default_config
            self.save_config()
    
    def save_config(self):
        """Save user-specific configuration to JSON file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

    def load_data(self):
        """Load user-specific persistent data"""
        default_data = {
            "username": self.username,
            "today": datetime.now().strftime("%Y-%m-%d"),
            "time_spent_today": 0,
            "total_time_spent": 0,
            "goals_completed": 0,
            "last_activity": None,
            "sites_visited_today": [],
            "sites_visited_sessions": [],
            "blocking_active": False,
            "created_date": datetime.now().isoformat()
        }
        
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r') as f:
                    self.data = json.load(f)
                
                # Reset daily data if it's a new day
                today = datetime.now().strftime("%Y-%m-%d")
                if self.data.get("today") != today:
                    self.data["today"] = today
                    self.data["time_spent_today"] = 0
                    self.data["sites_visited_today"] = []
                
                # Ensure all required fields exist
                for key, value in default_data.items():
                    if key not in self.data:
                        self.data[key] = value
                
                # Update username in case it changed
                self.data["username"] = self.username
                    
            except Exception as e:
                print(f"Error loading data: {e}")
                self.data = default_data
        else:
            self.data = default_data
        
        self.save_data()
    
    def save_data(self):
        """Save user-specific persistent data"""
        self.data["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Error saving data: {e}")
    
    def determine_blocking_method(self):
        """Determine the best blocking method for this user/system"""
        method = self.config.get("blocking_method", "auto")
        
        if method == "auto":
            # Check if user has sudo privileges
            try:
                subprocess.run(['sudo', '-n', 'true'], check=True, capture_output=True)
                return "hosts"  # User has sudo, use system-wide hosts file
            except subprocess.CalledProcessError:
                return "browser"  # No sudo, use browser-specific blocking
        
        return method
    
    def block_websites_hosts(self):
        """Block websites using system-wide hosts file (requires sudo)"""
        if not self.backup_hosts_file():
            return False
        
        try:
            # Read current hosts file
            with open(self.hosts_file, 'r') as f:
                hosts_content = f.read()
            
            # Add user-specific blocking entries
            blocked_entries = []
            user_marker = f"# Productivity Guardian - {self.username} - Blocked Sites"
            
            # Remove existing entries for this user
            lines = hosts_content.split('\n')
            filtered_lines = []
            skip_until_end = False
            
            for line in lines:
                if user_marker in line or f"# End Productivity Guardian - {self.username}" in line:
                    skip_until_end = not skip_until_end
                    continue
                if not skip_until_end:
                    filtered_lines.append(line)
            
            hosts_content = '\n'.join(filtered_lines)
            
            # Add new blocking entries
            for site in self.config["blocked_sites"]:
                entry = f"{self.config['redirect_ip']} {site}"
                blocked_entries.append(entry)
            
            if blocked_entries:
                hosts_content += f"\n{user_marker}\n"
                hosts_content += "\n".join(blocked_entries)
                hosts_content += f"\n# End Productivity Guardian - {self.username}\n"
                
                # Write back to hosts file
                temp_file = f'/tmp/hosts_temp_{self.username}'
                with open(temp_file, 'w') as f:
                    f.write(hosts_content)
                
                subprocess.run(['sudo', 'cp', temp_file, self.hosts_file], check=True)
                os.remove(temp_file)
                
                print(f"✓ Blocked {len(blocked_entries)} websites using hosts file")
                return True
        
        except Exception as e:
            print(f"Error blocking websites: {e}")
            return False
    
    def unblock_websites_hosts(self):
        """Remove blocked websites from hosts file"""
        try:
            with open(self.hosts_file, 'r') as f:
                hosts_content = f.read()
            
            # Remove user-specific blocking entries
            user_marker = f"# Productivity Guardian - {self.username} - Blocked Sites"
            lines = hosts_content.split('\n')
            filtered_lines = []
            skip_until_end = False
            
            for line in lines:
                if user_marker in line or f"# End Productivity Guardian - {self.username}" in line:
                    skip_until_end = not skip_until_end
                    continue
                if not skip_until_end:
                    filtered_lines.append(line)
            
            hosts_content = '\n'.join(filtered_lines)
            
            # Write back to hosts file
            temp_file = f'/tmp/hosts_temp_{self.username}'
            with open(temp_file, 'w') as f:
                f.write(hosts_content)
            
            subprocess.run(['sudo', 'cp', temp_file, self.hosts_file], check=True)
            os.remove(temp_file)
            
            print(f"✓ Unblocked websites for user {self.username}")
            return True
        
        except Exception as e:
            print(f"Error unblocking websites: {e}")
            return False
    
    def block_websites_browser(self):
        """Block websites using browser-specific methods"""
        print(f"🌐 Implementing browser-specific blocking for user {self.username}")
        
        # Create user-specific blocking configuration
        blocking_config = {
            "username": self.username,
            "blocked_sites": self.config["blocked_sites"],
            "redirect_ip": self.config["redirect_ip"],
            "timestamp": datetime.now().isoformat()
        }
        
        # Save browser blocking config
        browser_config_file = self.config_dir / "browser_blocking.json"
        with open(browser_config_file, 'w') as f:
            json.dump(blocking_config, f, indent=2)
        
        # Try to implement browser-specific blocking
        success = False
        
        # Method 1: Try to create user-specific hosts file override
        user_hosts_file = self.config_dir / "hosts_override"
        try:
            with open(user_hosts_file, 'w') as f:
                f.write("# User-specific hosts override\n")
                for site in self.config["blocked_sites"]:
                    f.write(f"{self.config['redirect_ip']} {site}\n")
            
            print(f"✓ Created user-specific hosts override: {user_hosts_file}")
            success = True
        except Exception as e:
            print(f"Warning: Could not create hosts override: {e}")
        
        # Method 2: Browser extension simulation (placeholder)
        try:
            extension_config = self.config_dir / "browser_extension_config.json"
            with open(extension_config, 'w') as f:
                json.dump({
                    "blocked_domains": self.config["blocked_sites"],
                    "redirect_url": f"http://{self.config['redirect_ip']}",
                    "user": self.username,
                    "active": True
                }, f, indent=2)
            
            print(f"✓ Created browser extension config: {extension_config}")
            success = True
        except Exception as e:
            print(f"Warning: Could not create browser extension config: {e}")
        
        if success:
            print(f"✓ Browser-specific blocking activated for {self.username}")
            print("💡 Note: For full browser blocking, install a compatible browser extension")
            print("💡 Or run with sudo privileges for system-wide hosts file blocking")
        
        return success
    
    def unblock_websites_browser(self):
        """Remove browser-specific blocking"""
        try:
            # Remove user-specific blocking files
            files_to_remove = [
                self.config_dir / "browser_blocking.json",
                self.config_dir / "hosts_override",
                self.config_dir / "browser_extension_config.json"
            ]
            
            for file_path in files_to_remove:
                if file_path.exists():
                    file_path.unlink()
                    print(f"✓ Removed {file_path.name}")
            
            print(f"✓ Browser-specific blocking removed for {self.username}")
            return True
        
        except Exception as e:
            print(f"Error removing browser blocking: {e}")
            return False
    
    def block_websites(self):
        """Block websites using the appropriate method"""
        method = self.determine_blocking_method()
        print(f"🔒 Using blocking method: {method}")
        
        if method == "hosts":
            success = self.block_websites_hosts()
        elif method == "browser":
            success = self.block_websites_browser()
        else:
            print(f"❌ Unknown blocking method: {method}")
            return False
        
        if success:
            self.data["blocking_active"] = True
            self.save_data()
        
        return success
    
    def unblock_websites(self):
        """Unblock websites using the appropriate method"""
        method = self.determine_blocking_method()
        
        if method == "hosts":
            success = self.unblock_websites_hosts()
        elif method == "browser":
            success = self.unblock_websites_browser()
        else:
            print(f"❌ Unknown blocking method: {method}")
            return False
        
        if success:
            self.data["blocking_active"] = False
            self.save_data()
        
        return success

    def backup_hosts_file(self):
        """Create user-specific backup of original hosts file"""
        if not os.path.exists(self.hosts_backup):
            try:
                subprocess.run(['sudo', 'cp', self.hosts_file, self.hosts_backup], check=True)
                print(f"✓ Hosts file backed up for user {self.username}")
            except subprocess.CalledProcessError as e:
                print(f"Error backing up hosts file: {e}")
                return False
        return True
    
    def get_active_window_title(self):
        """Get title of currently active window"""
        # In test mode, simulate educational activity
        if self.config.get("test_mode", False):
            import random
            educational_activities = [
                "Khan Academy - Algebra Basics - https://www.khanacademy.org/math/algebra",
                "Coursera - Python Programming - https://www.coursera.org/learn/python",
                "edX - Introduction to Computer Science - https://www.edx.org/course/introduction-computer-science",
                "CodeAcademy - Learn JavaScript - https://www.codecademy.com/learn/introduction-to-javascript"
            ]
            return random.choice(educational_activities)
        
        try:
            # Try Linux method first (xdotool)
            result = subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Fallback: check running processes for browsers
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['name'] and any(browser in proc.info['name'].lower() 
                                           for browser in ['firefox', 'chrome', 'chromium', 'brave']):
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline:
                        for arg in cmdline:
                            if 'http' in arg.lower():
                                return arg
        except Exception:
            pass
        
        return None
    
    def extract_url_from_title(self, window_title):
        """Extract URL from window title or activity description"""
        if not window_title:
            return None
        
        import re
        
        # Look for URLs in the title
        url_pattern = r'https?://[^\s<>"\']+|www\.[^\s<>"\']+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s<>"\']*)?'
        urls = re.findall(url_pattern, window_title)
        
        if urls:
            url = urls[0]
            # Clean up the URL
            url = url.rstrip('.,;:!?)')
            # Add protocol if missing
            if not url.startswith('http'):
                url = 'https://' + url
            return url
        
        # Try to infer URL from educational site names
        title_lower = window_title.lower()
        site_mappings = {
            'khan academy': 'https://www.khanacademy.org',
            'khanacademy': 'https://www.khanacademy.org',
            'coursera': 'https://www.coursera.org',
            'edx': 'https://www.edx.org',
            'codecademy': 'https://www.codecademy.com',
            'duolingo': 'https://www.duolingo.com',
            'youtube': 'https://www.youtube.com'
        }
        
        for site_name, url in site_mappings.items():
            if site_name in title_lower:
                return url
        
        return None
    
    def record_site_visit(self, url, activity_title):
        """Record a site visit during educational activity"""
        if not url:
            return
        
        current_time = datetime.now()
        
        # Create visit record
        visit_record = {
            "url": url,
            "title": activity_title,
            "timestamp": current_time.isoformat(),
            "date": current_time.strftime("%Y-%m-%d")
        }
        
        # Add to today's visits if not already there
        if url not in self.data["sites_visited_today"]:
            self.data["sites_visited_today"].append(url)
        
        # Add to all sessions
        self.data["sites_visited_sessions"].append(visit_record)
        
        # Keep only last 100 session records to prevent file from growing too large
        if len(self.data["sites_visited_sessions"]) > 100:
            self.data["sites_visited_sessions"] = self.data["sites_visited_sessions"][-100:]
    
    def is_educational_activity(self, window_title):
        """Check if current activity is educational"""
        if not window_title:
            return False
        
        window_title_lower = window_title.lower()
        
        # Check for educational sites in browser windows
        for site in self.config["educational_sites"]:
            if site.lower() in window_title_lower:
                return True
        
        # Check for educational keywords
        educational_keywords = [
            "khan academy", "coursera", "edx", "codecademy", "duolingo",
            "learning", "tutorial", "course", "lesson", "study", "algebra", "python", "javascript"
        ]
        
        for keyword in educational_keywords:
            if keyword in window_title_lower:
                return True
        
        return False
    
    def monitor_activity(self):
        """Monitor user activity and track educational time"""
        last_educational_time = None
        
        while self.is_running:
            try:
                window_title = self.get_active_window_title()
                current_time = datetime.now()
                
                if self.is_educational_activity(window_title):
                    # Extract and record URL
                    url = self.extract_url_from_title(window_title)
                    if url:
                        self.record_site_visit(url, window_title)
                    
                    if last_educational_time:
                        # Calculate time spent since last check
                        time_diff = (current_time - last_educational_time).total_seconds() / 60
                        if time_diff <= self.config["check_interval_seconds"] / 60 * 2:  # Allow some tolerance
                            self.data["time_spent_today"] += time_diff
                            self.data["total_time_spent"] += time_diff
                            self.data["last_activity"] = current_time.isoformat()
                            self.save_data()
                    
                    last_educational_time = current_time
                    print(f"📚 Educational activity detected: {window_title[:50]}...")
                    if url:
                        print(f"🌐 Site recorded: {url}")
                    print(f"⏱️  Time today: {self.data['time_spent_today']:.1f} minutes")
                else:
                    last_educational_time = None
                
                # Check if goal is met
                if self.data["time_spent_today"] >= self.config["daily_goal_minutes"]:
                    print(f"🎉 Daily goal achieved! Unblocking websites...")
                    self.unblock_websites()
                    self.data["goals_completed"] += 1
                    self.save_data()
                    break
                
                time.sleep(self.config["check_interval_seconds"])
                
            except Exception as e:
                print(f"Error in monitoring: {e}")
                time.sleep(self.config["check_interval_seconds"])
    
    def test_blocking_functionality(self):
        """Test the blocking functionality for the current user"""
        blocking_method = self.determine_blocking_method()
        print(f"🧪 Testing blocking functionality for user {self.username}")
        print(f"🔒 Using blocking method: {blocking_method}")
        
        if blocking_method == "hosts":
            return self._test_hosts_blocking()
        elif blocking_method == "browser":
            return self._test_browser_blocking()
        else:
            print(f"❌ Unknown blocking method: {blocking_method}")
            return False
    
    def _test_hosts_blocking(self):
        """Test system-wide hosts file blocking"""
        print("\n📋 Testing hosts file modification...")
        
        # Show original hosts file (last 10 lines)
        print("\n📋 Current /etc/hosts (last 10 lines):")
        try:
            result = subprocess.run(['sudo', 'tail', '-10', self.hosts_file], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(result.stdout)
            else:
                print("Could not read hosts file")
        except Exception as e:
            print(f"Error reading hosts file: {e}")
            return False
        
        # Test blocking
        print(f"\n🚫 Testing website blocking for {self.username}...")
        if self.block_websites():
            print(f"\n📋 Modified /etc/hosts (showing {self.username}'s entries):")
            try:
                user_marker = f"# Productivity Guardian - {self.username} - Blocked Sites"
                result = subprocess.run(['sudo', 'grep', '-A', '20', user_marker, self.hosts_file],
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    print(result.stdout)
                else:
                    print("No blocking entries found")
            except Exception as e:
                print(f"Error reading modified hosts file: {e}")
            
            # Test DNS resolution
            print("\n🔍 Testing DNS resolution for blocked sites:")
            for site in self.config["blocked_sites"][:3]:
                try:
                    result = subprocess.run(['nslookup', site], 
                                          capture_output=True, text=True, timeout=5)
                    print(f"  {site}: {'BLOCKED' if '127.0.0.1' in result.stdout else 'NOT BLOCKED'}")
                except Exception as e:
                    print(f"  {site}: Error testing - {e}")
            
            # Test unblocking
            print(f"\n✅ Testing website unblocking for {self.username}...")
            if self.unblock_websites():
                print("✓ Websites unblocked successfully")
                return True
            else:
                print("❌ Failed to unblock websites")
                return False
        else:
            print("❌ Failed to block websites")
            return False
    
    def _test_browser_blocking(self):
        """Test browser-specific blocking"""
        print(f"\n🌐 Testing browser-specific blocking for {self.username}...")
        
        # Test blocking
        if self.block_websites():
            print("\n📄 Created blocking configuration files:")
            
            # Show created files
            blocking_files = [
                self.config_dir / "browser_blocking.json",
                self.config_dir / "hosts_override",
                self.config_dir / "browser_extension_config.json"
            ]
            
            for file_path in blocking_files:
                if file_path.exists():
                    print(f"  ✓ {file_path}")
                    # Show first few lines of the file
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read(200)
                            print(f"    Content preview: {content[:100]}...")
                    except:
                        pass
            
            # Test unblocking
            print(f"\n✅ Testing browser unblocking for {self.username}...")
            if self.unblock_websites():
                print("✓ Browser blocking configuration removed successfully")
                return True
            else:
                print("❌ Failed to remove browser blocking configuration")
                return False
        else:
            print("❌ Failed to set up browser blocking")
            return False
    
    def status(self):
        """Show current user-specific status"""
        goal_minutes = self.config["daily_goal_minutes"]
        spent_today = self.data["time_spent_today"]
        remaining = max(0, goal_minutes - spent_today)
        blocking_method = self.determine_blocking_method()
        
        print("\n" + "="*60)
        print("📊 PRODUCTIVITY GUARDIAN STATUS")
        print("="*60)
        print(f"👤 User: {self.username}")
        print(f"📁 Config Dir: {self.config_dir}")
        print(f"📅 Date: {self.data['today']}")
        print(f"🎯 Daily Goal: {goal_minutes} minutes")
        print(f"⏱️  Time Spent Today: {spent_today:.1f} minutes")
        print(f"⏳ Time Remaining: {remaining:.1f} minutes")
        print(f"🏆 Goals Completed: {self.data['goals_completed']}")
        print(f"📈 Total Time: {self.data['total_time_spent']:.1f} minutes")
        print(f"🔒 Blocking Method: {blocking_method}")
        print(f"🧪 Test Mode: {'ON' if self.config.get('test_mode', False) else 'OFF'}")
        
        blocking_status = self.data.get("blocking_active", False)
        if remaining > 0:
            print(f"🚫 Websites are {'BLOCKED' if blocking_status else 'NOT BLOCKED'}")
            print(f"💡 Study for {remaining:.1f} more minutes to unlock!")
        else:
            print(f"✅ Websites are {'UNBLOCKED' if not blocking_status else 'BLOCKED'}")
            print(f"🎉 Congratulations! Goal achieved!")
        
        print("\n📚 Educational sites (tracked):")
        for site in self.config["educational_sites"][:5]:
            print(f"  • {site}")
        if len(self.config["educational_sites"]) > 5:
            print(f"  ... and {len(self.config['educational_sites']) - 5} more")
        
        print("\n🚫 Blocked sites:")
        for site in self.config["blocked_sites"][:5]:
            print(f"  • {site}")
        if len(self.config["blocked_sites"]) > 5:
            print(f"  ... and {len(self.config['blocked_sites']) - 5} more")
        
        # Show visited sites today
        if self.data.get("sites_visited_today"):
            print(f"\n🌐 Educational sites visited today ({len(self.data['sites_visited_today'])}):")
            for site in self.data["sites_visited_today"][:10]:  # Show up to 10
                print(f"  • {site}")
            if len(self.data["sites_visited_today"]) > 10:
                print(f"  ... and {len(self.data['sites_visited_today']) - 10} more")
        else:
            print("\n🌐 No educational sites visited today yet")
        
        print("="*60)
    
    def start(self):
        """Start the productivity guardian"""
        print(f"🛡️  Starting Productivity Guardian for user {self.username}...")
        
        # Try to acquire lock to prevent multiple instances
        if not self.acquire_lock():
            print(f"❌ Another instance is already running for user {self.username}")
            print("💡 Use 'stop' command to stop the existing instance")
            return
        
        try:
            # Check if already achieved goal today
            if self.data["time_spent_today"] >= self.config["daily_goal_minutes"]:
                print("🎉 Goal already achieved today! Websites remain unblocked.")
                self.status()
                return
            
            # Check for required tools
            if not self.check_requirements():
                return
            
            print("🚫 Blocking websites...")
            if not self.block_websites():
                print("❌ Failed to block websites. Continuing with monitoring only.")
                print("💡 You can still track educational time without blocking")
            
            self.is_running = True
            print("👀 Starting activity monitor...")
            print("💡 Focus on educational content to unlock websites!")
            
            # Start monitoring in a separate thread
            self.monitor_thread = threading.Thread(target=self.monitor_activity)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            
            try:
                # Keep main thread alive
                while self.is_running:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stop()
        
        finally:
            # Always release the lock
            self.release_lock()
    
    def stop(self):
        """Stop the productivity guardian"""
        print(f"\n🛑 Stopping Productivity Guardian for user {self.username}...")
        self.is_running = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        # Unblock websites and clean up
        if self.unblock_websites():
            print("✅ Websites unblocked successfully")
        else:
            print("⚠️  Warning: Failed to unblock websites completely")
        
        # Release lock
        self.release_lock()
        
        print(f"👋 Goodbye, {self.username}!")
    
    def check_requirements(self):
        """Check if required tools are installed based on blocking method"""
        blocking_method = self.determine_blocking_method()
        
        # For Linux window detection
        if sys.platform.startswith('linux'):
            required_tools = ['xdotool']
            missing_tools = []
            
            for tool in required_tools:
                if subprocess.run(['which', tool], capture_output=True).returncode != 0:
                    missing_tools.append(tool)
            
            if missing_tools:
                print(f"⚠️  Missing window detection tools: {', '.join(missing_tools)}")
                print("📦 Install with: sudo apt install xdotool")
                if not self.config.get("test_mode", False):
                    print("💡 Window detection may not work properly")
        
        # Check requirements based on blocking method
        if blocking_method == "hosts":
            # Check sudo privileges for hosts file modification
            try:
                subprocess.run(['sudo', '-n', 'true'], check=True, capture_output=True)
                print("✅ Sudo privileges available - using system-wide hosts file blocking")
            except subprocess.CalledProcessError:
                print("⚠️  No sudo privileges - falling back to browser-specific blocking")
                self.config["blocking_method"] = "browser"
                self.save_config()
        
        elif blocking_method == "browser":
            print("🌐 Using browser-specific blocking method")
            print("💡 For full blocking effectiveness, consider installing browser extensions")
        
        return True
    
    def show_site_history(self):
        """Show detailed site visit history"""
        print("\n" + "="*60)
        print("🌐 EDUCATIONAL SITE VISIT HISTORY")
        print("="*60)
        
        # Today's unique sites
        today_sites = self.data.get("sites_visited_today", [])
        print(f"📅 Today ({self.data['today']}) - {len(today_sites)} unique sites:")
        for site in today_sites:
            print(f"  • {site}")
        
        # Recent sessions with timestamps
        sessions = self.data.get("sites_visited_sessions", [])
        if sessions:
            print(f"\n📊 Recent Sessions ({len(sessions)} total):")
            
            # Group by date
            sessions_by_date = {}
            for session in sessions[-20:]:  # Show last 20 sessions
                date = session.get("date", "Unknown")
                if date not in sessions_by_date:
                    sessions_by_date[date] = []
                sessions_by_date[date].append(session)
            
            # Display by date (most recent first)
            for date in sorted(sessions_by_date.keys(), reverse=True):
                print(f"\n  📅 {date}:")
                for session in sessions_by_date[date]:
                    timestamp = session.get("timestamp", "")
                    time_str = timestamp.split("T")[1][:8] if "T" in timestamp else ""
                    url = session.get("url", "Unknown")
                    title = session.get("title", "")[:50] + "..." if len(session.get("title", "")) > 50 else session.get("title", "")
                    print(f"    {time_str} - {url}")
                    if title and title != url:
                        print(f"      └─ {title}")
        else:
            print("\n📊 No session history yet")
        
        print("="*60)
    
    def signal_handler(self, signum, frame):
        """Handle termination signals"""
        print(f"\n🔔 Received signal {signum} for user {self.username}")
        self.stop()
        sys.exit(0)

def show_multi_user_info():
    """Show information about multi-user functionality"""
    print("\n" + "="*70)
    print("👥 MULTI-USER PRODUCTIVITY GUARDIAN INFORMATION")
    print("="*70)
    
    current_user = getpass.getuser()
    home_dir = Path.home()
    config_dir = home_dir / ".productivity_guardian"
    
    print(f"👤 Current User: {current_user}")
    print(f"📁 Your Config Directory: {config_dir}")
    
    # Check if user has data
    data_file = config_dir / "guardian_data.json"
    config_file = config_dir / "config.json"
    
    if data_file.exists() or config_file.exists():
        print(f"📊 You have existing productivity data:")
        if config_file.exists():
            print(f"  ✓ Configuration file: {config_file}")
        if data_file.exists():
            print(f"  ✓ Data file: {data_file}")
    else:
        print(f"📊 No existing data found for user {current_user}")
    
    print("\n🔄 Multi-User Features:")
    print("  • Each user has separate configuration and data")
    print("  • Users can run simultaneously without conflicts")
    print("  • File locking prevents multiple instances per user")
    print("  • Supports both system-wide and user-specific blocking")
    
    print("\n🔒 Blocking Methods:")
    print("  • AUTO: Automatically chooses best method")
    print("  • HOSTS: System-wide blocking (requires sudo)")
    print("  • BROWSER: User-specific blocking (no sudo needed)")
    
    print("\n💡 Usage Tips:")
    print("  • Users with sudo: Full system-wide blocking")
    print("  • Users without sudo: Browser-specific blocking")
    print("  • Each user tracks their own educational progress")
    print("  • Multiple users can have different goals and sites")
    
    # Try to detect other users
    print("\n🔍 Detecting Other Users:")
    try:
        all_users_home = Path("/home")
        if all_users_home.exists():
            users_with_guardian = []
            for user_home in all_users_home.iterdir():
                if user_home.is_dir():
                    user_config_dir = user_home / ".productivity_guardian"
                    if user_config_dir.exists():
                        users_with_guardian.append(user_home.name)
            
            if users_with_guardian:
                print(f"  Found {len(users_with_guardian)} users with Productivity Guardian:")
                for user in users_with_guardian:
                    print(f"    • {user}")
            else:
                print("  No other users found with Productivity Guardian")
        else:
            print("  Cannot detect other users (not on Linux system)")
    except Exception as e:
        print(f"  Could not detect other users: {e}")
    
    print("="*70)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 productivity_guardian.py [start|stop|status|config|test|sites|users]")
        print("\nCommands:")
        print("  start  - Start blocking websites and monitoring activity")
        print("  stop   - Stop blocking and restore access")
        print("  status - Show current progress and configuration")
        print("  config - Show configuration files and directories")
        print("  test   - Test blocking functionality")
        print("  sites  - Show detailed history of educational sites visited")
        print("  users  - Show information about multiple user setups")
        sys.exit(1)
    
    try:
        guardian = ProductivityGuardian()
        command = sys.argv[1].lower()
        
        if command == "start":
            guardian.start()
        elif command == "stop":
            guardian.stop()
        elif command == "status":
            guardian.status()
        elif command == "config":
            print(f"👤 User: {guardian.username}")
            print(f"📁 Config directory: {guardian.config_dir}")
            print(f"📄 Config file: {guardian.config_file}")
            print(f"📊 Data file: {guardian.data_file}")
            print(f"🔒 Lock file: {guardian.lock_file}")
            print(f"🌐 Blocking method: {guardian.determine_blocking_method()}")
            print()
            guardian.status()
        elif command == "test":
            guardian.test_blocking_functionality()
        elif command == "sites":
            guardian.show_site_history()
        elif command == "users":
            show_multi_user_info()
        else:
            print(f"❌ Unknown command: {command}")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
