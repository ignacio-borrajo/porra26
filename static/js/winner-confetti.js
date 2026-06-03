import { openModal, closeModal } from "./modal.js";

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/);
  return m ? m[1] : "";
}

function blast() {
  if (!window.confetti) return;
  window.confetti({
    particleCount: 140,
    spread: 80,
    origin: { y: 0.4 },
    startVelocity: 45,
    scalar: 1.1,
  });
  const end = Date.now() + 2500;
  (function frame() {
    window.confetti({
      particleCount: 5,
      angle: 270,
      spread: 70,
      startVelocity: 35,
      origin: { x: Math.random(), y: 0 },
      gravity: 1.1,
      scalar: 0.9,
    });
    if (Date.now() < end) requestAnimationFrame(frame);
  })();
}

const observer = new MutationObserver(() => {
  const modal = document.querySelector(".winner-modal:not([data-confetti-fired])");
  if (modal) {
    modal.setAttribute("data-confetti-fired", "1");
    setTimeout(blast, 80);
  }
});
observer.observe(document.body, { childList: true, subtree: true });

document.addEventListener("click", async (event) => {
  const btn = event.target.closest("[data-winner-confirm]");
  if (!btn) return;
  event.preventDefault();
  const modal = btn.closest(".winner-modal");
  if (!modal) return;
  const url = modal.dataset.seenUrl;
  const res = await fetch(url, {
    method: "POST",
    headers: { "X-CSRFToken": getCsrf(), "X-Modal": "1" },
    credentials: "same-origin",
  });
  const next = res.headers.get("X-Modal-Next");
  if (next) {
    await openModal(next);
  } else {
    closeModal();
  }
});
