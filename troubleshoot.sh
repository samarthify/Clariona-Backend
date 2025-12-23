#!/bin/bash

# Clariti Cycle Runner - Automated Troubleshooting Script
# Usage: ./troubleshoot.sh

echo "======================================"
echo "Clariti Cycle Runner Diagnostics"
echo "======================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
        return 0
    else
        echo -e "${RED}✗${NC} $2"
        return 1
    fi
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# 1. Check PM2 processes
echo "1. Checking PM2 Processes..."
PM2_API=$(pm2 list | grep "clariti-python-api" | grep "online")
PM2_CYCLES=$(pm2 list | grep "clariti-cycles" | grep "online")

if [ ! -z "$PM2_API" ]; then
    check_status 0 "Python API is running"
else
    check_status 1 "Python API is NOT running"
    echo "   Fix: pm2 restart clariti-python-api"
fi

if [ ! -z "$PM2_CYCLES" ]; then
    check_status 0 "Cycle runner is running"
else
    check_status 1 "Cycle runner is NOT running"
    echo "   Fix: pm2 start clariti-cycles"
fi
echo ""

# 2. Check API health
echo "2. Checking API Health..."
API_HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null)
if [ ! -z "$API_HEALTH" ]; then
    check_status 0 "API is responding"
else
    check_status 1 "API is NOT responding"
    echo "   Fix: pm2 restart clariti-python-api"
fi
echo ""

# 3. Check continuous_mode setting
echo "3. Checking Configuration..."
CONTINUOUS_MODE=$(cat config/agent_config.json | grep continuous_mode | grep -o "true\|false")
if [ "$CONTINUOUS_MODE" = "false" ]; then
    check_status 0 "continuous_mode is false (correct)"
else
    check_status 1 "continuous_mode is true (WRONG!)"
    echo "   Fix: Edit config/agent_config.json and set continuous_mode to false"
    echo "        Then: pm2 restart clariti-python-api"
fi
echo ""

# 4. Check for recent cycle activity
echo "4. Checking Recent Cycle Activity..."
RECENT_CYCLE=$(tail -n 50 logs/automatic_scheduling.log | grep "CYCLE START" | tail -1)
if [ ! -z "$RECENT_CYCLE" ]; then
    CYCLE_TIME=$(echo "$RECENT_CYCLE" | grep -oP '\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')
    check_status 0 "Recent cycle detected at $CYCLE_TIME"
    
    # Check if it completed
    CYCLE_END=$(tail -n 50 logs/automatic_scheduling.log | grep "CYCLE END" | tail -1)
    if [ ! -z "$CYCLE_END" ]; then
        END_TIME=$(echo "$CYCLE_END" | grep -oP '\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')
        echo -e "${GREEN}✓${NC} Cycle completed at $END_TIME"
    else
        warn "Cycle may still be running or failed"
        CYCLE_FAILED=$(tail -n 50 logs/automatic_scheduling.log | grep "CYCLE ABORTED\|Collection failed" | tail -1)
        if [ ! -z "$CYCLE_FAILED" ]; then
            echo -e "${RED}✗${NC} Cycle failed: $CYCLE_FAILED"
        fi
    fi
else
    warn "No recent cycle activity found"
fi
echo ""

# 5. Check for multiple running collectors
echo "5. Checking for Multiple Running Cycles..."
RECENT_COLLECTORS=$(ls -t logs/collectors/all_collectors_*.log 2>/dev/null | head -3)
RUNNING_COUNT=0

for log in $RECENT_COLLECTORS; do
    # Get file modification time
    MOD_TIME=$(stat -c %Y "$log" 2>/dev/null)
    CURRENT_TIME=$(date +%s)
    TIME_DIFF=$((CURRENT_TIME - MOD_TIME))
    
    if [ $TIME_DIFF -lt 600 ]; then  # Modified in last 10 minutes
        RUNNING_COUNT=$((RUNNING_COUNT + 1))
    fi
done

