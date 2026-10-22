import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    APP_NAME = "GetApps"
    SECRET_KEY = os.environ.get("SECRET_KEY") or "getapps-dev-secret-key-pwd301-se173285"
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or "getapps-dev-jwt-secret-key-pwd301-se173285"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///app.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TEMPLATES_AUTO_RELOAD = True
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")

    # ==================== CHỈ DÙNG KHI QUAY DEMO KỊCH BẢN BROKEN ACCESS CONTROL ====================
    # Bật = True (qua biến môi trường DEMO_BAC_VULNERABLE=1 trong .env) để admin_required
    # "giả vờ quên" kiểm tra quyền, tái hiện đúng lỗi Missing Function Level Access Control
    # (OWASP A01:2021) cho báo cáo/live demo. PHẢI để False (mặc định) khi nộp bài / chạy thật —
    # xem app/admin/decorators.py và README_SECURITY.md.
    DEMO_BAC_VULNERABLE = os.environ.get("DEMO_BAC_VULNERABLE", "0") == "1"



"""
Config — đọc secret key và cấu hình từ file .env, tập trung 1 chỗ.
KHÔNG hardcode giá trị thật ở đây, luôn lấy qua os.environ.get().
"""