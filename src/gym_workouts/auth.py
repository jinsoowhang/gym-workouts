"""Google sign-in for the single approved owner; local recording needs no login."""

import hashlib
import secrets
import time

import httpx
from authlib.integrations.base_client import OAuthError
from authlib.integrations.starlette_client import OAuth
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from joserfc.errors import JoseError
from sqlalchemy import delete, or_, update
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware

from gym_workouts.models import LoginSession, User

COOKIE_NAME = "__Host-gym_session"
SESSION_SECONDS = 24 * 60 * 60


def session_id(token):
    return hashlib.sha256(token.encode()).hexdigest()


def configure_auth(app, settings, factory, templates, owner_id):
    app.state.auth_enabled = settings.auth_enabled
    if not settings.auth_enabled:
        return

    oauth = OAuth()
    google = oauth.register(
        "google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email", "code_challenge_method": "S256", "timeout": 10},
    )
    app.state.google = google
    ready = bool(settings.google_client_id and settings.google_client_secret)

    def authenticated(request):
        token = request.session.get("login")
        if not isinstance(token, str):
            return False
        with factory.begin() as db:
            login = db.get(LoginSession, session_id(token))
            user = db.get(User, login.user_id) if login is not None else None
            if (
                login is not None
                and user is not None
                and user.id == owner_id
                and login.expires_at > time.time()
                and login.email == settings.allowed_email
                and user.email == settings.allowed_email
                and user.google_subject == login.subject
            ):
                return user.id
            if login is not None:
                db.delete(login)
        request.session.pop("login", None)
        return False

    @app.middleware("http")
    async def login_required(request, call_next):
        request.state.user_id = await run_in_threadpool(authenticated, request) if ready else None
        request.state.authenticated = bool(request.state.user_id)
        public = request.url.path in {"/health", "/login", "/auth/login", "/auth/callback"}
        if (
            not request.state.authenticated
            and not public
            and not request.url.path.startswith("/static/")
        ):
            if request.url.path.startswith("/api/") or request.headers.get("hx-request"):
                return JSONResponse(
                    {"detail": "Sign in required", "login_url": "/login"}, status_code=401
                )
            return RedirectResponse("/login", status_code=303)
        return await call_next(request)

    # This wraps the authentication check; the cookie holds opaque session IDs and OAuth state.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie=COOKIE_NAME,
        max_age=SESSION_SECONDS,
        same_site="lax",
        https_only=True,
    )

    def login_page(request, error=None, status=200):
        return templates.TemplateResponse(
            request, "login.html", {"login_ready": ready, "error": error}, status_code=status
        )

    @app.get("/login")
    async def login(request: Request):
        if request.state.authenticated:
            return RedirectResponse("/", status_code=303)
        return login_page(request, status=200 if ready else 503)

    @app.get("/auth/login")
    async def google_login(request: Request):
        if not ready:
            return login_page(request, status=503)
        try:
            return await google.authorize_redirect(
                request, settings.public_url + "/auth/callback", prompt="select_account"
            )
        except (OAuthError, httpx.HTTPError):
            return login_page(request, "Sign-in is temporarily unavailable. Please try again.", 503)

    @app.get("/auth/callback")
    async def callback(request: Request):
        if not ready:
            return login_page(request, status=503)
        try:
            token = await google.authorize_access_token(request, leeway=30)
            claims = token.get("userinfo", {})
        except (OAuthError, JoseError, httpx.HTTPError, ValueError, KeyError):
            request.session.clear()
            return login_page(request, "Sign-in could not be verified. Please try again.", 400)
        if (
            claims.get("email_verified") is not True
            or not isinstance(claims.get("email"), str)
            or claims["email"].casefold() != settings.allowed_email
            or not claims.get("sub")
            or not isinstance(claims.get("sub"), str)
        ):
            request.session.clear()
            return login_page(request, "This Google account does not have access.", 403)
        opaque = secrets.token_urlsafe(32)
        old = request.session.get("login")
        with factory.begin() as db:
            # A verified email can claim the owner once; future logins must match
            # Google's stable subject rather than transferring workouts by email.
            try:
                bound = db.execute(
                    update(User)
                    .where(
                        User.id == owner_id,
                        User.email == settings.allowed_email,
                        or_(User.google_subject.is_(None), User.google_subject == claims["sub"]),
                    )
                    .values(google_subject=claims["sub"])
                )
            except IntegrityError:
                db.rollback()
                request.session.clear()
                return login_page(request, "This Google account does not have access.", 403)
            if bound.rowcount != 1:
                request.session.clear()
                return login_page(request, "This Google account does not have access.", 403)
            db.execute(delete(LoginSession).where(LoginSession.expires_at <= time.time()))
            if isinstance(old, str):
                db.execute(delete(LoginSession).where(LoginSession.id == session_id(old)))
            db.add(
                LoginSession(
                    id=session_id(opaque),
                    user_id=owner_id,
                    subject=claims["sub"],
                    email=settings.allowed_email,
                    expires_at=int(time.time()) + SESSION_SECONDS,
                )
            )
        request.session.clear()
        request.session["login"] = opaque
        return RedirectResponse("/", status_code=303)

    @app.post("/auth/logout")
    async def logout(request: Request):
        opaque = request.session.get("login")
        if isinstance(opaque, str):
            with factory.begin() as db:
                db.execute(delete(LoginSession).where(LoginSession.id == session_id(opaque)))
        request.session.clear()
        return RedirectResponse("/login", status_code=303)
