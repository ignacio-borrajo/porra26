function pad(n) { return String(n).padStart(2, "0"); }

function update(el, target) {
  const ms = target - Date.now();
  if (ms <= 0) { el.textContent = "00:00:00"; el.classList.add("expired"); return; }
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms / 60000) % 60);
  const s = Math.floor((ms / 1000) % 60);
  el.textContent = `${pad(h)}:${pad(m)}:${pad(s)}`;
  if (ms < 3600000) el.classList.add("under-hour");
}

document.querySelectorAll("[data-countdown-to]").forEach((el) => {
  const target = new Date(el.dataset.countdownTo).getTime();
  update(el, target);
  setInterval(() => update(el, target), 1000);
});
