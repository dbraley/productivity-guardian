# Productivity Guardian - Docker Test Environment

A proof-of-concept productivity control system that blocks distracting websites until educational goals are completed.

## 🚀 Quick Start with Docker

### 1. Build the Docker Image

```bash
docker build -t productivity-guardian .
```

### 2. Run the Container

```bash
docker run -it --rm productivity-guardian
```

### 3. Run Tests

Once inside the container, you have several options:

**Option A: Run the interactive test menu**
```bash
./docker_test.sh
```

**Option B: Run automated test sequence**
```bash
python3 test_runner.py
```

**Option C: Manual testing**
```bash
# Check status
python3 productivity_guardian.py status

# Test hosts file modification
python3 productivity_guardian.py test

# Start the guardian (with simulated activity)
python3 productivity_guardian.py start
```

## 🧪 What the Tests Do

### Automated Test Sequence
1. **Configuration Test**: Creates a test config with 2-minute goal
2. **Status Check**: Shows initial system status
3. **Hosts File Test**: Tests website blocking/unblocking
4. **Activity Monitor**: Runs for 30 seconds with simulated educational activity
5. **Final Status**: Shows updated progress

### Interactive Menu Options
1. **Quick test**: Full automated sequence
2. **Manual hosts test**: Step-by-step hosts file modification
3. **Manual guardian start**: Start the guardian manually
4. **Show status**: Current progress and configuration
5. **Show hosts file**: View current /etc/hosts content
6. **Test DNS resolution**: Before/after DNS lookup test
7. **Stop guardian**: Emergency stop and cleanup

## 🔍 Key Features Tested

### ✅ Website Blocking
- Modifies `/etc/hosts` to redirect blocked sites to localhost
- Creates backup and restores original file
- Tests DNS resolution changes

### ✅ Activity Monitoring
- In test mode: Simulates educational activity
- In real mode: Monitors window titles for educational content
- Tracks time spent on educational sites

### ✅ Goal Management
- Configurable daily time goals
- Persistent progress tracking
- Automatic unblocking when goals are met

### ✅ System Integration
- Sudo privilege checking
- Signal handling for clean shutdown
- Configuration management

## 📋 Test Configuration

The test environment uses these settings:
- **Goal**: 2 minutes (for quick testing)
- **Check interval**: 10 seconds
- **Test mode**: ON (simulates educational activity)
- **Blocked sites**: YouTube, Facebook, Reddit, Twitter, etc.
- **Educational sites**: Khan Academy, Coursera, edX, CodeAcademy

## 🛠️ For Ubuntu Production Use

To use this on a real Ubuntu system:

1. **Install dependencies:**
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip xdotool
   pip3 install psutil
   ```

2. **Configure:**
   ```bash
   # Edit config.json to set:
   # - "test_mode": false
   # - "daily_goal_minutes": 30 (or desired time)
   # - Add/remove blocked/educational sites as needed
   ```

3. **Run:**
   ```bash
   sudo python3 productivity_guardian.py start
   ```

## ⚠️ Important Notes

- **Requires sudo privileges** for hosts file modification
- **Test mode** simulates educational activity for demo purposes
- **Real mode** requires GUI environment and active window detection
- **Backup created** automatically before modifying hosts file
- **Clean shutdown** restores original hosts file

## 🔧 Customization

Edit `config.json` to customize:
- Blocked websites list
- Educational websites list
- Daily goal in minutes
- Check interval
- Redirect IP address

## 🐛 Troubleshooting

If you encounter issues:

1. **Permission errors**: Make sure you're running with sudo
2. **Missing tools**: Install xdotool with `sudo apt install xdotool`
3. **Hosts file issues**: Check if backup exists at `/etc/hosts.guardian_backup`
4. **Clean up**: Run `python3 productivity_guardian.py stop` to restore hosts file

## 📝 License

This is a proof-of-concept for educational purposes.
