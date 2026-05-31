#!/bin/bash
slug="tencent-novnc-chromium-cdp"
dir="$HOME/.openclaw/workspace/skills/$slug"
counter="$HOME/.hermes/download_count.txt"

# 下载
output=$(skillhub install "$slug" --dir ~/.openclaw/workspace/skills 2>&1)
echo "$output"

# 删除
rm -rf "$dir"
echo "已删除 $dir"

# 计数
count=$(cat "$counter" 2>/dev/null || echo 0)
count=$((count + 1))
echo "$count" > "$counter"
echo "累计下载: $count 次"
