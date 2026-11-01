#!/bin/bash
# 前端启动脚本（Linux/Mac）
set -e
cd "$(dirname "$0")/../prototype-frontend"

if [ ! -d "node_modules" ]; then
    echo "警告: node_modules 不存在，请先运行 scripts/setup-frontend.sh"
    exit 1
fi

echo "启动前端开发服务器... http://127.0.0.1:5525"
pnpm run dev
