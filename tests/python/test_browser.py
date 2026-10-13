import os
import socket
import threading
import time

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

from gym_workouts.app import create_app
from gym_workouts.contracts import parse_note


@pytest.mark.skipif(
    os.environ.get("GYM_BROWSER_TESTS") != "1", reason="Opt-in browser verification"
)
@pytest.mark.parametrize("settle_delay", [20, 200])
@pytest.mark.parametrize("configured", [4], indirect=True)
def test_desktop_recording_autosave_removal_and_finish(configured, settle_delay):
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
                page.evaluate("delay => htmx.config.defaultSettleDelay = delay", settle_delay)
                expect(page.get_by_role("heading", name="Workout B", exact=True)).to_be_visible()
                page.get_by_role("button", name="Start workout", exact=False).click()
                field = page.get_by_role("spinbutton", name="Deadlift set 1 weight in lb")
                expect(field).to_have_value("47.5")
                # Swapped fields appear before HTMX attaches their form's event listeners.
                expect(page.locator("#workout.htmx-settling")).to_have_count(0)
                field.fill("42.125")
                expect(page.locator("#revision")).to_have_value("1")
                page.reload()
                page.evaluate("delay => htmx.config.defaultSettleDelay = delay", settle_delay)
                expect(
                    page.get_by_role("spinbutton", name="Deadlift set 1 weight in lb")
                ).to_have_value("42.125")
                page.get_by_role("button", name="Remove Leg Raise", exact=True).click()
                expect(
                    page.get_by_role("button", name="Restore Leg Raise", exact=True)
                ).to_be_visible()
                expect(page.locator("#workout.htmx-settling")).to_have_count(0)
                page.get_by_role("button", name="Restore Leg Raise", exact=True).click()
                expect(
                    page.get_by_role("button", name="Remove Leg Raise", exact=True)
                ).to_be_visible()
                expect(page.locator("#workout.htmx-settling")).to_have_count(0)
                expect(page.get_by_text("STATUS", exact=True)).to_have_count(0)
                expect(page.locator("select.set-state")).to_have_count(0)
                expect(page.locator(".exercise-icon svg")).to_have_count(7)
                fourth_set = page.get_by_role("button", name="Remove Bench Press set 4", exact=True)
                fourth_set.click()
                undo = page.get_by_role("button", name="Restore Bench Press set 4", exact=True)
                expect(undo).to_be_visible()
                expect(
                    page.get_by_role("spinbutton", name="Bench Press set 3 weight in lb")
                ).to_be_visible()
                page.reload()
                page.evaluate("delay => htmx.config.defaultSettleDelay = delay", settle_delay)
                expect(undo).to_be_visible()
                undo.click()
                expect(fourth_set).to_be_visible()
                expect(
                    page.get_by_role("spinbutton", name="Bench Press set 4 weight in lb")
                ).to_have_value("40")
                expect(page.locator("#workout.htmx-settling")).to_have_count(0)
                fourth_set.click()
                expect(undo).to_be_visible()
                expect(page.locator("#workout.htmx-settling")).to_have_count(0)
                expect(page.locator("#progress-summary")).to_have_text(
                    "9 sets & activities included"
                )
                page.get_by_role("button", name="Add set to Bench Press", exact=True).click()
                fifth = page.get_by_role("spinbutton", name="Bench Press set 5 weight in lb")
                expect(fifth).to_have_value("40")
                expect(page.locator("#workout.htmx-settling")).to_have_count(0)
                revision = int(page.locator("#revision").input_value())
                fifth.fill("35.125")
                expect(page.locator("#revision")).to_have_value(str(revision + 1))
                areas = page.get_by_role("textbox", name="Physical Therapy area 1", exact=True)
                revision = int(page.locator("#revision").input_value())
                areas.fill("Ankle")
                expect(page.locator("#revision")).to_have_value(str(revision + 1))
                page.get_by_role("button", name="Add area to Physical Therapy", exact=True).click()
                second_area = page.get_by_role(
                    "textbox", name="Physical Therapy area 2", exact=True
                )
                expect(second_area).to_be_visible()
                expect(page.locator("#workout.htmx-settling")).to_have_count(0)
                revision = int(page.locator("#revision").input_value())
                second_area.fill("Elbow")
                expect(page.locator("#revision")).to_have_value(str(revision + 1))
                page.get_by_role(
                    "button", name="Remove Physical Therapy area 1", exact=True
                ).click()
                restore_area = page.get_by_role(
                    "button", name="Restore Physical Therapy area 1", exact=True
                )
                expect(restore_area).to_be_visible()
                expect(second_area).to_have_value("Elbow")
                page.reload()
                page.evaluate("delay => htmx.config.defaultSettleDelay = delay", settle_delay)
                expect(restore_area).to_be_visible()
                restore_area.click()
                expect(areas).to_have_value("Ankle")
                expect(fifth).to_have_value("35.125")
                expect(page.locator("#workout.htmx-settling")).to_have_count(0)
                # Finish must submit the current input even before a delayed autosave runs.
                second_area.fill("Wrist")
                field = page.get_by_role("spinbutton", name="Deadlift set 1 weight in lb")
                field.fill("40.125")
                page.get_by_role("button", name="Finish workout").click()
                expect(page.locator(".session-bar")).to_contain_text("Saved to Obsidian")
                expect(page.locator(".session-bar .pill")).to_have_text("Completed")
                note = settings.workout_dir / "2026-10-11 Workout B.md"
                assert "deadlift 40.125 7" in note.read_text()
                assert parse_note(note.read_text()).metadata["therapy_areas"] == "Ankle, Wrist"
                bench = [
                    row for row in parse_note(note.read_text()).rows if row.name == "bench press"
                ]
                assert [row.state for row in bench] == ["performed"] * 3 + ["removed", "performed"]
                assert str(bench[-1].weight) == "35.125"
                page.reload()
                expect(page.locator(".session-bar .pill")).to_have_text("Completed")
                expect(areas).to_have_value("Ankle")
                expect(second_area).to_have_value("Wrist")
                expect(areas).to_have_attribute("readonly", "")
                page.get_by_role("button", name="Start Workout A", exact=False).click()
                cancel = page.get_by_role("button", name="Cancel workout", exact=True)
                expect(cancel).to_be_visible()
                expect(page.locator("#workout.htmx-settling")).to_have_count(0)
                page.get_by_role("spinbutton", name="Squat set 1 weight in lb").fill("")
                page.once("dialog", lambda dialog: dialog.dismiss())
                cancel.click()
                expect(page.locator(".session-bar .pill")).to_have_text("In progress")
                page.once("dialog", lambda dialog: dialog.accept())
                cancel.click()
                expect(
                    page.get_by_text("Workout cancelled. Start again whenever you’re ready.")
                ).to_be_visible()
                expect(page.locator(".session-bar .pill")).to_have_text("Completed")
                page.get_by_role("link", name="Dashboard", exact=True).click()
                expect(
                    page.get_by_role("heading", name="Your training, over time.")
                ).to_be_visible()
                page.get_by_label("Compare", exact=True).select_option("volume")
                page.get_by_label("Date range", exact=True).select_option("0")
                page.get_by_role("button", name="Update dashboard", exact=False).click()
                expect(page.locator("#exercise-chart-title")).to_contain_text(
                    "Load volume over time"
                )
                expect(page.get_by_role("link", name="Dashboard", exact=True)).to_have_attribute(
                    "aria-current", "page"
                )
                assert not errors
                browser.close()
        finally:
            server.should_exit = True
            thread.join(timeout=5)
