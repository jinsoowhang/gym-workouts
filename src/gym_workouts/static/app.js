"use strict";

let changes = 0;
let acknowledged = 0;
const exerciseViews = new Map();
const weightValues = new WeakMap();
const restTimers = new Map();
const restDurations = [30, 60, 90, 120, 180, 300];

function restTimerKey(sessionId) {
  return `gym-rest:${sessionId}`;
}

function restTimer(sessionId) {
  if (!restTimers.has(sessionId)) {
    let saved;
    try {
      saved = JSON.parse(localStorage.getItem(restTimerKey(sessionId)));
    } catch (_) { /* Timers still work when browser storage is unavailable. */ }
    restTimers.set(sessionId, {
      duration: restDurations.includes(saved?.duration) ? saved.duration : 90,
      endsAt: Number.isFinite(saved?.endsAt) && saved.endsAt > 0 ? saved.endsAt : null,
    });
  }
  return restTimers.get(sessionId);
}

function saveRestTimer(sessionId, timer) {
  try {
    localStorage.setItem(restTimerKey(sessionId), JSON.stringify(timer));
  } catch (_) { /* Keep the in-memory timer if storage is unavailable. */ }
}

function formatTimer(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds / 60) % 60;
  const remainder = seconds % 60;
  return `${hours ? `${String(hours).padStart(2, "0")}:` : ""}${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function updateWorkoutTimers() {
  const panel = document.querySelector(".workout-timers");
  if (!panel) return;
  const now = Date.now();
  const startedAt = Date.parse(panel.dataset.startedAt);
  panel.querySelector("#workout-clock").textContent = formatTimer(
    Number.isFinite(startedAt) ? Math.max(0, Math.floor((now - startedAt) / 1000)) : 0
  );
  const timer = restTimer(panel.dataset.sessionId);
  const remaining = timer.endsAt === null ? timer.duration : Math.max(0, Math.ceil((timer.endsAt - now) / 1000));
  panel.querySelector("#rest-clock").textContent = formatTimer(remaining);
  panel.querySelector("#rest-duration").value = String(timer.duration);
  panel.querySelector('[data-rest-action="start"]').textContent = timer.endsAt === null ? "Start rest" : "Restart rest";
  const finished = timer.endsAt !== null && remaining === 0;
  panel.classList.toggle("rest-finished", finished);
  const status = panel.querySelector("#rest-status");
  const message = timer.endsAt === null ? "Starts when you check a set." : finished ? "Rest finished." : "Resting…";
  if (status.textContent !== message) status.textContent = message;
  panel.hidden = false;
}

function setRestRunning(sessionId, running) {
  const timer = restTimer(sessionId);
  timer.endsAt = running ? Date.now() + timer.duration * 1000 : null;
  saveRestTimer(sessionId, timer);
  updateWorkoutTimers();
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-rest-action]");
  if (!button) return;
  const sessionId = button.closest(".workout-timers").dataset.sessionId;
  setRestRunning(sessionId, button.dataset.restAction === "start");
});

document.addEventListener("change", (event) => {
  if (event.target.id !== "rest-duration") return;
  const sessionId = event.target.closest(".workout-timers").dataset.sessionId;
  const timer = restTimer(sessionId);
  timer.duration = Number(event.target.value);
  timer.endsAt = null;
  saveRestTimer(sessionId, timer);
  updateWorkoutTimers();
});

document.addEventListener("htmx:load", updateWorkoutTimers);
document.addEventListener("visibilitychange", updateWorkoutTimers);
window.addEventListener("pageshow", updateWorkoutTimers);
window.addEventListener("storage", (event) => {
  const panel = document.querySelector(".workout-timers");
  if (panel && (event.key === null || event.key === restTimerKey(panel.dataset.sessionId))) {
    restTimers.delete(panel.dataset.sessionId);
    updateWorkoutTimers();
  }
});
// Derive time from timestamps so background tabs and sleeping phones do not drift.
setInterval(updateWorkoutTimers, 250);

// Native number arrows emit Event; typing and pasting emit InputEvent.
// Keep step="any" for decimal entry and adjust native arrow changes before autosave.
document.addEventListener("input", (event) => {
  const input = event.target;
  if (!input.matches('#session-form input[type="number"][data-unit="lb"]') ||
      input.readOnly || input.disabled) return;
  const previous = weightValues.get(input);
  if (event.isTrusted && !(event instanceof InputEvent) && Number.isFinite(input.valueAsNumber)) {
    const baseline = Number.isFinite(previous) ? previous : 0;
    const direction = Math.sign(input.valueAsNumber - baseline);
    if (direction) {
      const value = Math.min(Number(input.max), Math.max(Number(input.min), baseline + direction * 2.5));
      input.value = String(Number(value.toFixed(4)));
    }
  }
  weightValues.set(input, input.valueAsNumber);
}, true);

function updateRoutinePreview(select) {
  const panel = select.closest(".start-panel");
  panel.querySelector(".routine-letter").textContent = select.value;
  panel.querySelector("h2").textContent = `Workout ${select.value}`;
  panel.querySelectorAll("[data-routine-preview]").forEach((preview) => {
    preview.hidden = preview.dataset.routinePreview !== select.value;
  });
}

document.addEventListener("change", (event) => {
  if (event.target.matches(".start-panel select[name='routine']")) {
    updateRoutinePreview(event.target);
  }
});

function setExerciseMinimized(card, minimized) {
  const button = card.querySelector(".exercise-toggle");
  const body = card.querySelector(".exercise-body");
  const label = minimized ? "Expand" : "Minimize";
  body.hidden = minimized;
  button.setAttribute("aria-expanded", String(!minimized));
  button.setAttribute("aria-label", `${label} ${card.getAttribute("aria-label")}`);
  button.firstChild.textContent = `${label} `;
  button.lastElementChild.textContent = minimized ? "+" : "−";
  button.hidden = false;
  exerciseViews.set(body.id, {
    minimized,
    completed: card.dataset.completed === "true",
    removed: card.dataset.removed === "true",
  });
}

document.addEventListener("click", (event) => {
  const button = event.target.closest(".exercise-toggle");
  if (!button) return;
  setExerciseMinimized(button.closest(".exercise-card"), button.getAttribute("aria-expanded") === "true");
});

// Reveal an invalid field before the browser tries to focus it on submission.
document.addEventListener("invalid", (event) => {
  const card = event.target.closest(".exercise-card");
  if (card) setExerciseMinimized(card, false);
}, true);

function updateValueChange(input) {
  const indicator = document.getElementById(input.getAttribute("aria-describedby"));
  const baseline = Number(input.dataset.default);
  const current = input.valueAsNumber;
  const direction = input.dataset.default.trim() !== "" && input.validity.valid &&
    Number.isFinite(baseline) && Number.isFinite(current) ? Math.sign(current - baseline) : 0;
  indicator.hidden = direction === 0;
  indicator.classList.toggle("increase", direction > 0);
  indicator.classList.toggle("decrease", direction < 0);
  const amount = Number(Math.abs(current - baseline).toFixed(4));
  const change = direction ? `${direction > 0 ? "+" : "-"}${amount} ${input.dataset.unit}` : "";
  indicator.firstElementChild.textContent = direction ? `${direction > 0 ? "↑" : "↓"} ${change}` : "";
  const description = direction ? `${direction > 0 ? "Increased" : "Decreased"} by ${amount} ${input.dataset.unit} from default: ${input.dataset.default} ${input.dataset.unit}` : "";
  indicator.lastElementChild.textContent = description;
  indicator.title = description;
}

document.addEventListener("htmx:load", () => {
  document.querySelectorAll('input[data-unit="lb"]').forEach((input) => {
    weightValues.set(input, input.valueAsNumber);
  });
  document.querySelectorAll(".start-panel select[name='routine']").forEach(updateRoutinePreview);
  document.querySelectorAll(".set-input input[data-default]").forEach(updateValueChange);
  document.querySelectorAll(".exercise-card").forEach((card) => {
    const previous = exerciseViews.get(card.querySelector(".exercise-body").id);
    const completed = card.dataset.completed === "true";
    const removed = card.dataset.removed === "true";
    const restored = previous?.removed && !removed;
    const newlyCollapsed = (completed && !previous?.completed) || (removed && !previous?.removed);
    setExerciseMinimized(card, restored ? false : newlyCollapsed ? true : previous?.minimized ?? (completed || removed));
  });
});

document.addEventListener("submit", (event) => {
  if (event.target.id !== "session-form" || event.submitter?.value !== "cancel") return;
  if (!window.confirm("Cancel this workout? It won’t be added to history or saved to Obsidian.")) {
    event.preventDefault();
    event.stopImmediatePropagation();
  }
}, true);

// HTMX owns requests; keep inputs in place and acknowledge the submitted edit generation.
document.addEventListener("htmx:configRequest", (event) => {
  if (event.detail.elt.id !== "session-form") return;
  const trigger = event.detail.triggeringEvent;
  const submitter = trigger && trigger.submitter;
  event.detail.parameters.action = submitter ? submitter.value : "save";
});

document.addEventListener("input", (event) => {
  if (!event.target.closest("#session-form")) return;
  if (event.target.matches(".set-input input[data-default]")) updateValueChange(event.target);
  changes += 1;
  const receipt = document.getElementById("save-status");
  if (receipt) receipt.textContent = "Unsaved changes…";
});

document.addEventListener("htmx:beforeSwap", (event) => {
  if ([409, 422].includes(event.detail.xhr.status)) {
    event.detail.shouldSwap = true;
    event.detail.isError = false;
  }
});

document.addEventListener("htmx:beforeRequest", (event) => {
  if (event.detail.elt.id !== "session-form") return;
  event.detail.xhr.gymChanges = changes;
  event.detail.xhr.gymTimerSession = document.querySelector(".workout-timers")?.dataset.sessionId;
  const receipt = document.getElementById("save-status");
  if (receipt) {
    receipt.classList.remove("save-error");
    receipt.textContent = "Saving…";
  }
  // Structural actions replace the form. Prevent newer typing in its outgoing fields.
  if (event.detail.requestConfig.parameters.action !== "save") {
    event.detail.elt.querySelectorAll("input, select, textarea, button").forEach((field) => {
      if (!field.disabled) {
        field.dataset.gymLocked = "true";
        field.disabled = true;
      }
    });
  }
});

// A successful Finish redirects before afterRequest; acknowledge its saved edits first.
document.addEventListener("htmx:beforeOnLoad", (event) => {
  const sessionId = event.detail.xhr.gymTimerSession;
  if (sessionId && event.detail.xhr.status === 200) {
    const action = event.detail.requestConfig.parameters.action;
    if (action.startsWith("complete-set:")) {
      setRestRunning(sessionId, true);
    } else if (["finish", "cancel", "discard"].includes(action)) {
      restTimers.delete(sessionId);
      try {
        localStorage.removeItem(restTimerKey(sessionId));
      } catch (_) { /* Storage may be unavailable. */ }
    }
  }
  if (event.detail.elt.id === "session-form" && event.detail.xhr.status === 200 &&
      event.detail.xhr.getResponseHeader("HX-Redirect") === "/") {
    acknowledged = Math.max(acknowledged, event.detail.xhr.gymChanges || 0);
  }
});

document.addEventListener("htmx:afterRequest", (event) => {
  if (event.detail.elt.id !== "session-form") return;
  event.detail.elt.querySelectorAll("[data-gym-locked]").forEach((field) => {
    field.disabled = false;
    delete field.dataset.gymLocked;
  });
  if (event.detail.xhr.status === 200) {
    acknowledged = Math.max(acknowledged, event.detail.xhr.gymChanges || 0);
    if (changes > acknowledged) {
      const receipt = document.getElementById("save-status");
      if (receipt) receipt.textContent = "Saving latest changes…";
    }
  }
});

document.addEventListener("htmx:sendError", () => {
  const receipt = document.getElementById("save-status");
  if (receipt) {
    receipt.textContent = "Connection lost. Keep this page open and try again; these edits are not saved yet.";
    receipt.classList.add("save-error");
  }
});

document.addEventListener("htmx:responseError", (event) => {
  if (event.detail.xhr.status !== 401) return;
  const receipt = document.getElementById("save-status");
  if (!receipt) return;
  receipt.textContent = "Your sign-in expired. Sign in in a new tab, then retry saving these edits. ";
  receipt.classList.add("save-error");
  const login = document.createElement("a");
  login.href = "/auth/login";
  login.target = "_blank";
  login.rel = "noopener";
  login.textContent = "Sign in with Google";
  receipt.append(login);
  const retry = document.createElement("button");
  retry.type = "button";
  retry.className = "text-button";
  retry.textContent = "Retry save";
  retry.addEventListener("click", () => {
    const form = document.getElementById("session-form");
    if (form) htmx.trigger(form, "input");
  });
  receipt.append(retry);
});

window.addEventListener("beforeunload", (event) => {
  if (changes > acknowledged) {
    event.preventDefault();
    event.returnValue = "";
  }
});
