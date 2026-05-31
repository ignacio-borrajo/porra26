// Theme toggle
document.querySelectorAll("[data-theme-toggle]").forEach(btn => {
  btn.addEventListener("click", () => {
    const html = document.documentElement;
    const next = html.dataset.theme === "dark" ? "light" : "dark";
    html.dataset.theme = next;
    fetch("/theme/", { method: "POST", headers: { "X-CSRFToken": getCookie("csrftoken") }, body: new URLSearchParams({ theme: next }) }).catch(() => {});
  });
});

function getCookie(name) {
  const v = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
  return v ? v.pop() : "";
}
