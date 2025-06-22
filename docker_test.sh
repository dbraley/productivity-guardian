#!/bin/bash

echo "🐳 Productivity Guardian Docker Test Suite"
echo "=========================================="

# Function to show menu
show_menu() {
    echo ""
    echo "Choose a test to run:"
    echo "1. Quick test (automated sequence)"
    echo "2. Manual hosts file test"
    echo "3. Manual guardian start"
    echo "4. Show status"
    echo "5. Show current hosts file"
    echo "6. Test DNS resolution"
    echo "7. Stop guardian"
    echo "8. Exit"
    echo ""
}

# Function to test DNS resolution
test_dns() {
    echo "🔍 Testing DNS resolution for blocked sites:"
    echo "Before blocking:"
    nslookup youtube.com | head -5
    
    echo ""
    echo "Blocking sites..."
    python3 productivity_guardian.py test
    
    echo ""
    echo "After blocking:"
    nslookup youtube.com | head -5
    
    echo ""
    echo "Unblocking sites..."
    python3 productivity_guardian.py stop
}

# Function to show hosts file
show_hosts() {
    echo "📋 Current /etc/hosts file:"
    echo "------------------------"
    sudo cat /etc/hosts
    echo "------------------------"
}

# Function to manual test
manual_test() {
    echo "🔧 Starting manual hosts file test..."
    echo "This will show you the hosts file before and after modification"
    
    echo ""
    echo "BEFORE blocking:"
    sudo tail -10 /etc/hosts
    
    echo ""
    echo "Blocking websites..."
    python3 productivity_guardian.py test
    
    echo ""
    echo "AFTER blocking:"
    sudo tail -10 /etc/hosts
}

# Main loop
while true; do
    show_menu
    read -p "Enter your choice (1-8): " choice
    
    case $choice in
        1)
            echo "🚀 Running automated test sequence..."
            python3 test_runner.py
            ;;
        2)
            manual_test
            ;;
        3)
            echo "🛡️ Starting Productivity Guardian manually..."
            echo "Press Ctrl+C to stop"
            python3 productivity_guardian.py start
            ;;
        4)
            python3 productivity_guardian.py status
            ;;
        5)
            show_hosts
            ;;
        6)
            test_dns
            ;;
        7)
            python3 productivity_guardian.py stop
            ;;
        8)
            echo "👋 Goodbye!"
            exit 0
            ;;
        *)
            echo "❌ Invalid choice. Please try again."
            ;;
    esac
    
    echo ""
    read -p "Press Enter to continue..."
done
