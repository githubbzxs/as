#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=${1:-/opt/grvt-mm}
cd "$ROOT_DIR"

echo "[1/5] 拉取代码"
git pull --rebase

echo "[2/5] 构建前端"
cd frontend
npm ci
npm run build

cd ../backend
echo "[3/5] 安装后端依赖"
python -m pip install -r requirements.txt

echo "[4/5] 重启服务"
systemctl restart grvt-mm

echo "[5/5] 健康检查"
systemctl is-active --quiet grvt-mm && echo "service: active"
ss -ltnp | grep 18081
curl -fsS http://127.0.0.1:18081/healthz && echo

