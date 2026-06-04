function getCsrf() {
  const el = document.querySelector("[name=csrfmiddlewaretoken]");
  if (el) return el.value;
  const m = document.cookie.match(/(^|;)\s*csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[2]) : "";
}

function showToast(text) {
  const t = document.createElement("div");
  t.className = "glass pop toast";
  t.style.cssText =
    "position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:80;padding:13px 20px;border-radius:16px;display:flex;align-items:center;gap:10px";
  t.textContent = text;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2600);
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-resend-invite-url]");
  if (!btn) return;
  e.preventDefault();
  const url = btn.dataset.resendInviteUrl;
  btn.disabled = true;
  fetch(url, {
    method: "POST",
    headers: { "X-CSRFToken": getCsrf(), Accept: "application/json" },
  })
    .then((r) => r.json().catch(() => null))
    .then((data) => {
      if (data && data.ok) {
        const verb = data.purpose === "welcome" ? "bienvenida" : "recuperación";
        showToast(`Email de ${verb} enviado a ${data.email}`);
      } else {
        showToast("No se pudo enviar el email.");
      }
    })
    .catch(() => showToast("Error de red al enviar el email."))
    .finally(() => {
      btn.disabled = false;
    });
});
