# Pose Suggesting App - Backend API (API Layer only)

This repository contains the backend API layer for the "Pose Suggesting App Using Deep Learning" final-year project. It intentionally excludes database models, persistence, and model training code. Services are mocked or defined as interfaces where persistence and model-loading should be implemented.

Quick start (local):

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

2. Run the server:

```bash
uvicorn main:app --reload --port 8000
```

3. Test endpoints with Postman or curl. Example login/register endpoints are under `/api/auth`.

Environment variables (`.env`):

```env
DB_HOST=localhost
DB_USER=app_user
DB_PASSWORD=your_db_password
DB_NAME=posea_db

JWT_SECRET=CHANGE_ME_FOR_PRODUCTION

# Forgot/Reset password settings
RESET_TOKEN_EXPIRY_MINUTES=15
RESET_PASSWORD_BASE_URL=https://your-frontend/reset-password

# Email verification OTP settings
EMAIL_VERIFICATION_EXPIRY_MINUTES=15
EMAIL_VERIFICATION_OTP_LENGTH=6

# SMTP (optional; if omitted, reset link is logged server-side for development)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@example.com
SMTP_PASSWORD=your_smtp_password
SMTP_FROM_EMAIL=your_email@example.com
# STARTTLS mode: auto (default), always, never
SMTP_STARTTLS_MODE=auto

# Optional model path overrides
BACKGROUND_MODEL_PATH=app/models/Background_classification_model03.h5
POSE_SUGGESTION_MODEL_PATH=app/models/pose_suggestion_model_with_10Poses.h5

# Optional comma-separated labels if .labels.txt is unavailable
# BACKGROUND_MODEL_LABELS=beach,sea,horizon,vegetation,golden_hour,midday,overcast,other_negative
# POSE_SUGGESTION_MODEL_LABELS=pose_a,pose_b,pose_c,pose_d,pose_e,pose_f,pose_g,pose_h,pose_i,pose_j
```

Notes for Google Colab testing:

- Colab already provides Python and GPU; install dependencies with `pip install -r requirements.txt` in a cell.
- Run the app in Colab using `nest-asyncio` and `uvicorn` in a background thread or use `ngrok` to expose the server for testing.

API Overview (selected endpoints):

- POST `/api/auth/register` — register user (mocked)
- POST `/api/auth/login` — login and receive JWT token
- POST `/api/auth/logout` — logout (requires `Authorization: Bearer <token>`)
- PUT `/api/auth/profile` — update profile (requires auth)
- POST `/api/background/upload` — upload background image (JPG/PNG, <=5MB)
- POST `/api/ai/classify` — classify uploaded image (returns tags/confidences)
- POST `/api/pose/suggest` — request pose suggestions by tags
- POST `/api/session/start` — start a posing session
- POST `/api/session/end` — end a session
- POST `/api/session/capture` — submit capture metadata

Skeleton extraction for pose library:

```bash
python scripts/extract_pose_skeleton_data.py --dry-run --only-empty-skeleton
python scripts/extract_pose_skeleton_data.py --only-empty-skeleton
python scripts/extract_pose_skeleton_data.py --only-empty-skeleton --pose-model-path app/models/pose_landmarker_lite.task
```

- The script reads pose images from `pose_image_base64` (or dataset file fallback),
  extracts 33 body landmarks using MediaPipe Pose, and stores JSON in `pose_library.skeleton_data`.

Security: JWT is used for token-based auth. Replace `JWT_SECRET` env var for production.
