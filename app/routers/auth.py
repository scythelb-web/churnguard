"""Authentication routes — signup, login, logout."""
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse
from passlib.hash import bcrypt
from jose import jwt
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.config import SECRET_KEY

router = APIRouter(prefix="/auth", tags=["auth"])

ALGORITHM = "HS256"
SESSION_DAYS = 30


def create_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(request: Request) -> dict | None:
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
        with get_db() as db:
            row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


@router.get("/signup")
async def signup_page(request: Request):
    return request.app.state.templates.TemplateResponse("signup.html", {"request": request})


@router.post("/signup")
async def signup(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    with get_db() as db:
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise HTTPException(400, "Email already registered")

        pw_hash = bcrypt.hash(password)
        cursor = db.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, pw_hash),
        )
        user_id = cursor.lastrowid

    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie("session", create_token(user_id), max_age=SESSION_DAYS * 86400, httponly=True)
    return response


@router.get("/login")
async def login_page(request: Request):
    return request.app.state.templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    if not row or not bcrypt.verify(password, row["password_hash"]):
        raise HTTPException(401, "Invalid email or password")

    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie("session", create_token(row["id"]), max_age=SESSION_DAYS * 86400, httponly=True)
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("session")
    return response
