# Stage 1: Build gemini-web-to-api (Go Service)
FROM golang:alpine AS go-builderWORKDIR /app
# Cài đặt git để clone repo
RUN apk add --no-cache git
# Clone mã nguồn gemini-web-to-api
RUN git clone https://github.com/ntthanh2603/gemini-web-to-api.git .
# Build binary tối ưu dung lượng
RUN go build -ldflags="-w -s" -o gemini-web-to-api cmd/server/main.go

# Stage 2: Final Runtime Image (Python + Go Binary)
FROM python:3.10-alpine
WORKDIR /app

# Cài đặt các dependencies hệ thống cơ bản
RUN apk add --no-cache bash curl libstdc++

# Sao chép file binary Go đã compile từ Stage 1
COPY --from=go-builder /app/gemini-web-to-api /app/gemini-web-to-api

# Sao chép các tệp cài đặt python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn python và static web assets
COPY . .

# Đảm bảo start.sh có quyền thực thi
RUN chmod +x start.sh

# Cổng mặc định
EXPOSE 10000

# Khởi động dịch vụ thông qua start.sh
CMD ["./start.sh"]
