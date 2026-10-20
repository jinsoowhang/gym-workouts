"use strict";

let changes = 0;
let acknowledged = 0;
const minimizedExercises = new Set();

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
  if (minimized) minimizedExercises.add(body.id);
  else minimizedExercises.delete(body.id);
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
  document.querySelectorAll(".set-input input[data-default]").forEach(updateValueChange);
  document.querySelectorAll(".exercise-card").forEach((card) => {
    setExerciseMinimized(card, minimizedExercises.has(card.querySelector(".exercise-body").id));
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
