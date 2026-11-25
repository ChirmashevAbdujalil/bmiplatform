// BMI Platforma — umumiy skriptlar
document.addEventListener("DOMContentLoaded", () => {
  // Jadvaldagi belgilash (ommaviy amallar)
  const master = document.querySelector("[data-check-all]");
  const boxes = () => Array.from(document.querySelectorAll("input[data-row-check]"));
  const bar = document.querySelector(".bulk-bar");
  const counter = document.querySelector("[data-selected-count]");
  const refresh = () => {
    const n = boxes().filter((b) => b.checked).length;
    if (counter) counter.textContent = n;
    if (bar) bar.classList.toggle("show", n > 0);
  };
  if (master) master.addEventListener("change", () => { boxes().forEach((b) => (b.checked = master.checked)); refresh(); });
  boxes().forEach((b) => b.addEventListener("change", refresh));

  // Tasdiqlash so‘raladigan tugmalar
  document.querySelectorAll("[data-confirm]").forEach((el) => {
    el.addEventListener("click", (e) => { if (!confirm(el.dataset.confirm)) e.preventDefault(); });
  });

  // Filtr formalari: fakultet o‘zgarsa avtomatik yuborish
  document.querySelectorAll("form[data-autosubmit] select").forEach((s) => {
    s.addEventListener("change", () => s.form.submit());
  });

  // Baholash formasi: umumiy ballni jonli hisoblash
  const inputs = document.querySelectorAll(".score-input");
  const totalEl = document.querySelector("[data-score-total]");
  const calc = () => {
    let sum = 0;
    inputs.forEach((i) => { const v = parseFloat(i.value); if (!isNaN(v)) sum += Math.min(v, parseFloat(i.max)); });
    if (totalEl) totalEl.textContent = sum.toFixed(2);
  };
  inputs.forEach((i) => i.addEventListener("input", calc));
  calc();

  // Mobil menyu: tashqarisiga bosilganda yopish
  document.addEventListener("click", (e) => {
    const sb = document.getElementById("sidebar");
    if (sb && sb.classList.contains("open") && !sb.contains(e.target) && !e.target.closest(".icon-btn")) sb.classList.remove("open");
  });
});
