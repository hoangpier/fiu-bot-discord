# Sử dụng một ảnh nền Python 3.10 gọn nhẹ
FROM python:3.10-slim

# Cài đặt tất cả các gói hệ thống cần thiết và dọn dẹp cache
# --no-install-recommends giúp giảm kích thước image cuối cùng
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        libgl1-mesa-glx \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Sao chép file requirements trước để tận dụng cache của Docker
COPY requirements.txt .

# Cài đặt các thư viện Python và không lưu cache
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn của bot vào image
COPY . .

# Lệnh để chạy bot khi container khởi động
CMD ["python", "main.py"]
