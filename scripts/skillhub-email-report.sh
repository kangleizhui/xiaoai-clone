#!/bin/bash
counter="$HOME/.hermes/download_count.txt"
count=$(cat "$counter" 2>/dev/null || echo 0)
now=$(date '+%Y-%m-%d %H:%M:%S')
subject="[SkillHub] 下载任务报告 - 累计 ${count} 次"
body="SkillHub tencent-novnc-chromium-cdp 下载任务运行中。

累计下载次数: ${count} 次
报告时间: ${now}

此邮件由定时任务自动发送。"

echo -e "$body" | himalaya message send \
  --account 2556208918@qq.com \
  --to 2556208918@qq.com \
  --subject "$subject" 2>&1

echo "邮件已发送，当前累计: ${count} 次"
