#!/bin/bash
# 前端构建/依赖安装脚本（Linux/Mac）
set -e
cd "$(dirname "$0")/../prototype-frontend"

echo "开始设置前端环境..."

if ! command -v node &> /dev/null; then
    echo "错误: 未找到 Node.js，请先安装 Node.js 24+"
    exit 1
fi
echo "Node.js 版本: $(node --version)"

if ! command -v pnpm &> /dev/null; then
    echo "安装 pnpm..."
    npm install -g pnpm
fi

echo "安装前端依赖..."
pnpm install --frozen-lockfile

if [ "$1" == "build" ]; then
    echo "构建生产版本..."
    pnpm run build
    echo "构建完成。"
else
    echo "完成。启动开发服务器：scripts/start-frontend.sh"
fi
