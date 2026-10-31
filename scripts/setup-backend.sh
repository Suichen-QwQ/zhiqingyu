#!/bin/bash
# 后端环境初始化脚本（Linux/Mac）
set -e
cd "$(dirname "$0")/../prototype-backend"

echo "开始设置后端环境..."

if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3.11+"
    exit 1
fi
echo "Python 版本: $(python3 --version 2>&1 | awk '{print $2}')"

if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate
echo "升级 pip..."
pip install --upgrade pip
echo "安装 Python 依赖..."
pip install -r requirements.txt

echo "完成。启动：scripts/start-backend.sh"
