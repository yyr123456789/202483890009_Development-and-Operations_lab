#!/usr/bin/bash
#
# monitoring.sh - enhanced monitoring for the Assignment 1 web server.
#
# Based on the sample script supplied with the module, with additional
# checks: uptime/load, disk usage, swap, TCP connections, web server HTTP
# response, top CPU processes and failed SSH logins.
#
# Tested on Amazon Linux 2023.
#
# Exit code: 0 if the web server is running and healthy, 1 otherwise.

# ---------------------------------------------------------------------------
# Instance metadata (IMDSv2 - a session token is required first)
# ---------------------------------------------------------------------------
TOKEN=`curl -s -X PUT "http://169.254.169.254/latest/api/token" \
       -H "X-aws-ec2-metadata-token-ttl-seconds: 21600"`

meta() {
    curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
         "http://169.254.169.254/latest/meta-data/$1"
}

INSTANCE_ID=$(meta instance-id)
INSTANCE_TYPE=$(meta instance-type)
AVAILABILITY_ZONE=$(meta placement/availability-zone)
PRIVATE_IP=$(meta local-ipv4)

# ---------------------------------------------------------------------------
# Original checks
# ---------------------------------------------------------------------------
MEMORYUSAGE=$(free -m | awk 'NR==2{printf "%.2f%%", $3*100/$2 }')
PROCESSES=$(ps -A --no-headers | wc -l)
HTTPD_PROCESSES=$(pgrep -c httpd 2>/dev/null || echo 0)

# ---------------------------------------------------------------------------
# Additional checks
# ---------------------------------------------------------------------------
UPTIME=$(uptime -p 2>/dev/null || cut -d. -f1 /proc/uptime)
LOADAVG=$(awk '{printf "%s %s %s", $1, $2, $3}' /proc/loadavg)
CPUCOUNT=$(nproc)

DISKUSAGE=$(df -h / | awk 'NR==2{print $5" used ("$4" free)"}')

SWAPUSAGE=$(free -m | awk 'NR==3{ if ($2 > 0) printf "%.2f%% (%sMB of %sMB)", $3*100/$2, $3, $2; else print "no swap" }')

TCPCONNECTIONS=$(ss -tan 2>/dev/null | grep -c ESTAB)
LISTENING=$(ss -tln 2>/dev/null | grep -c LISTEN)

HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://localhost/ 2>/dev/null)

FAILED_SSH=$(grep -c "Failed password" /var/log/secure 2>/dev/null || echo 0)

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
echo "=============================================================="
echo " Monitoring report      $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "=============================================================="
echo "Instance ID          : $INSTANCE_ID"
echo "Instance type        : $INSTANCE_TYPE"
echo "Availability zone    : $AVAILABILITY_ZONE"
echo "Private IP address   : $PRIVATE_IP"
echo "--------------------------------------------------------------"
echo "Uptime               : $UPTIME"
echo "Load average         : $LOADAVG  (${CPUCOUNT} vCPU)"
echo "Memory utilisation   : $MEMORYUSAGE"
echo "Swap utilisation     : $SWAPUSAGE"
echo "Disk usage (/)       : $DISKUSAGE"
echo "--------------------------------------------------------------"
echo "No of processes      : $PROCESSES"
echo "TCP connections      : $TCPCONNECTIONS established, $LISTENING listening"
echo "Failed SSH logins    : $FAILED_SSH"
echo "--------------------------------------------------------------"
echo "HTTP status (/)      : $HTTP_CODE"
echo "httpd processes      : $HTTPD_PROCESSES"
echo "--------------------------------------------------------------"
echo "Top 3 processes by CPU:"
ps -eo pcpu,pid,comm --sort=-pcpu | head -4 | tail -3 | \
    awk '{printf "  %5s%%  pid %-6s %s\n", $1, $2, $3}'
echo "=============================================================="

# ---------------------------------------------------------------------------
# Health check - the web server must be running and answering
# ---------------------------------------------------------------------------
if [ "$HTTPD_PROCESSES" -ge 1 ] && [ "$HTTP_CODE" = "200" ]; then
    echo "Web server is running"
    echo "RESULT: OK"
    exit 0
else
    echo "Web server is NOT running correctly"
    echo "RESULT: FAILED"
    exit 1
fi
