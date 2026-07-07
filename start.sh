#!/bin/bash

# Khởi chạy Go API proxy (gemini-web-to-api) ở background
# Server này sẽ tự động lắng nghe cổng 4981 theo mặc định
echo "========================================="
echo "Starting Go Gemini Web-to-API proxy on port 4981..."
echo "========================================="
PORT=4981 ./gemini-web-to-api &
# Chờ 5 giây cho Go proxy khởi chạy hoàn tất
sleep 5

# Kiểm tra xem Go proxy có phản hồi không
echo "Checking Go proxy health..."
curl -s http://localhost:4981/health || echo "Go proxy is starting up..."

# Khởi chạy Python Trading Bot ở foreground
# Render tự động cấp biến PORT, nếu không có mặc định là 10000
PORT_NUM=${PORT:-10000}
echo "========================================="
echo "Starting Trading Bot Server on port $PORT_NUM..."
echo "========================================="
exec uvicorn main:app --host 0.0.0.0 --port $PORT_NUM
