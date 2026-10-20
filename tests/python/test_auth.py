import base64
import hashlib
import json
import time
from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from joserfc import jwt
from joserfc.jwk import RSAKey
from sqlalchemy import func, select

from gym_workouts.app import create_app
from gym_workouts.auth import COOKIE_NAME
from gym_workouts.models import LoginSession, User, WorkoutSession


@pytest.fixture
def hosted(configured):
    settings, factory, _service = configured
    settings = replace(
        settings,
        auth_enabled=True,
        public_url="https://gym.example.com",
        allowed_hosts=("gym.example.com", "127.0.0.1"),
        allowed_email="owner@example.com",
        session_secret="s" * 64,
        google_client_id="synthetic-client.apps.googleusercontent.com",
        google_client_secret="synthetic-secret",
    )
    app = create_app(settings)
    signing_key = RSAKey.generate_key(2048, parameters={"kid": "synthetic-key"})
    provider = {"claims": {}, "nonce": None, "challenge": None, "wrong_key": False}

    def google_response(request):
        if request.url.path == "/.well-known/openid-configuration":
            return httpx.Response(
                200,
                json={
                    "issuer": "https://accounts.google.com",
                    "authorization_endpoint": "https://accounts.google.com/authorize",
                    "token_endpoint": "https://accounts.google.com/token",
                    "jwks_uri": "https://accounts.google.com/certs",
                    "id_token_signing_alg_values_supported": ["RS256"],
                },
            )
        if request.url.path == "/certs":
            return httpx.Response(200, json={"keys": [signing_key.as_dict(private=False)]})
        assert request.url.path == "/token" and request.method == "POST"
        fields = parse_qs(request.content.decode())
        verifier = fields["code_verifier"][0]
        assert (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
            == provider["challenge"]
        )
        assert fields["redirect_uri"] == [settings.public_url + "/auth/callback"]
        now = int(time.time())
        claims = {
            "iss": "https://accounts.google.com",
            "aud": settings.google_client_id,
            "sub": "synthetic-google-owner",
            "iat": now,
            "exp": now + 3600,
            "nonce": provider["nonce"],
            "email": settings.allowed_email,
            "email_verified": True,
            **provider["claims"],
        }
        key = (
            RSAKey.generate_key(2048, parameters={"kid": "synthetic-key"})
            if provider["wrong_key"]
            else signing_key
        )
        id_token = jwt.encode({"alg": "RS256", "kid": "synthetic-key"}, claims, key)
        return httpx.Response(
            200,
            json={
                "access_token": "synthetic-access",
                "token_type": "Bearer",
                "expires_in": 3600,
                "id_token": id_token,
            },
        )

    app.state.google.client_kwargs["transport"] = httpx.MockTransport(google_response)
    with TestClient(app, base_url=settings.public_url, follow_redirects=False) as client:
        yield client, factory, provider


def begin_login(client, provider):
    response = client.get("/auth/login")
    assert response.status_code == 302
    url = urlsplit(response.headers["location"])
    assert url.netloc == "accounts.google.com"
    parameters = parse_qs(url.query)
    assert parameters["scope"] == ["openid email"]
    assert parameters["code_challenge_method"] == ["S256"]
    provider["nonce"] = parameters["nonce"][0]
    provider["challenge"] = parameters["code_challenge"][0]
    return parameters["state"][0]


def complete_login(client, provider):
    state = begin_login(client, provider)
    return client.get("/auth/callback", params={"state": state, "code": "synthetic-code"})


def test_anonymous_requests_cannot_read_or_write_workouts(hosted):
    client, _factory, _provider = hosted
    for path in ("/", "/history", "/dashboard", "/workouts/anything"):
        response = client.get(path)
        assert response.status_code == 303 and response.headers["location"] == "/login"
        assert response.headers["cache-control"] == "no-store"
    for path in ("/api/v1/state", "/api/v1/sessions/anything"):
        assert client.get(path).status_code == 401
    assert client.post("/api/v1/sessions", json={}).status_code == 401
    assert client.post("/start", headers={"HX-Request": "true"}).status_code == 401
    assert client.get("/health").status_code == 200
    assert client.get("/login").status_code == 200
    assert client.get("/static/app.css").status_code == 200
    assert client.get("/", headers={"Host": "untrusted.example.com"}).status_code == 400