if [ $RUNNING_COUNT -eq 0 ]; then
    warn "No active collectors detected"
elif [ $RUNNING_COUNT -eq 1 ]; then
    check_status 0 "ONE active collector log (correct)"
else
    check_status 1 "MULTIPLE active collectors detected ($RUNNING_COUNT)"
    echo "   This indicates overlapping cycles!"
    echo "   Fix: pm2 restart clariti-python-api && sleep 10 && pm2 start clariti-cycles"
fi
echo ""

# 6. Check for stuck locks
echo "6. Checking for Stuck Locks..."
STUCK_LOCKS=$(grep "Agent is already busy" logs/pm2-error.log 2>/dev/null | tail -5 | wc -l)
if [ $STUCK_LOCKS -eq 0 ]; then
    check_status 0 "No stuck locks detected"
else
    warn "Found $STUCK_LOCKS recent lock warnings"
    echo "   This is normal if cycles are running sequentially"
    echo "   Problem ONLY if no cycles are actually running"
fi
echo ""

# 7. Check disk space
echo "7. Checking Disk Space..."
DISK_USAGE=$(df -h /home/ubuntu/Clariti-1.0 | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $DISK_USAGE -lt 80 ]; then
    check_status 0 "Disk space OK (${DISK_USAGE}% used)"
elif [ $DISK_USAGE -lt 90 ]; then
    warn "Disk space getting low (${DISK_USAGE}% used)"
else
    check_status 1 "Disk space critical (${DISK_USAGE}% used)"
    echo "   Fix: Clean up old logs or increase disk space"
fi
echo ""

# 8. Check memory
echo "8. Checking Memory..."
MEM_USAGE=$(free | grep Mem | awk '{printf("%.0f", $3/$2 * 100)}')
if [ $MEM_USAGE -lt 80 ]; then
    check_status 0 "Memory OK (${MEM_USAGE}% used)"
elif [ $MEM_USAGE -lt 90 ]; then
    warn "Memory getting high (${MEM_USAGE}% used)"
else
    check_status 1 "Memory critical (${MEM_USAGE}% used)"
    echo "   Fix: Restart processes: pm2 restart all"
fi
echo ""

# Summary
echo "======================================"
echo "Summary & Recommendations"
echo "======================================"

# Check if everything is healthy
ISSUES=0

if [ -z "$PM2_API" ] || [ -z "$PM2_CYCLES" ]; then
    echo -e "${RED}• Processes not running${NC}"
    echo "  Run: pm2 start clariti-cycles"
    ISSUES=$((ISSUES + 1))
fi

if [ "$CONTINUOUS_MODE" != "false" ]; then
    echo -e "${RED}• continuous_mode is true (should be false)${NC}"
    echo "  Edit: config/agent_config.json"
    ISSUES=$((ISSUES + 1))
fi

if [ $RUNNING_COUNT -gt 1 ]; then
    echo -e "${RED}• Multiple overlapping cycles detected${NC}"
    echo "  Run: pm2 restart clariti-python-api && sleep 10 && pm2 restart clariti-cycles"
    ISSUES=$((ISSUES + 1))
fi

if [ $DISK_USAGE -gt 90 ]; then
    echo -e "${RED}• Disk space critical${NC}"
    echo "  Run: cd logs/collectors && rm all_collectors_*.log (keep recent 5)"
    ISSUES=$((ISSUES + 1))
fi

if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}✓ System appears healthy!${NC}"
    echo ""
    echo "Current Status:"
    pm2 list | grep "clariti"
    echo ""
    echo "Recent Activity:"
    tail -n 5 logs/automatic_scheduling.log | grep "CYCLE\|PHASE"
else
    echo -e "${YELLOW}⚠ Found $ISSUES issue(s) that need attention${NC}"
fi

echo ""
echo "For detailed logs, run:"
echo "  pm2 logs clariti-cycles --lines 50"
echo ""
echo "For full documentation, see:"
echo "  CYCLE_RUNNER_DOCUMENTATION.md"
echo ""







