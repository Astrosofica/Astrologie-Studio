// 90-start.js
//
// Alles wat bij het laden loopt, en niets anders: luisteraars, de eerste tekening, de klok.
//
// Alle bestanden delen één werkruimte en worden in deze volgorde geladen; 90-start.js
// komt achteraan en gebruikt wat hierboven staat.

try {
  kenmerk = new URLSearchParams(location.search).get("vt") || "";
} catch (e) { /* geen URLSearchParams: dan blijft de titel zoals hij is */ }
zetTitel(1);

KEURVELDEN.forEach(id => {
  const veld = document.getElementById(id);
  if (veld) { veld.addEventListener("blur", () => keurVeld(id)); }
});
// Ook bij een ander venster: geen rAF, om dezelfde reden als in zetTab.
window.addEventListener("resize", schaalAfdruk);

// De regel onder de lijst opent het venster met alle horoscopen. Eén ingang: dezelfde
// functie als de werkbalk en het menu, zodat er niet twee keer iets anders kan gebeuren.
document.getElementById("kaartenmeer").addEventListener("click", () => openOpenen());

// Rekenen hoort het wiel te laten zien: staat de gebruiker op een ander tabblad (Instellingen,
// Aspecten of de afdruk), dan springt het scherm naar Wiel. Dat gebeurt met opzet hier en niet in
// reken(), want bij het openen van de pagina bepaalt laadInstellingen() welk tabblad actief is
// (zonder settings.json opent het instellingenscherm) en dat mag reken() niet overschrijven.
document.getElementById("form").addEventListener("submit", (e) => {
  e.preventDefault();
  zetTab("wiel");
  reken();
});
document.getElementById("toon-aspecten").addEventListener("change", (e) => zetAspecten(e.target.checked));
document.getElementById("dlg-solaar-ok").addEventListener("click", berekenSolaar);
document.getElementById("inst-bewaar").addEventListener("click", bewaarInstellingen);
// De plaatszoekers hangen hun eigen 'input'-luisteraar op (maakPlaatszoeker), dus hier staat er
// geen enkele meer: één luisteraar per zoeker, ook als een veld later wordt vervangen.
document.querySelectorAll(".tabs button").forEach(b =>
  b.addEventListener("click", () => zetTab(b.dataset.tab)));

zetBewaarKnop();
document.getElementById("bewaar").addEventListener("click", async () => {
  const aanpassen = (actiefId !== null && actiefId !== undefined);
  // Altijd eerst opnieuw rekenen met wat er in het formulier staat — bij Bewaren én bij Aanpassen.
  // Zonder deze stap schrijft de knop de laatst gerekende kaart weg: een gewijzigde naam of tijd
  // komt dan niet in het bestand en het lijkt of er niets gebeurt.
  const berekend = await reken();
  if (!berekend) { return; }        // toonFout heeft de melding dan al gezet
  if (aanpassen) {
    // Hernoemen is een echte wijziging: de bewaarde kaart onder de oude naam verdwijnt. Dat vraagt
    // een bevestiging, met de oude naam erbij — anders sloopt een vergissing stil een bestaande kaart.
    const rij = kaarten.find(k => k.id === actiefId) || {};
    const oud = String(rij.naam || "").trim();
    const nieuw = String((laatste.kaart.meta || {}).naam || "").trim();
    if (oud && nieuw && oud !== nieuw &&
        !await bericht({ titel: "Horoscoop hernoemen",
          tekst: "Je past de horoscoop '" + oud + "' aan en hernoemt hem naar '" + nieuw +
            "'. De bewaarde horoscoop onder de oude naam verdwijnt. Wil je dat?",
          ja: "Hernoemen", nee: "Annuleren" })) {
      zetMeld("", "niet aangepast: de naam is niet overgenomen.");
      return;
    }
  }
  const r = await fetch("/api/bewaren", { method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kaart: laatste.kaart, id: aanpassen ? actiefId : null }) });
  const j = await r.json();
  if (!r.ok) {
    zetMeld("fout", j.fout || "onbekend");
    return;
  }
  // Na het bewaren is dit de open kaart: de knop blijft Aanpassen, ook bij een nieuwe kaart.
  actiefId = (j.id !== undefined) ? j.id : actiefId;
  klokStop();             // bewaard is bewaard: het moment ligt vast, ook als het nú was
  zetBewaarKnop();
  zetMeld("", (j.nieuw ? "nieuw bewaard: " : "bijgewerkt: ") + j.bestand);
  await laadKaarten();
});

