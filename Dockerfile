# Dockerfile

# Bước 1: Chọn một ảnh nền Python gọn nhẹ
FROM python:3.10-slim

# Bước 2: Cài đặt các gói hệ thống cần thiết
# - tesseract-ocr: Công cụ OCR chính mà pytesseract sử dụng
# - libgl1-mesa-glx & libglib2.0-0: Các thư viện cần thiết cho OpenCV hoạt động trên Linux
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && apt-get clean

# Bước 3: Tạo thư mục làm việc cho ứng dụng
WORKDIR /app

# Bước 4: Sao chép file requirements và cài đặt thư viện Python
# Tách riêng bước này để tận dụng Docker cache, giúp build nhanh hơn sau này
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bước 5: Sao chép toàn bộ mã nguồn của bot vào thư mục làm việc
COPY . .

# Bước 6: Chạy ứng dụng khi container khởi động
CMD ["python", "main.py"]
