"use strict";

const $ = (id) => document.getElementById(id);

let lastTrace = null;

function show(el, on) {
  el.classList.toggle("hidden", on === false);
}

async function loadHealth() {
  try {
    const res = await fetch("/api/health");
    const health = await res.json();
    $("pill-version").textContent = "v" + health.version;
    $("pill-model").textContent = health.model;
    const key = $("pill-key");
    if (health.key_present) {
      key.textContent = "API key ready";
      key.classList.add("ok");
    } else {
      key.textContent = "No key \u2014 set PRAETOR_OPENROUTER_KEY";
      key.classList.add("warn");
    }
  } catch (err) {
    $("pill-key").textContent = "Console offline";
  }
}

function stepRow(step) {
  const li = document.createElement("li");

  const head = document.createElement("div");
  head.className = "step-head";

  const name = document.createElement("span");
  name.className = "step-name";
  name.textContent = step.tool;

  const badge = document.createElement("span");
  badge.className = "badge " + (step.ok ? "ok" : "fail");
  badge.textContent = step.ok ? "ok" : (step.error || "failed");

  const dur = document.createElement("span");
  dur.className = "step-dur";
  dur.textContent = step.duration_s.toFixed(2) + " s";

  head.append(name, badge, dur);

  const args = document.createElement("pre");
  args.className = "step-args";
  args.textContent = JSON.stringify(step.arguments);

  li.append(head, args);
  return li;
}

function chip(label, value) {
  const el = document.createElement("div");
  el.className = "chip";
  const l = document.createElement("span");
  l.textContent = label;
  const v = document.createElement("strong");
  v.textContent = String(value);
  el.append(l, v);
  return el;
}

function renderResult(body) {
  const r = body.result;
  lastTrace = body.trace;

  const banner = $("status-banner");
  banner.className = "banner " + r.status;
  banner.textContent = r.status;
  show(banner);

  $("answer").textContent = r.answer || "(no answer)";
  $("steps-list").replaceChildren(...r.steps.map(stepRow));

  const chips = [chip("tool calls", r.tool_calls), chip("elapsed", r.elapsed_s.toFixed(2) + " s")];
  if (r.usage) {
    for (const [key, value] of Object.entries(r.usage)) chips.push(chip(key, value));
  }
  $("metrics").replaceChildren(...chips);

  const notes = r.errors.length ? r.errors : ["(no audit notes)"];
  $("audit").replaceChildren(
    ...notes.map((note) => {
      const li = document.createElement("li");
      li.textContent = note;
      return li;
    })
  );
  $("workspace").textContent = "workspace: " + body.workspace;

  show($("results"));
  show($("error-card"), false);
}

async function run() {
  const task = $("task").value.trim();
  if (!task) return;
  const button = $("run");
  button.disabled = true;
  button.textContent = "Running\u2026";
  try {
    const payload = { task: task, max_steps: Number($("steps").value) };
    const model = $("model").value.trim();
    if (model) payload.model = model;
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({ error: "HTTP " + res.status }));
      throw new Error(detail.error || "HTTP " + res.status);
    }
    renderResult(await res.json());
  } catch (err) {
    $("error-text").textContent = String((err && err.message) || err);
    show($("error-card"));
  } finally {
    button.disabled = false;
    button.textContent = "Run agent";
  }
}

function downloadTrace() {
  if (!lastTrace) return;
  const lines = lastTrace.map((span) => JSON.stringify(span)).join("\n") + "\n";
  const blob = new Blob([lines], { type: "application/x-ndjson" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "praetor-trace.jsonl";
  a.click();
  URL.revokeObjectURL(url);
}

window.addEventListener("DOMContentLoaded", () => {
  loadHealth();
  $("run").addEventListener("click", run);
  $("download").addEventListener("click", downloadTrace);
  $("steps").addEventListener("input", () => {
    $("steps-out").textContent = $("steps").value;
  });
});
