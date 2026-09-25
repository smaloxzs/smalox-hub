/* Smalox Hub Website: Einblenden, Zähler, Kachel-Licht und die interaktive Demo. Keine Abhängigkeiten. */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const ruhig = matchMedia("(prefers-reduced-motion: reduce)").matches;

/* Einblenden beim Scrollen (leicht versetzt je Gruppe) */
const beobachter = new IntersectionObserver((eintraege) => {
  for (const e of eintraege) if (e.isIntersecting) { e.target.classList.add("sichtbar"); beobachter.unobserve(e.target); }
}, { threshold: 0.12 });
$$(".zeige").forEach((el, i) => { el.style.transitionDelay = `${(i % 4) * 70}ms`; beobachter.observe(el); });

/* Zahlen hochzählen */
$$("[data-zaehlen]").forEach((el) => {
  const ziel = +el.dataset.zaehlen;
  if (ruhig) return;
  el.textContent = "0";
  new IntersectionObserver(([e], o) => {
    if (!e.isIntersecting) return;
    o.disconnect();
    const start = performance.now();
    const schritt = (t) => {
      const p = Math.min(1, (t - start) / 1200);
      el.textContent = Math.round(ziel * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(schritt);
    };
    requestAnimationFrame(schritt);
  }).observe(el);
});

/* Licht folgt der Maus auf den Kacheln */
$$(".kachel").forEach((k) => k.addEventListener("pointermove", (e) => {
  const r = k.getBoundingClientRect();
  k.style.setProperty("--mx", `${e.clientX - r.left}px`);
  k.style.setProperty("--my", `${e.clientY - r.top}px`);
}));

/* ───── Demo: Reiter ───── */
$$(".demo-nav button").forEach((b) => b.addEventListener("click", () => {
  $$(".demo-nav button").forEach((x) => x.setAttribute("aria-selected", x === b));
  $$(".demo-seite").forEach((s) => s.classList.toggle("aktiv", s.dataset.seite === b.dataset.tab));
  if (b.dataset.tab === "zeit") saeulenZeichnen();
}));

/* To-Dos */
function todosAktualisieren() {
  const alle = $$("#todo-liste li"), fertig = alle.filter((li) => li.querySelector("input").checked);
  alle.forEach((li) => li.classList.toggle("fertig", li.querySelector("input").checked));
  const p = alle.length ? Math.round((fertig.length / alle.length) * 100) : 0;
  $("#todo-balken").style.width = p + "%";
  $("#todo-prozent").textContent = p === 100 ? "Alles erledigt! 🎉" : `${p} % erledigt`;
  $("#todo-zaehler").textContent = `${alle.length - fertig.length} offen`;
}
$("#todo-liste").addEventListener("change", todosAktualisieren);
$("#todo-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("#todo-text").value.trim();
  if (!text) return;
  const li = document.createElement("li");
  li.innerHTML = `<label><input type="checkbox"><span></span></label><em>neu</em>`;
  li.querySelector("span").textContent = text;
  $("#todo-liste").prepend(li);
  $("#todo-text").value = "";
  todosAktualisieren();
});

/* Dropbox: erkennt einfache Muster und zeigt, wohin es einsortiert würde */
const ZIELE = [
  [/https?:\/\//i, "✦", "Destille", "Link wird ausgelesen und in To-Dos verwandelt"],
  [/sperr|deadswitch|pakt/i, "⚑", "Deadswitch-Vorschlag", "Deadline mit Sperre, du bestätigst per Klick"],
  [/kaufen|€|euro/i, "◎", "Wunschliste", "mit Preis, für später"],
  [/idee|gedanke|merk/i, "🧠", "Second Brain", "Notiz im passenden Bereich"],
  [/projekt|für .+ noch/i, "▦", "Projekt-Aufgabe", "unter „Nächste Schritte“ im Projekt"],
  [/morgen|heute|montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag|uhr|\d{1,2}\.\d{1,2}/i, "📅", "To-Do im Kalender", "mit Datum, taucht im Kalender auf"],
];
$$(".bsp button").forEach((b) => b.addEventListener("click", () => { $("#dropbox-text").value = b.dataset.bsp; $("#dropbox-text").focus(); }));
$("#dropbox-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("#dropbox-text").value.trim();
  if (!text) return;
  const flug = $("#dropbox-flug");
  flug.innerHTML = `<div class="denkt"><i></i><i></i><i></i> Claude sortiert ein …</div>`;
  const [, ik, ziel, info] = ZIELE.find(([muster]) => muster.test(text)) || [null, "✓", "To-Do", "in deiner To-Do-Liste"];
  setTimeout(() => {
    flug.innerHTML = `<div class="treffer"><span class="ziel-ik"></span><div><b></b><small></small></div></div>`;
    $(".ziel-ik", flug).textContent = ik;
    $("b", flug).textContent = `→ ${ziel}`;
    $("small", flug).textContent = `„${text.slice(0, 70)}“ · ${info}`;
  }, ruhig ? 0 : 900);
});