// Het openen van het programma:
//  1. de instellingen ophalen - die beslissen het tabblad (zonder locatie: het instellingenscherm)
//     en leveren het moment van de server;
//  2. staat er een locatie, dan gaat het formulier op "Nu" met dat moment en die locatie, en wordt
//     er gewoon gerekend.
(async () => {
  await laadProfiel();
  const uit = await laadInstellingen();
  if (uit && uit.instellingen) {
    vulNu(uit.instellingen, uit.nu);
    await reken();
    klokStart();
  }
})();
laadKaarten();
laadBron();
document.querySelectorAll(".uitlegvak").forEach(vak => {
  const veld = vak.closest(".veld");
  if (!veld) { return; }
  const zet = () => plaatsUitlegvak(vak);
  veld.addEventListener("mouseenter", zet);
  veld.addEventListener("focusin", zet);
});

document.querySelectorAll(".menubalk .m").forEach(b => {
  b.addEventListener("click", (e) => {
    e.stopPropagation();
    const lijst = document.getElementById("menu-" + b.dataset.menu);
    if (!lijst) { return; }
    const wasOpen = lijst.classList.contains("open");
    sluitMenu();
    if (!wasOpen) {
      // De keuzelijst hangt onder zijn eigen menu, niet links in de balk.
      lijst.style.left = b.offsetLeft + "px";
      lijst.classList.add("open"); b.classList.add("open");
    }
  });
});
document.querySelectorAll("[data-doet]").forEach(b =>
  b.addEventListener("click", () => doet(b.dataset.doet)));
document.addEventListener("click", (e) => {
  const inBalk = e.target instanceof Element && e.target.closest("#menubalk");
  if (!inBalk) { sluitMenu(); }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { sluitMenu(); return; }
  if (e.key === "F9") { e.preventDefault(); doet("reken"); return; }
  // F5 haalt de horoscoop van dit moment terug. Dat is wat hij met
  // Ctrl+F5 deed: de pagina verversen om weer bij "Nu" te komen. Het verschil is er één van
  // belangrijkheid - deze weg vraagt het als er niet-bewaard werk in het formulier staat, terwijl
  // de browserverversing dat stil weggooide. Ctrl+F5 blijft de gewone verversing van de browser.
  if (e.key === "F5" && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) {
    e.preventDefault(); doet("nu"); return;
  }
  const ctrl = (e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey;
  if (ctrl && e.key.toLowerCase() === "s") { e.preventDefault(); doet("bewaar"); return; }
  if (ctrl && e.key.toLowerCase() === "q") { e.preventDefault(); doet("afsluiten"); return; }
  // Ctrl+N en Ctrl+O werken in het gebundelde venster (WebView2 zonder browserbalk); in een gewone
  // browser houdt de browser ze zelf. Daarom staan ze niet als sneltoets in het menu vermeld.
  if (ctrl && e.key.toLowerCase() === "n") { e.preventDefault(); doet("nieuw"); return; }
  if (ctrl && e.key.toLowerCase() === "o") { e.preventDefault(); doet("openen"); return; }
});
// Zie de CSS: buiten Windows is "Segoe UI" niet te vinden en lost fontconfig hem verkeerd op.
if (!/Windows/i.test(navigator.userAgent)) { document.documentElement.classList.add("niet-windows"); }
["input", "change"].forEach(soort =>
  document.getElementById("form").addEventListener(soort, () => { vies = true; klokStop(); }));

// Komt het venster terug in beeld, dan meteen bijwerken. Een browser vertraagt de timers van een
// verborgen venster tot ongeveer één per minuut, en dan zou je naar de kaart van een minuut oud
// kijken - precies de vertraging die de klok moest wegnemen.
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && klokStand()) { klokTik(); }
});

maakSleepbaar(document.getElementById("dlg-openen"));

document.getElementById("dlg-bericht-ja").addEventListener("click", () => antwoordBericht(true));
fetch("/api/venster?id=" + encodeURIComponent(VENSTER_ID), { method: "POST" }).catch(() => {});
addEventListener("pagehide", meldWeg);
addEventListener("beforeunload", meldWeg);
addEventListener("resize", () => {
  clearTimeout(vensterTik);
  vensterTik = setTimeout(meldVensterstaat, 600);
});
// Bij het sluiten: de laatst gemeten stand, geen nieuwe meting. Een venster dat uit volledig scherm
// komt voordat het sluit zou anders zijn rustmaat melden en de stand kwijtraken.
// Na afsluiten in volledig scherm opende het programma elke keer op de standaardmaat.
addEventListener("pagehide", () => meldVensterstaat(false));
meldVensterstaat();
// Een venster dat met `--start-fullscreen` opent is een fractie later pas schermvullend; komt daar
// geen resize meer achteraan, dan is dit de meting die de stand vastlegt.
setTimeout(meldVensterstaat, 1500);

