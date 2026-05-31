#!/bin/bash
# 小艾自动同步备份脚本（cron 调用）
# 显式 PATH，cron 环境默认不包含 git 等
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root

LOG=/var/log/xiaoai-sync.log
echo "===== $(date '+%F %T') 开始同步 =====" >> "$LOG"
bash /root/projects/hermes-clone-of-xiaoai/scripts/sync.sh --quiet >> "$LOG" 2>&1
RC=$?
echo "===== $(date '+%F %T') 结束 exit=$RC =====" >> "$LOG"
exit $RC
