import os
import socket
import threading
import time

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

from gym_workouts.app import create_app


@pytest.mark.skipif(
    os.environ.get("GYM_BROWSER_TESTS") != "1", reason="Opt-in browser verification"
)
def test_desktop_recording_autosave_removal_and_finish(configured):
    settings, _factory, _service = configured
    app = create_app(settings)
    app.state.service.today = lambda: "2026-10-11"
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.started
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    executable_path=os.environ.get("GYM_CHROMIUM_PATH") or None
                )
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{sock.getsockname()[1]}")
                expect(page.get_by_role("heading", name="Workout B", exact=True)).to_be_visible()
                page.get_by_role("button", name="Start workout", exact=False).click()
                field = page.get_by_role("spinbutton", name="Deadlift set 1 weight in lb")
                expect(field).to_have_value("47.5")
                field.fill("42.125")
                expect(page.locator("#revision")).to_have_value("1")
                page.reload()
                expect(
                    page.get_by_role("spinbutton", name="Deadlift set 1 weight in lb")
                ).to_have_value("42.125")
                page.get_by_role("button", name="Remove Leg Raise", exact=True).click()
                expect(
                    page.get_by_role("button", name="Restore Leg Raise", exact=True)
                ).to_be_visible()
                page.get_by_role("button", name="Restore Leg Raise", exact=True).click()
                expect(
                    page.get_by_role("button", name="Remove Leg Raise", exact=True)
                ).to_be_visible()
                page.get_by_role("button", name="Mark remaining done").click()
                expect(page.locator(".set-state").first).to_have_value("performed")
                # Finish must submit the current input even before a delayed autosave runs.
                field = page.get_by_role("spinbutton", name="Deadlift set 1 weight in lb")
                field.fill("40.125")
                page.get_by_role("button", name="Finish workout").click()
                expect(page.locator(".session-bar")).to_contain_text("Saved to Obsidian")
                expect(page.locator(".session-bar .pill")).to_have_text("Completed")
                note = settings.workout_dir / "2026-10-11 Workout B.md"
                assert "deadlift 40.125 7" in note.read_text()
                page.reload()
                expect(page.locator(".session-bar .pill")).to_have_text("Completed")
                assert not errors
                browser.close()
        finally:
            server.should_exit = True
            thread.join(timeout=5)
