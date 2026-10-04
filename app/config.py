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


"""
Config — đọc secret key và cấu hình từ file .env, tập trung 1 chỗ.
KHÔNG hardcode giá trị thật ở đây, luôn lấy qua os.environ.get().
"""