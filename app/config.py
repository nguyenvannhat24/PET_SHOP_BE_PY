import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    PORT: int = int(os.getenv("PORT", "5000"))
    NODE_ENV: str = os.getenv("NODE_ENV", "development")
    MONGO_URI: str = os.getenv(
        "MONGO_URI",
        "mongodb+srv://nhat:123@cluster0.ajpeazo.mongodb.net/PetShop?retryWrites=true&w=majority&appName=Cluster0"
    )
    JWT_SECRET: str = os.getenv("JWT_SECRET", "your_jwt_secret_key_here")
    JWT_EXPIRE: str = os.getenv("JWT_EXPIRE", "30d")
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public", "uploads")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Đảm bảo thư mục lưu trữ ảnh tồn tại
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
