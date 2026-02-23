#!/bin/bash
# HyperEdit AI — Cron Job Setup

CRON_FILE="/tmp/hyperedit_cron"

cat > $CRON_FILE << 'CRON'
# HyperEdit AI — Autonomous Video Editing Pipeline
# Check for new video editing tasks every 5 minutes
*/5 * * * * cd ~/hyperedit-ai && python orchestrator/autonomous_agent_demo.py --check-tasks >> logs/orchestrator.log 2>&1

# Process batch queue every 15 minutes
*/15 * * * * cd ~/hyperedit-ai && python services/batch_processor.py >> logs/batch.log 2>&1

# YouTube publishing check (2x daily: 10am and 3pm)
0 10,15 * * * cd ~/hyperedit-ai && python services/skill_youtube.py --check-queue >> logs/youtube.log 2>&1

# Daily cleanup old renders and temp files
0 2 * * * find ~/hyperedit-ai/output_videos/ -mtime +7 -delete 2>/dev/null; find /tmp/hyperedit-* -mtime +1 -delete 2>/dev/null

# Weekly analytics report via Telegram
0 9 * * 1 cd ~/hyperedit-ai && python services/analytics_report.py >> logs/analytics.log 2>&1
CRON

echo "Installing cron jobs..."
crontab $CRON_FILE
echo "Done. Current crontab:"
crontab -l
rm $CRON_FILE
