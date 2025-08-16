# Sử dụng một ảnh nền Python gọn nhẹ
FROM python:3.10-slim

# Cài đặt Tesseract OCR trên hệ điều hành Debian
RUN apt-get update && apt-get install -y tesseract-ocr && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Sao chép file requirements trước
COPY requirements.txt .

# Cài đặt các thư viện Python
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn của bot
COPY . .

# Lệnh để chạy bot khi khởi động
CMD ["python", "main.py"]
