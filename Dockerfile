# Sử dụng ảnh nền Python 3.10 chính thức, phiên bản slim (gọn nhẹ)
FROM python:3.10-slim

# Đặt thư mục làm việc bên trong máy ảo là /app
WORKDIR /app

# Cập nhật và cài đặt phần mềm Tesseract OCR. Đây là bước quan trọng nhất.
RUN apt-get update && apt-get install -y tesseract-ocr

# Sao chép file requirements.txt vào trước để tận dụng cache
COPY requirements.txt .

# Cài đặt tất cả các thư viện Python cần thiết
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ code của bạn (main.py, tennhanvatvasotim.txt, v.v.) vào máy ảo
COPY . .

# Lệnh sẽ được chạy khi máy ảo khởi động, chính là lệnh để chạy bot
CMD ["python", "main.py"]