def test_google_login_creates_secure_revocable_session(hosted):
    client, factory, provider = hosted
    response = complete_login(client, provider)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    cookie = response.headers["set-cookie"].lower()
    assert all(flag in cookie for flag in ("httponly", "secure", "samesite=lax", "path=/"))
    payload = json.loads(base64.b64decode(client.cookies.get(COOKIE_NAME).split(".")[0]))
    assert set(payload) == {"login"}
    assert client.get("/api/v1/state").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/dashboard").status_code == 200
    with factory() as db:
        row = db.scalar(select(LoginSession))
        assert len(row.id) == 64 and row.email == "owner@example.com"
    old_cookie = client.cookies.get(COOKIE_NAME)
    assert (
        client.post("/auth/logout", headers={"Origin": "https://untrusted.example.com"}).status_code
        == 403
    )
    assert client.post("/auth/logout").status_code == 303
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(LoginSession)) == 0
    client.cookies.set(COOKIE_NAME, old_cookie, domain="gym.example.com", path="/")
    assert client.get("/api/v1/state").status_code == 401


@pytest.mark.parametrize("internal_scheme", ["http", "https"])
def test_start_workout_behind_https_termination(hosted, internal_scheme):
    client, _factory, provider = hosted
    assert complete_login(client, provider).status_code == 303
    # The browser sends its Secure cookie over HTTPS; a proxy may use HTTP upstream.
    headers = {
        "Origin": "https://gym.example.com",
        "Cookie": f"{COOKIE_NAME}={client.cookies.get(COOKIE_NAME)}",
        "HX-Request": "true",
    }
    url = f"{internal_scheme}://gym.example.com/start"
    for origin in (
        "http://gym.example.com",
        "https://other.example.com",
        "https://gym.example.com:444",
    ):
        response = client.post(url, data={"routine": "A"}, headers=headers | {"Origin": origin})
        assert response.status_code == 403
    response = client.post(url, data={"routine": "A"}, headers=headers)
    assert response.status_code == 200
    assert 'id="session-form"' in response.text
    assert client.get("/api/v1/state").json()["session"]["status"] == "draft"


@pytest.mark.parametrize(
    "claims",
    [
        {"email": "other@example.com"},
        {"email_verified": False},
        {"email_verified": "true"},
        {"aud": "another-client"},
        {"iss": "https://untrusted.example.com"},
        {"nonce": "another-nonce"},
        {"exp": 1},
        {"sub": ""},
    ],
)
def test_signed_but_invalid_google_identity_cannot_sign_in(hosted, claims):
    client, factory, provider = hosted
    provider["claims"] = claims
    assert complete_login(client, provider).status_code in (400, 403)
    assert client.get("/api/v1/state").status_code == 401
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(LoginSession)) == 0


def test_wrong_signature_and_oauth_state_are_rejected(hosted):
    client, _factory, provider = hosted
    state = begin_login(client, provider)
    assert (
        client.get("/auth/callback", params={"state": "wrong", "code": "code"}).status_code == 400
    )
    assert client.get("/auth/callback", params={"state": state, "code": "code"}).status_code == 400
    provider["wrong_key"] = True
    assert complete_login(client, provider).status_code == 400
    assert client.get("/api/v1/state").status_code == 401