/* Deadswitch: Countdown und Schritte */
let rest = 2 * 3600 + 59 * 60 + 59;
setInterval(() => {
  rest = rest > 0 ? rest - 1 : 3 * 3600;
  const h = Math.floor(rest / 3600), m = Math.floor(rest / 60) % 60, s = rest % 60;
  $("#countdown").textContent = `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}, 1000);
$("#ds-schritte").addEventListener("change", () => {
  const alle = $$("#ds-schritte input"), fertig = alle.filter((i) => i.checked).length;
  $$("#ds-schritte li").forEach((li) => li.classList.toggle("fertig", li.querySelector("input").checked));
  $("#ds-balken").style.width = `${(fertig / alle.length) * 100}%`;
  $("#ds-text").textContent = fertig === alle.length ? "Alle Schritte fertig, Sperre bleibt aus ✓" : `${fertig}/${alle.length} Schritte`;
});
$$("#ds-schritte li").forEach((li) => li.classList.toggle("fertig", li.querySelector("input").checked));

/* Bildschirmzeit: gestapelte Säulen */
const WOCHE = [["Mo", 3.1, 1.2, 1.4, .6], ["Di", 4.2, .8, 1.1, .3], ["Mi", 2.4, 1.5, 2.0, 1.1], ["Do", 4.8, 1.0, .7, .2],
  ["Fr", 3.3, .6, 1.8, 1.4], ["Sa", 1.2, .9, 2.4, 2.6], ["So", 1.6, 1.8, 1.5, 1.0]];
const FARBEN = ["var(--blau)", "var(--lila)", "var(--pink)", "var(--gelb)"];
function saeulenZeichnen() {
  const max = Math.max(...WOCHE.map(([, ...w]) => w.reduce((a, b) => a + b)));
  const box = $("#saeulen");
  box.innerHTML = WOCHE.map(([tag, ...werte]) => {
    const summe = werte.reduce((a, b) => a + b);
    return `<div class="tag-saeule"><span>${tag}</span><div class="tipp">${tag}: ${summe.toFixed(1).replace(".", ",")} Std · Fokus ${Math.round(((werte[0] + werte[1]) / summe) * 100)} %</div>
      ${werte.map((w, i) => `<i style="height:0;background:${FARBEN[i]}" data-h="${(w / max) * 100}"></i>`).join("")}</div>`;
  }).join("");
  requestAnimationFrame(() => requestAnimationFrame(() => $$("#saeulen i").forEach((i) => { i.style.height = i.dataset.h + "%"; })));
  const alle = WOCHE.reduce((a, [, ...w]) => a + w.reduce((x, y) => x + y), 0), fokus = WOCHE.reduce((a, [, p, l]) => a + p + l, 0);
  $("#fokus-chip").textContent = `${Math.round((fokus / alle) * 100)} % Fokus`;
}

/* Wunschliste: Summe rechnet mit */
$("#wunsch-liste").addEventListener("change", () => {
  let offen = 0;
  $$("#wunsch-liste li").forEach((li) => {
    const gekauft = li.querySelector("input").checked;
    li.classList.toggle("fertig", gekauft);
    if (!gekauft) offen += +li.dataset.preis;
  });
  $("#wunsch-summe").textContent = `${offen.toLocaleString("de-DE", { minimumFractionDigits: offen % 1 ? 2 : 0 })} € offen`;
});

/* Ring in der Deadswitch-Kachel läuft beim Sichtbarwerden */
const ring = $(".ring");
if (ring) new IntersectionObserver(([e], o) => { if (e.isIntersecting) { ring.style.strokeDashoffset = "60"; o.disconnect(); } }).observe(ring);

todosAktualisieren();
