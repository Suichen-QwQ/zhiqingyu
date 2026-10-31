#!/bin/bash
# 后端启动脚本（Linux/Mac）
cd "$(dirname "$0")/../prototype-backend"

if [ ! -d "venv" ]; then
    echo "警告: 虚拟环境不存在，请先运行 scripts/setup-backend.sh"
    exit 1
fi

# shellcheck disable=SC1091
source venv/bin/activate
echo "启动后端服务... http://127.0.0.1:8000"
python -m app.main