def test_expired_or_modified_session_does_not_authorize_requests(hosted):
    client, factory, provider = hosted
    assert complete_login(client, provider).status_code == 303
    original = client.cookies.get(COOKIE_NAME)
    client.cookies.set(COOKIE_NAME, original + "changed", domain="gym.example.com", path="/")
    assert client.get("/api/v1/state").status_code == 401
    client.cookies.set(COOKIE_NAME, original, domain="gym.example.com", path="/")
    with factory.begin() as db:
        db.scalar(select(LoginSession)).expires_at = 1
    assert client.get("/api/v1/state").status_code == 401


def test_missing_google_credentials_keep_hosted_app_closed(configured):
    settings, _factory, _service = configured
    app = create_app(
        replace(
            settings,
            auth_enabled=True,
            public_url="https://gym.example.com",
            allowed_hosts=("gym.example.com",),
            allowed_email="owner@example.com",
            session_secret="s" * 64,
        )
    )
    with TestClient(app, base_url="https://gym.example.com", follow_redirects=False) as client:
        assert client.get("/login").status_code == 503
        assert "Sign-in setup is in progress" in client.get("/login").text
        assert client.get("/auth/login").status_code == 503
        assert client.get("/api/v1/state").status_code == 401


def test_owner_cannot_read_or_change_another_users_workout(hosted):
    client, factory, provider = hosted
    with factory.begin() as db:
        db.add(User(id="other-user", email="guest@example.com"))
        db.flush()
        db.add(
            WorkoutSession(
                id="private-other-session",
                user_id="other-user",
                routine="A",
                session_date="2026-10-11",
                created_at="2026-10-11T00:00:00",
                status="review",
                notes="Private guest workout marker",
            )
        )
    assert complete_login(client, provider).status_code == 303
    for path in ("/workouts/private-other-session", "/api/v1/sessions/private-other-session"):
        assert client.get(path).status_code == 404
    assert client.post("/review/private-other-session").status_code == 404
    assert (
        client.post(
            "/sessions/private-other-session/command", data={"action": "retry", "revision": 0}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/sessions/private-other-session/command",
            json={"action": "cancel", "revision": 0},
        ).status_code
        == 404
    )
    for path in ("/", "/history", "/dashboard", "/api/v1/state"):
        response = client.get(path)
        assert response.status_code == 200
        assert "Private guest workout marker" not in response.text
        assert "private-other-session" not in response.text
    response = client.post("/api/v1/sessions", json={"routine": "A", "user_id": "other-user"})
    assert response.status_code == 200
    with factory() as db:
        login = db.scalar(select(LoginSession))
        assert db.get(WorkoutSession, response.json()["id"]).user_id == login.user_id
        assert db.get(WorkoutSession, "private-other-session").status == "review"


def test_google_subject_cannot_be_replaced_even_with_the_same_email(hosted):
    client, factory, provider = hosted
    assert complete_login(client, provider).status_code == 303
    assert client.post("/auth/logout").status_code == 303
    provider["claims"] = {"sub": "different-google-account"}
    assert complete_login(client, provider).status_code == 403
    assert client.get("/api/v1/state").status_code == 401
    with factory() as db:
        owner = db.scalar(select(User).where(User.vault_owner.is_(True)))
        assert owner.google_subject == "synthetic-google-owner"
        assert db.scalar(select(func.count()).select_from(User)) == 1


def test_existing_other_users_still_cannot_sign_in(hosted):
    client, factory, provider = hosted
    with factory.begin() as db:
        db.add(User(id="invited-later", email="guest@example.com", google_subject="guest-subject"))
    provider["claims"] = {"email": "guest@example.com", "sub": "guest-subject"}
    assert complete_login(client, provider).status_code == 403
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(LoginSession)) == 0


def test_google_subject_already_bound_to_another_user_is_rejected(hosted):
    client, factory, provider = hosted
    with factory.begin() as db:
        db.add(
            User(
                id="another-user",
                email="guest@example.com",
                google_subject="synthetic-google-owner",
            )
        )
    assert complete_login(client, provider).status_code == 403
    assert client.get("/api/v1/state").status_code == 401
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(LoginSession)) == 0
