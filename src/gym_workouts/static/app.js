"use strict";

let changes = 0;
let acknowledged = 0;

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
