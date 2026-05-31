function openModal(url) {
  fetch(url, { headers: { "X-Requested-With": "fetch" } })
    .then((r) => r.text())
    .then((html) => {
      const wrap = document.createElement("div");
      wrap.className = "modal-overlay";
      wrap.style.cssText = "position:fixed;inset:0;z-index:90;background:rgba(0,0,0,0.55);backdrop-filter:blur(8px);display:grid;place-items:center";
      wrap.innerHTML = html;
      document.body.appendChild(wrap);

      const onClose = () => wrap.remove();
      wrap.addEventListener("click", (e) => { if (e.target === wrap) onClose(); });
      document.addEventListener("keydown", (e) => { if (e.key === "Escape") onClose(); }, { once: true });
    });
}

document.addEventListener("click", (e) => {
  const a = e.target.closest("[data-modal-url]");
  if (!a) return;
  e.preventDefault();
  openModal(a.dataset.modalUrl);
});