try {
  const bewaard = Number(localStorage.getItem("astrologie-studio.weergave"));
  if (WEERGAVE.includes(bewaard)) { weergave = bewaard; }
} catch (e) { /* privémodus */ }
if (weergave !== 100) {
  document.documentElement.style.zoom = String(weergave / 100);
  document.documentElement.dataset.weergave = String(weergave);
}
zetWeergaveVinkjes();
zetWeergaveKnoppen();
dlgOpenen.querySelector("#dlg-openen-ok").addEventListener("click", openGekozen);
dlgOpenen.querySelector("#dlg-openen-lijst").addEventListener("click", (e) => {
  // Het kruisje in de rij verwijdert via dezelfde functie als het paneel; het mag de rij niet ook
  // nog kiezen, dus deze tak komt eerst.
  const weg = e.target.closest("[data-weg]");
  if (weg) { verwijderKaart(Number(weg.dataset.weg)); return; }
  const kop = e.target.closest("[data-sorteer]");
  if (kop) {
    const kolom = kop.dataset.sorteer;
    if (dlgSorteer === kolom) {
      dlgRichting = (dlgRichting === "op") ? "af" : "op";
    } else {
      dlgSorteer = kolom;
      // Datum: nieuwste bovenaan (zoals het paneel); naam: A→Z.
      dlgRichting = (kolom === "datum") ? "af" : "op";
    }
    tekenOpenen();
    const rijen = [...dlgOpenen.querySelectorAll("tbody tr")];
    if (rijen.length) { rijen[0].focus(); }
    return;
  }
  const tr = e.target.closest("tbody tr");
  if (tr) { kiesRij(tr); }
});
dlgOpenen.querySelector("#dlg-openen-lijst").addEventListener("dblclick", (e) => {
  if (e.target.closest("[data-weg]") || e.target.closest("[data-sorteer]")) { return; }
  const tr = e.target.closest("tbody tr");
  if (tr) { kiesRij(tr); openGekozen(); }
});
dlgOpenen.querySelector("#dlg-openen-zoek").addEventListener("input", (e) => {
  dlgZoek = e.target.value;
  tekenOpenen();
});

// Alle vensters delen één bedrading: klik naast het venster of op iets met `data-sluit` sluit het.
document.addEventListener("click", (e) => {
  if (!(e.target instanceof Element)) { return; }
  const vlak = e.target.closest(".dialoogvlak");
  if (!vlak || vlak.hidden) { return; }
  if (e.target === vlak || e.target.closest("[data-sluit]")) { sluitDialoog(); }
});

document.addEventListener("keydown", (e) => {
  const vlak = zichtbaarDialoog();
  if (!vlak) { return; }
  if (e.key === "Escape") { e.preventDefault(); sluitDialoog(); return; }
  if (vlak.id === "dlg-bericht") {
    if (e.key === "Enter") { e.preventDefault(); antwoordBericht(true); }
    return;
  }
  if (vlak.id === "dlg-solaar") {
    if (e.key === "Enter") { e.preventDefault(); berekenSolaar(); }
    return;
  }
  if (vlak.id !== "dlg-openen") { return; }
  if (e.key === "Enter") { e.preventDefault(); openGekozen(); }
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    const rijen = [...dlgOpenen.querySelectorAll("tbody tr")];
    if (!rijen.length) { return; }
    e.preventDefault();
    const nu = rijen.findIndex(r => r.classList.contains("gekozen"));
    const volgende = Math.max(0, Math.min(rijen.length - 1,
      (nu < 0 ? 0 : nu + (e.key === "ArrowDown" ? 1 : -1))));
    kiesRij(rijen[volgende]);
    rijen[volgende].focus();
  }
});
if (toonAspectenVak) { toonAspectenVak.addEventListener("change", zetVinkjes); }
if (toonChironVak) {
  toonChironVak.addEventListener("change", zetVinkjes);
  toonChironVak.addEventListener("change", () => reken(true));
}
zetVinkjes();
