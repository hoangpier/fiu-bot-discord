# Sử dụng một ảnh nền Python 3.10 gọn nhẹ
FROM python:3.10-slim

# Cài đặt Tesseract, gói ngôn ngữ Tiếng Anh, và dọn dẹp cache trong cùng một lệnh
RUN apt-get update && \
    apt-get install -y tesseract-ocr tesseract-ocr-eng && \
    rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Sao chép file requirements trước để tận dụng cache
COPY requirements.txt .

# Cài đặt các thư viện Python và không lưu cache
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn của bot
COPY . .

# Lệnh để chạy bot khi khởi động
CMD ["python", "main.py"]
