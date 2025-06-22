#!/usr/bin/env python3
"""
Test runner for Productivity Guardian in Docker environment
"""

import json
import subprocess
import time
import sys

def create_test_config():
    """Create a test configuration with shorter goal time"""
    config = {
        "blocked_sites": [
            "youtube.com",
            "www.youtube.com",
            "facebook.com",
            "www.facebook.com",
            "reddit.com",
            "www.reddit.com"
        ],
        "educational_sites": [
            "khanacademy.org",
            "www.khanacademy.org",
            "coursera.org",
            "www.coursera.org"
        ],
        "daily_goal_minutes": 2,  # Short goal for testing
        "check_interval_seconds": 10,  # Quick checks for testing
        "redirect_ip": "127.0.0.1",
        "test_mode": True  # Enable test mode
    }
    
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print("✓ Created test configuration")
    print(f"  Goal: {config['daily_goal_minutes']} minutes")
    print(f"  Check interval: {config['check_interval_seconds']} seconds")
    print(f"  Test mode: {config['test_mode']}")

def run_test_sequence():
    """Run a complete test sequence"""
    print("🧪 Starting Productivity Guardian Test Sequence")
    print("=" * 50)
    
    # Create test config
    create_test_config()
    
    # Test 1: Check status
    print("\n📋 Test 1: Checking initial status...")
    result = subprocess.run(['python3', 'productivity_guardian.py', 'status'], 
                          capture_output=True, text=True)
    print(result.stdout)
    
    # Test 2: Test hosts file modification
    print("\n🔧 Test 2: Testing hosts file modification...")
    result = subprocess.run(['python3', 'productivity_guardian.py', 'test'], 
                          capture_output=True, text=True)
    print(result.stdout)
    
    # Test 3: Start guardian for a short time
    print("\n🚀 Test 3: Starting guardian (will run for 30 seconds)...")
    print("In test mode, it will simulate educational activity")
    
    try:
        # Start the guardian process
        process = subprocess.Popen(['python3', 'productivity_guardian.py', 'start'],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, bufsize=1, universal_newlines=True)
        
        # Let it run for 30 seconds
        start_time = time.time()
        while time.time() - start_time < 30:
            line = process.stdout.readline()
            if line:
                print(line.strip())
            if process.poll() is not None:
                break
            time.sleep(0.1)
        
        # Terminate if still running
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
        if process.poll() is None:
            process.terminate()
    
    # Test 4: Final status check
    print("\n📊 Test 4: Final status check...")
    result = subprocess.run(['python3', 'productivity_guardian.py', 'status'], 
                          capture_output=True, text=True)
    print(result.stdout)
    
    # Test 5: Manual stop
    print("\n🛑 Test 5: Manual stop...")
    result = subprocess.run(['python3', 'productivity_guardian.py', 'stop'], 
                          capture_output=True, text=True)
    print(result.stdout)
    
    print("\n✅ Test sequence completed!")

if __name__ == "__main__":
    run_test_sequence()
