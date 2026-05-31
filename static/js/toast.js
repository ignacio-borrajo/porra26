const box = document.getElementById("dj-messages");
if (box) {
  for (const span of box.querySelectorAll("[data-msg]")) {
    const t = document.createElement("div");
    t.className = "glass pop toast";
    t.style.cssText = "position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:80;padding:13px 20px;border-radius:16px;display:flex;align-items:center;gap:10px";
    t.textContent = span.dataset.msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 2600);
  }
}
