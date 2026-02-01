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

Security: JWT is used for token-based auth. Replace `JWT_SECRET` env var for production.
