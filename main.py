from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from app.routes import auth, background, ai, pose, session, profile
from app.middleware.error_handler import register_exception_handlers
from app.logging_config import configure_logging

configure_logging()

app = FastAPI(title="Pose Suggesting App - API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])
app.include_router(background.router, prefix="/api/background", tags=["background"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(pose.router, prefix="/api/pose", tags=["pose"])
app.include_router(session.router, prefix="/api/session", tags=["session"])

register_exception_handlers(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="10.69.40.112", port=int(os.environ.get("PORT", 8000)))
