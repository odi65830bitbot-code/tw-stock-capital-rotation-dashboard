#!/bin/zsh
# 取得目前腳本所在目錄
DIR="/Users/maxyu/Documents/台股資金網站/web"

echo "=========================================="
echo "   正在為您一鍵啟動「台股資金輪動大師」網頁   "
echo "=========================================="

# 1. 關閉先前可能殘留佔用 port 3000 和 5173 的程序
echo "🧹 正在清理可能殘留的舊伺服器程序..."
lsof -ti :3000 | xargs kill -9 2>/dev/null || true
lsof -ti :5173 | xargs kill -9 2>/dev/null || true
sleep 1

# 2. 切換到網頁目錄
cd "$DIR"

# 3. 啟動 Node.js 後端服務（背景執行）
echo "🚀 正在背景啟動 Express 後端服務 (Port 3000)..."
nohup node server.js > /tmp/tw_stock_backend.log 2>&1 &
sleep 2

# 4. 啟動 Vite 前端服務（背景執行）
echo "🚀 正在背景啟動 Vite 前端開發伺服器 (Port 5173)..."
nohup npm run dev > /tmp/tw_stock_frontend.log 2>&1 &
sleep 3

# 5. 自動打開瀏覽器
echo "🌐 正在為您打開網頁瀏覽器..."
open "http://127.0.0.1:5173/"

echo "=========================================="
echo "🎉 一鍵啟動完成！"
echo "您可以點擊書籤，或直接在彈出的瀏覽器中開始使用。"
echo "若要結束服務，直接在 Terminal 執行：killall node"
echo "=========================================="
sleep 2
exit 0
