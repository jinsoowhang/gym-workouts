from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from gym_workouts.auth import configure_auth
from gym_workouts.config import Settings
from gym_workouts.contracts import SessionCommand, StartCommand
from gym_workouts.database import create_database
from gym_workouts.services import ConflictError, WorkoutService

PACKAGE = Path(__file__).parent
templates = Jinja2Templates(directory=PACKAGE / "templates")


def exercise_groups(rows):
    groups = []
    for row in rows:
        name = row["name"]
        group_key = "Arms" if name in ("skull crusher", "bicep curl bar") else name.title()
        group = next((group for group in groups if group["title"] == group_key), None)
        if group is None:
            group = {"title": group_key, "rows": [], "exercises": []}
            groups.append(group)
        group["rows"].append(row)
        if not any(e["id"] == row["exercise_id"] for e in group["exercises"]):
            group["exercises"].append(
                {
                    "id": row["exercise_id"],
                    "name": name.title(),
                    "removed": all(
                        r["state"] == "removed"
                        for r in rows
                        if r["exercise_id"] == row["exercise_id"]
                    ),
                }
            )
    for group in groups:
        sources = {row["default_source"] for row in group["rows"]}
        group["source_summary"] = group["rows"][0]["default_source"]
        if len(sources) > 1 and "Template" in sources and group["source_summary"] != "Template":
            group["source_summary"] += " + template defaults"
    return groups


def workout_context(service, workout=None):
    state = service.state()
    if workout is not None:
        state["session"] = workout
    session = state["session"]
    state["groups"] = exercise_groups(session["sets"]) if session else []
    state["done"] = sum(r["state"] == "performed" for r in session["sets"]) if session else 0
    state["total"] = sum(r["state"] != "removed" for r in session["sets"]) if session else 0
    return state


def create_app(settings=None):
    settings = settings or Settings.from_env()
    engine, factory = create_database(settings.database_path)
    service = WorkoutService(factory, settings)

    @asynccontextmanager
    async def lifespan(_app):
        service.recover_writes()
        yield
        engine.dispose()

    app = FastAPI(title="Gym Workouts", lifespan=lifespan)
    app.state.service = service
    app.state.factory = factory
    app.state.engine = engine
    configure_auth(app, settings, factory, templates)
    app.mount("/static", StaticFiles(directory=PACKAGE / "static"), name="static")

    @app.middleware("http")
    async def local_boundary(request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin:
                parsed = urlsplit(origin)
                if parsed.scheme != request.url.scheme or parsed.netloc != request.headers.get(
                    "host"
                ):
                    return JSONResponse({"detail": "Cross-origin request denied"}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Cross-site request denied"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = (
            "no-store" if not request.url.path.startswith("/static/") else "public, max-age=3600"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    @app.exception_handler(ConflictError)
    async def conflict_handler(_request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(ValueError)
    async def value_handler(_request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(LookupError)
    async def lookup_handler(_request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        return templates.TemplateResponse(request, "home.html", workout_context(service))

    @app.get("/history", response_class=HTMLResponse)
    def history(request: Request):
        from sqlalchemy import select

        from gym_workouts.models import WorkoutSession

        with factory() as db:
            records = list(
                db.scalars(
                    select(WorkoutSession)
                    .where(WorkoutSession.status.in_(["completed", "review"]))
                    .order_by(WorkoutSession.session_date.desc(), WorkoutSession.created_at.desc())
                )
            )
            return templates.TemplateResponse(request, "history.html", {"records": records})

    @app.get("/workouts/{session_id}", response_class=HTMLResponse)
    def saved_workout(request: Request, session_id: str):
        return templates.TemplateResponse(
            request, "home.html", workout_context(service, service.get(session_id))
        )

    @app.post("/start", response_class=HTMLResponse)
    async def start_form(request: Request):
        form = await request.form()
        chosen = StartCommand(routine=form.get("routine") or None)
        workout = service.start(chosen.routine)
        if request.headers.get("hx-request"):
            return templates.TemplateResponse(
                request, "workout.html", workout_context(service, workout)
            )
        return RedirectResponse("/", status_code=303)

    @app.post("/review/{session_id}")
    def review(session_id: str):
        service.approve_import(session_id)
        return RedirectResponse("/history", status_code=303)

    @app.post("/sessions/{session_id}/command", response_class=HTMLResponse)
    async def form_command(request: Request, session_id: str):
        form = await request.form()
        action = str(form.get("action", "save"))
        try:
            current = service.get(session_id)
            edits = []
            for row in current["sets"] if action not in ("retry", "discard") else []:
                edits.append(
                    {
                        "id": row["id"],
                        "weight": form.get(f"weight_{row['id']}") or None,
                        "reps": int(form[f"reps_{row['id']}"])
                        if row["type"] == "weight_reps"
                        else None,
                        "state": "performed"
                        if action == "finish" and row["state"] != "removed"
                        else form.get(f"state_{row['id']}", row["state"]),
                        "activity_area": str(form[f"area_{row['id']}"])
                        if f"area_{row['id']}" in form
                        else None,
                    }
                )
            command = SessionCommand(
                revision=int(form["revision"]),
                sets=edits,
                notes=str(form.get("notes", "")),
                therapy_areas=str(form["therapy_areas"]) if "therapy_areas" in form else None,
                action=action,
            )
            workout = service.command(session_id, command)
        except (ValueError, ValidationError, KeyError) as exc:
            message = (
                "Check your weight, reps, and therapy areas; changes have not been saved."
                if isinstance(exc, (ValidationError, KeyError))
                else str(exc)
            )
            return templates.TemplateResponse(
                request,
                "receipt.html",
                {"error": message},
                status_code=409 if isinstance(exc, ConflictError) else 422,
                headers={"HX-Retarget": "#save-status", "HX-Reswap": "innerHTML"},
            )
        if action == "save":
            return templates.TemplateResponse(
                request,
                "receipt.html",
                {
                    "revision": workout["revision"],
                    "total": sum(r["state"] != "removed" for r in workout["sets"]),
                },
            )
        if action == "discard":
            return templates.TemplateResponse(
                request,
                "workout.html",
                workout_context(service),
                headers={"HX-Retarget": "#workout", "HX-Reswap": "outerHTML"},
            )
        return templates.TemplateResponse(
            request,
            "workout.html",
            workout_context(service, workout),
            headers={"HX-Retarget": "#workout", "HX-Reswap": "outerHTML"},
        )

    @app.get("/api/v1/state")
    def api_state():
        return service.state()

    @app.post("/api/v1/sessions")
    def api_start(command: StartCommand):
        return service.start(command.routine)

    @app.get("/api/v1/sessions/{session_id}")
    def api_session(session_id: str):
        return service.get(session_id)

    @app.post("/api/v1/sessions/{session_id}/command")
    def api_command(session_id: str, command: SessionCommand):
        return service.command(session_id, command)

    @app.get("/health")
    def health():
        return {"status": "ok", "application": "gym-workouts"}

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
    return app
