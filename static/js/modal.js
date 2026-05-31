const STATE = { wrap: null, escListener: null };

function close() {
  if (!STATE.wrap) return;
  STATE.wrap.remove();
  document.removeEventListener("keydown", STATE.escListener);
  STATE.wrap = null;
  STATE.escListener = null;
}

function mount(html) {
  close();
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
  const res = await fetch(form.action, {
    method: "POST",
    body: data,
    headers: { "X-Modal": "1" },
  });
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
