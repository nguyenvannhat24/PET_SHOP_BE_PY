import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import socketio

from app.config import settings
from app.socket_server import sio

# Import Routers
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.upload import router as upload_router
from app.routers.pets import router as pets_router
from app.routers.clinics import router as clinics_router
from app.routers.veterinarians import router as vets_router
from app.routers.services import router as services_router
from app.routers.appointments import router as appointments_router
from app.routers.medical_records import router as medical_records_router
from app.routers.vaccinations import router as vaccinations_router
from app.routers.notifications import router as notifications_router
from app.routers.chat import router as chat_router
from app.routers.admin import router as admin_router
from app.routers.search import router as search_router
from app.routers.reviews import router as reviews_router
from app.routers.commerce import products_router, cart_router, orders_router

# Khởi tạo FastAPI App với Metadata OpenAPI Swagger
fastapi_app = FastAPI(
    title="PET CONNECT API (Python FastAPI)",
    description="Hệ thống Backend quản lý thú cưng, đặt lịch khám, sổ bệnh án, chat realtime và thông báo đẩy.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Cấu hình CORS mở rộng cho Frontend Vite và các client khác
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phục vụ thư mục ảnh tĩnh /uploads
fastapi_app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Đăng ký các Router API
fastapi_app.include_router(auth_router)
fastapi_app.include_router(users_router)
fastapi_app.include_router(upload_router)
fastapi_app.include_router(pets_router)
fastapi_app.include_router(clinics_router)
fastapi_app.include_router(vets_router)
fastapi_app.include_router(services_router)
fastapi_app.include_router(appointments_router)
fastapi_app.include_router(medical_records_router)
fastapi_app.include_router(vaccinations_router)
fastapi_app.include_router(notifications_router)
fastapi_app.include_router(chat_router)
fastapi_app.include_router(admin_router)
fastapi_app.include_router(search_router)
fastapi_app.include_router(reviews_router)
fastapi_app.include_router(products_router)
fastapi_app.include_router(cart_router)
fastapi_app.include_router(orders_router)

# Route kiểm tra tình trạng server
@fastapi_app.get("/")
async def root():
    return {
        "status": "online",
        "service": "PET CONNECT API (FastAPI Python)",
        "version": "2.0.0",
        "docs": "/docs"
    }

# Tự động khởi tạo tài khoản Admin mặc định khi chạy với cơ sở dữ liệu local mới
@fastapi_app.on_event("startup")
async def startup_db_seed():
    try:
        from datetime import datetime
        from app.database import users_col
        from app.middlewares.auth import hash_password
        admin = await users_col.find_one({"email": "admin@petconnect.vn"})
        if not admin:
            await users_col.insert_one({
                "full_name": "Quản trị viên Hệ thống",
                "email": "admin@petconnect.vn",
                "password_hash": hash_password("admin123"),
                "phone": "0988888888",
                "role": "ADMIN",
                "status": "ACTIVE",
                "avatar_url": "",
                "email_verified": True,
                "phone_verified": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            print("🚀 [Database Seed] Đã khởi tạo tài khoản Admin mặc định: admin@petconnect.vn / admin123")
    except Exception as e:
        print("⚠️ [Startup Warning] Không thể tự động tạo admin:", e)


# Kết hợp FastAPI và Socket.IO thành ứng dụng ASGI duy nhất
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)
