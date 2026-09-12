import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    APP_NAME = "GetApps"
    SECRET_KEY = os.environ.get("SECRET_KEY")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False


"""
Config — đọc secret key và cấu hình từ file .env, tập trung 1 chỗ.
KHÔNG hardcode giá trị thật ở đây, luôn lấy qua os.environ.get().
"""