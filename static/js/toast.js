// Toast notifications from Django messages
const container = document.getElementById("dj-messages");
if (container) {
  container.querySelectorAll("[data-msg]").forEach(el => {
    const tag = el.dataset.tag || "info";
    const msg = el.dataset.msg;
    const toast = document.createElement("div");
    toast.className = `toast toast-${tag}`;
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  });
}
