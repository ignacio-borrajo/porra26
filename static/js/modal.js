const STATE = { wrap: null, escListener: null, dirty: false };

function close({ reloadIfDirty = true } = {}) {
  if (!STATE.wrap) return;
  const shouldReload = reloadIfDirty && STATE.dirty;
  STATE.wrap.remove();
  document.removeEventListener("keydown", STATE.escListener);
  STATE.wrap = null;
  STATE.escListener = null;
  if (shouldReload) {
    STATE.dirty = false;
    window.location.reload();
  }
}

function mount(html) {
  close({ reloadIfDirty: false });
  const wrap = document.createElement("div");
  wrap.className = "ovl";
  wrap.innerHTML = html;
  wrap.addEventListener("click", (e) => {
    if (e.target === wrap) close();
  });
  wrap.addEventListener("click", (e) => {
    if (e.target.closest("[data-modal-close]")) close();
  });
  const form = wrap.querySelector("form");
  if (form) form.addEventListener("submit", onSubmit);
  STATE.wrap = wrap;
  STATE.escListener = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", STATE.escListener);
  document.body.appendChild(wrap);
}

async function onSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const submitter = event.submitter;
  if (submitter && submitter.name) {
    data.append(submitter.name, submitter.value || "");
  }
  const res = await fetch(form.action, {
    method: "POST",
    body: data,
    headers: { "X-Modal": "1" },
  });
  const next = res.headers.get("X-Modal-Next");
  if (next) {
    STATE.dirty = true;
    await openModal(next);
    return;
  }
  const redirect = res.headers.get("X-Modal-Redirect");
  if (redirect) {
    window.location.assign(redirect);
    return;
  }
  if (res.headers.get("X-Modal-Errors") === "1") {
    const html = await res.text();
    mount(html);
    return;
  }
  if (res.ok) {
    close();
    window.location.reload();
  }
}

export async function openModal(url) {
  const res = await fetch(url, { headers: { "X-Modal": "1" } });
  const html = await res.text();
  mount(html);
}

export function closeModal() {
  close();
}

document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-modal-url]");
  if (!trigger) return;
  event.preventDefault();
  openModal(trigger.dataset.modalUrl);
});

document.addEventListener("click", (event) => {
  const step = event.target.closest("[data-step]");
  if (!step) return;
  const input = step.parentElement.querySelector("input[name]");
  if (!input) return;
  const min = parseInt(input.dataset.min ?? "0", 10);
  const max = parseInt(input.dataset.max ?? "99", 10);
  const cur = parseInt(input.value, 10) || 0;
  const next = Math.max(min, Math.min(max, cur + parseInt(step.dataset.step, 10)));
  input.value = String(next);
});
