// 60-scherm.js
//
// Het venster zelf: menu's, tabbladen, dialogen, de klok en de weergave.
//
// Alle bestanden delen één werkruimte en worden in deze volgorde geladen; 90-start.js
// komt achteraan en gebruikt wat hierboven staat.


// De knop hoort bij het register: staat de techniek niet aan, dan bestaat er geen tab (en blijft
// jaar 1 letterlijk ongewijzigd).
// mee, maar de techniektabs worden bij het laden aangemaakt en `appendChild` zet ze er daarna achter -
// dus schuift deze knop telkens naar het eind terug.
function zetAfdrukAchteraan() {
  const balk = document.querySelector(".tabs");
  const knop = balk ? balk.querySelector("button[data-tab='afdruk']") : null;
  if (balk && knop && balk.lastElementChild !== knop) { balk.appendChild(knop); }
}

function zetTab(naam) {
  // De transits bestaan niet zonder radix: de knop is uitgegrijsd, en dit is het vangnet
  // voor elke andere weg naar deze tab (menu, sneltoets).
  if (naam === "transits" && !trMag()) { naam = "wiel"; }
  // (Dezelfde grendel als bij de transits, die dan uitgegrijsd zijn.) Zonder radix - en op de kaart
  // van "Nu", waar de leeftijd nul is - valt er niets te progresseren.
  if (naam === "progressies" && !prMag()) { naam = "wiel"; }
  document.querySelectorAll(".tabs button").forEach(b =>
    b.classList.toggle("actief", b.dataset.tab === naam));
  document.querySelectorAll(".tab").forEach(x =>
    x.classList.toggle("actief", x.id === "tab-" + naam));
  // De kolom met de gegevens en de bewaarde kaarten hoort bij de kaart, dus hij staat op elke tab
  // Eén element dat meeverhuist naar de rij van de actieve tab; op de
  // Afdruk-tab is er geen rij en blijft hij in de vorige tab staan, die dan verborgen is.
  const rij = document.querySelector("#tab-" + naam + " .kolomrij");
  const kolom = document.getElementById("zijkolom");
  if (rij && kolom && kolom.parentNode !== rij) rij.appendChild(kolom);
  // Het A4-blad is pas te meten als de tab zichtbaar is. Bewust geen requestAnimationFrame: in een
  // venster dat als verborgen geldt (gemeten in de testbrowser) vuurt dat niet, en dan
  // bleef de preview op de terugvalmaat staan. Een directe aanroep leest de layout toch al (de
  // getBoundingClientRect hieronder dwingt een reflow af), dus dat is ook nog eens voorspelbaar.
  if (naam === "afdruk") {
    schaalAfdruk();
    // Staat de afdruk op de bi-stand, dan wordt het vel hier opnieuw opgebouwd: de leeftijd of het
    // moment kan intussen veranderd zijn, en een vel van een oude leeftijd is een verkeerde afdruk.
    if (drukBi && laatste) { zetAfdruk(laatste); }
  }
  // De tik van "Huidige transits" hangt aan de zichtbare tab: hij stopt zodra je de transits verlaat
  // en begint weer bij terugkomst.
  trKlok();
  // De momentopname van de progressies is van **vandaag**, dus hij wordt bij elk bezoek aan de tab
  // opnieuw gevraagd - anders staat er de leeftijd van de vorige keer, of "bereken eerst een
  // horoscoop" terwijl er allang een kaart staat (gemeten).
  if (naam === "progressies" && prGebouwd) { prStandNu(); }
}

function sluitMenu() {
  document.querySelectorAll(".keuzelijst.open").forEach(l => l.classList.remove("open"));
  document.querySelectorAll(".menubalk .m.open").forEach(b => b.classList.remove("open"));
}

// Het vinkje in Beeld en de stand van de werkbalkknop volgen de echte schakelaar (#toon-aspecten),
// zodat menu, knop en vinkje nooit uit elkaar kunnen lopen.
function zetVinkjes() {
  // Elk vinkje volgt zijn eigen schakelaar (er zijn er nu twee: aspectlijnen en Chiron).
  // Eerder zette deze functie álle vinkjes op de stand van de aspecten; met een tweede schakelaar zou
  // het vinkje bij Chiron dus de aspectstand tonen.
  document.querySelectorAll("[data-doet^='vinkje:']").forEach(b => {
    const vak = document.getElementById(b.dataset.doet.slice(7));
    const merk = b.querySelector("[data-vink]");
    if (merk) { merk.textContent = (vak && vak.checked) ? "\u2713" : ""; }
  });
  const v = document.getElementById("toon-aspecten");
  const aan = !!(v && v.checked);
  const wb = document.getElementById("wb-aspecten");
  if (wb) { wb.classList.toggle("aan", aan); wb.setAttribute("aria-pressed", aan ? "true" : "false"); }
}

function doet(wat) {
  if (wat === "nieuw") { nieuwKaart(); }
  else if (wat === "openen") { openOpenen(); }
  else if (wat === "bewaar") { document.getElementById("bewaar").click(); }
  else if (wat === "reken") { document.getElementById("form").requestSubmit(); }
  else if (wat === "print") { drukA4Af(); }
  else if (wat === "print-lijst") { drukLijstAf(); }
  else if (wat === "print-lijst-progressies") { prDrukLijstAf(); }
  else if (wat === "bewaar-png") { bewaarWielAlsPng(); }
  else if (wat === "nu") { nuKaart(); }
  else if (wat === "solaar") { openSolaar(); }
  else if (wat === "cursus") { openInstellingen(); }
  else if (wat === "instellingen") { openInstellingen(); }
  else if (wat === "over") { openOver(); }
  else if (wat === "afsluiten") { sluitAf(); }
  else if (wat.slice(0, 9) === "weergave:") { zetWeergave(wat.slice(9)); }
  else if (wat.slice(0, 13) === "weergavestap:") { weergaveStap(Number(wat.slice(13))); }
  else if (wat.slice(0, 4) === "tab:") { zetTab(wat.slice(4)); }
  else if (wat.slice(0, 7) === "vinkje:") {
    const v = document.getElementById(wat.slice(7));
    if (v) { v.checked = !v.checked; v.dispatchEvent(new Event("change", { bubbles: true })); }
  }
  sluitMenu();
}

// --- de klokstand -------------------------------------------------------------------------------
//
// Zolang het scherm de horoscoop van **dit moment** toont, wordt die elke 20 seconden opnieuw
// gerekend. Dat is geen nieuwe berekening: het is de gewone weg met een nieuw moment erin (de tijd
// van de server, via /api/nu). Je ziet de standen en de cuspen dan langzaam opschuiven - de
// ascendant 20' per minuut, de cuspen 14' tot 29' - en na een half uur staat het hele wiel een
// kwartslag verder.
//
// Er is géén schakelaar en géén keuzelijst met intervallen: de **stand** is de schakelaar. Zodra er
// in het formulier wordt getypt, een andere horoscoop wordt geopend, of de kaart wordt bewaard,
// stopt de klok - want dan is het geen "nu" meer maar een horoscoop die je aan het maken bent.
//
// Twintig seconden is een bewuste keuze; de kosten zijn klein (gemeten: 12 ms rekenen op de
// server, 36-50 ms voor fetch plus tekenen in de pagina). De tik valt op de :00, :20 en :40 van de
// klok, zodat de kaart niet "37 seconden na de vorige tik" staat.
const KLOK_MS = 20000;
let klokTimer = null;
let klokAan = false;

function klokStand() {
  return !vies && actiefId === null && document.getElementById("naam").value.trim() === "Nu";
}

// Aspectlijnen als die aan staat, --accent-zwak). Zo zegt de balk zelf dat je naar het hier en nu
// kijkt en dat het tikt; de knop hoeft daarvoor niet te verhuizen en de naam hoeft niet te liegen.
function zetKlokKnop() {
  const b = document.querySelector(".werkbalk [data-doet=\"nu\"]");
  if (!b) { return; }
  b.classList.toggle("aan", klokAan);
  b.setAttribute("aria-pressed", klokAan ? "true" : "false");
}

function klokStop() {
  if (klokTimer !== null) { clearTimeout(klokTimer); klokTimer = null; }
  klokAan = false;
  zetKlokKnop();
}

function klokStart() {
  if (klokTimer !== null) { clearTimeout(klokTimer); klokTimer = null; }
  if (!klokStand()) { klokAan = false; zetKlokKnop(); return; }
  klokAan = true;
  zetKlokKnop();
  klokTimer = setTimeout(klokTik, KLOK_MS - (Date.now() % KLOK_MS) + 40);
}

async function klokTik() {
  // Alleen de wachtende timer weghalen, niet `klokStop()`: dat zou de knop tijdens het rekenen
  // even uit zetten, en dan knippert hij elke twintig seconden.
  if (klokTimer !== null) { clearTimeout(klokTimer); klokTimer = null; }
  if (!klokStand()) { klokAan = false; zetKlokKnop(); return; }
  try {
    const r = await fetch("/api/nu");
    const j = await r.json();
    if (!j || !j.nu || !klokStand()) {
      // De stand is tijdens het wachten weggevallen (er is getypt, of een kaart geopend): dan is dit
      // de laatste tik en moet de knop uit, anders blijft hij "aan" staan zonder dat er iets loopt.
      klokAan = false; zetKlokKnop(); return;
    }
    document.getElementById("datum").value = alsNederlands(j.nu.datum);
    document.getElementById("tijd").value = j.nu.tijd;
    await reken(true);            // stil: de meldregel blijft staan
  } catch (e) {
    // Een gemiste tik is geen fout - de volgende komt over twintig seconden. (De schil kan even
    // bezig zijn; er hoort geen rode melding in het scherm te komen van een klok die zichzelf
    // bijwerkt.)
  }
  klokStart();
}

let dlgGekozen = null;      // index in `kaarten` van de regel die open gaat
let dlgTerugNaar = null;    // waar de focus terug moet als het venster sluit

// --- het venster Horoscopen: zoeken, sorteren, verwijderen ---------------------------------------
// De zoekterm en de volgorde leven zolang het venster open is; bij elk bezoek begint het zoekveld
// leeg (je komt hier om iets te zoeken, niet om je vorige zoekopdracht terug te vinden). Sorteren
// keuzelijst en een knop.
let dlgZoek = "";
let dlgSorteer = "naam";       // "naam" of "datum"
let dlgRichting = "op";        // "op" = A→Z / oud→nieuw, "af" = Z→A / nieuw→oud

function dlgVolgorde() {
  const alle = kaarten.map((k, i) => ({ k, i }));
  const zoek = dlgZoek.trim().toLowerCase();
  const zichtbaar = zoek
    ? alle.filter(({ k }) => String(k.naam || "zonder naam").toLowerCase().includes(zoek))
    : alle.slice();
  const teken = (dlgRichting === "op") ? 1 : -1;
  zichtbaar.sort((a, b) => {
    let c;
    if (dlgSorteer === "datum") {
      c = String(a.k.datum || "").localeCompare(String(b.k.datum || "")) ||
          String(a.k.tijd || "").localeCompare(String(b.k.tijd || ""));
    } else {
      c = String(a.k.naam || "zonder naam").localeCompare(String(b.k.naam || "zonder naam"), "nl",
        { sensitivity: "base" });
    }
    return (c || (a.i - b.i)) * teken;   // gelijk: de index beslist, zodat er niets verspringt
  });
  return { zichtbaar, totaal: alle.length, zoek };
}

function dlgKop(kolom, tekst) {
  const aan = (dlgSorteer === kolom);
  // De actieve kolom draagt ▲ of ▼ in het accent; de andere sorteerbare kolom een lichte ↕, zodat
  // je ziet dat ook die kan sorteren. Tijd en Plaats gebruiken deze functie niet.
  const pijl = aan ? (dlgRichting === "op" ? "▲" : "▼") : "↕";
  const klasse = aan ? "pijl" : "pijl stil";
  return "<th class='kop'><button type='button' data-sorteer='" + kolom + "' " +
         "title='Sorteren op " + tekst.toLowerCase() + "'>" + tekst +
         "<span class='" + klasse + "'> " + pijl + "</span></button></th>";
}

function tekenOpenen() {
  const vak = document.getElementById("dlg-openen-lijst");
  const telling = document.getElementById("dlg-openen-telling");
  const knop = document.getElementById("dlg-openen-ok");
  const { zichtbaar, totaal, zoek } = dlgVolgorde();
  dlgGekozen = null;
  if (!totaal) {
    vak.innerHTML = "<p class='dlg-tekst' style='padding:12px'>Er zijn nog geen bewaarde horoscopen. " +
      "Bewaar er een met Ctrl+S; daarna staat hij hier.</p>";
    telling.textContent = "geen bewaarde horoscopen";
    knop.disabled = true;
    return;
  }
  knop.disabled = !zichtbaar.length;
  telling.textContent = zoek
    ? zichtbaar.length + " van " + totaal + " horoscopen"
    : totaal + (totaal === 1 ? " horoscoop" : " horoscopen");
  if (!zichtbaar.length) {
    vak.innerHTML = "<p class='dlg-tekst' style='padding:12px'>Geen horoscoop met '" + esc(zoek) +
      "' in de naam.</p>";
    return;
  }
  vak.innerHTML = "<table class='dlg-tabel'>" +
    "<colgroup><col style='width:32%'><col style='width:20%'><col style='width:17%'>" +
    "<col style='width:25%'><col style='width:6%'></colgroup>" +
    "<thead><tr>" + dlgKop("naam", "Naam") + dlgKop("datum", "Datum") +
    "<th class='gewone-kop'>Tijd</th><th class='gewone-kop'>Plaats</th><th></th></tr></thead><tbody>" +
    zichtbaar.map(({ k, i }) =>
      "<tr data-i='" + i + "' tabindex='-1'>" +
      "<td title=\"" + attr(k.naam || "zonder naam") + "\">" + esc(k.naam || "zonder naam") + "</td>" +
      "<td>" + esc(alsNederlands(k.datum)) + "</td>" +
      "<td>" + esc(String(k.tijd || "")) + "</td>" +
      "<td title=\"" + attr(k.plaats || "") + "\">" + esc(k.plaats || "") + "</td>" +
      "<td class='wegcel'><button type='button' class='weg' data-weg='" + i + "' " +
      "title='Deze horoscoop verwijderen' aria-label='Deze horoscoop verwijderen'>&times;</button></td>" +
      "</tr>").join("") + "</tbody></table>";
  const eerste = vak.querySelector("tbody tr");
  if (eerste) { kiesRij(eerste); }
}

async function openOpenen() {
  dlgTerugNaar = document.activeElement;
  dlgGekozen = null;
  dlgZoek = "";
  document.getElementById("dlg-openen-zoek").value = "";
  await laadKaarten();
  tekenOpenen();
  toonDialoog("dlg-openen");
  const eerste = document.querySelector("#dlg-openen-lijst tbody tr");
  (eerste || document.getElementById("dlg-openen-zoek")).focus();
}

function kiesRij(tr) {
  if (!tr) { return; }
  document.querySelectorAll("#dlg-openen-lijst tbody tr.gekozen")
    .forEach(x => x.classList.remove("gekozen"));
  tr.classList.add("gekozen");
  dlgGekozen = Number(tr.dataset.i);
}

// Eén sluitweg voor alle vensters: Escape, ✕, Annuleren, Sluiten en een klik naast het
// venster komen hier allemaal uit. Staat er een berichtvenster open, dan is sluiten "Nee".
function zichtbaarDialoog() {
  return [...document.querySelectorAll(".dialoogvlak")].find(v => !v.hidden) || null;
}

function toonDialoog(id) {
  const vlak = document.getElementById(id);
  if (!vlak || !vlak.hidden) { return; }
  dlgTerugNaar = document.activeElement;
  // Elk bezoek begint in het midden: een venster dat de vorige keer opzij is geschoven hoort niet
  // halverwege het scherm terug te komen.
  const dlg = vlak.querySelector(".dialoog");
  if (dlg) { dlg.style.transform = ""; }
  vlak.hidden = false;
}

// --- een venster verslepen ---------------------------------------------------------------------
//
// Alleen het venster **Horoscopen** is sleepbaar. Dat venster bedekt het wiel, en op een groot scherm
// wil je het opzij kunnen schuiven om de horoscoop erachter te bekijken; Instellingen blijft staan
// (klein, kort, en er is niets achter om te zien). Eén helper, zodat een derde venster later geen
// tweede mechanisme wordt.
//
// Drie regels: slepen alleen aan de titelbalk, het venster blijft binnen het scherm (anders sleep je
// het weg en ben je het kwijt), en dubbelklikken op de titelbalk zet het terug in het midden. De
// verplaatsing is een `transform`: de flex-centrering blijft de ruststand, dus er verspringt niets
// als het venster opnieuw opent.
function maakSleepbaar(vlak) {
  const dlg = vlak.querySelector(".dialoog");
  const titel = dlg && dlg.querySelector(".dlg-titel");
  if (!dlg || !titel) { return; }
  let sleep = null;

  const zet = (dx, dy) => {
    dlg.style.transform = (dx || dy) ? "translate(" + dx + "px, " + dy + "px)" : "";
  };
  const huidig = () => {
    const m = /translate\((-?[\d.]+)px,\s*(-?[\d.]+)px\)/.exec(dlg.style.transform || "");
    return m ? [Number(m[1]), Number(m[2])] : [0, 0];
  };

  titel.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 || e.target.closest(".dlg-sluit")) { return; }
    const r = dlg.getBoundingClientRect();
    const v = vlak.getBoundingClientRect();
    const [dx, dy] = huidig();
    sleep = {
      px: e.clientX, py: e.clientY, dx, dy,
      minX: v.left - (r.left - dx), maxX: v.right - (r.right - dx),
      minY: v.top - (r.top - dy), maxY: v.bottom - (r.bottom - dy)
    };
    titel.setPointerCapture(e.pointerId);
    e.preventDefault();
  });
  titel.addEventListener("pointermove", (e) => {
    if (!sleep) { return; }
    const dx = Math.min(sleep.maxX, Math.max(sleep.minX, sleep.dx + e.clientX - sleep.px));
    const dy = Math.min(sleep.maxY, Math.max(sleep.minY, sleep.dy + e.clientY - sleep.py));
    zet(Math.round(dx), Math.round(dy));
  });
  const stop = () => { sleep = null; };
  titel.addEventListener("pointerup", stop);
  titel.addEventListener("pointercancel", stop);
  titel.addEventListener("dblclick", () => { zet(0, 0); });
}

function sluitDialoog() {
  const vlak = zichtbaarDialoog();
  if (!vlak) { return; }
  vlak.hidden = true;
  if (vlak.id === "dlg-bericht" && berichtKlaar) {
    const k = berichtKlaar;
    berichtKlaar = null;
    k(false);
  }
  if (dlgTerugNaar && dlgTerugNaar.focus) { dlgTerugNaar.focus(); }
  dlgTerugNaar = null;
}

async function openGekozen() {
  if (dlgGekozen === null || dlgGekozen === undefined) { return; }
  const i = dlgGekozen;
  sluitDialoog();
  await openKaart(i);
}

// --- Het eigen berichtvenster --------------------------------------------------------------------

let berichtKlaar = null;

function bericht({ titel, tekst, ja, nee }) {
  document.getElementById("dlg-bericht-titel").textContent = titel || "Astrologie Studio";
  document.getElementById("dlg-bericht-tekst").textContent = tekst || "";
  document.getElementById("dlg-bericht-ja").textContent = ja || "Ja";
  const neeKnop = document.getElementById("dlg-bericht-nee");
  neeKnop.textContent = nee || "Nee";
  neeKnop.hidden = !nee;
  toonDialoog("dlg-bericht");
  document.getElementById("dlg-bericht-ja").focus();
  return new Promise(res => { berichtKlaar = res; });
}

function antwoordBericht(ja) {
  const vlak = document.getElementById("dlg-bericht");
  if (vlak.hidden) { return; }
  vlak.hidden = true;
  const k = berichtKlaar;
  berichtKlaar = null;
  if (k) { k(ja); }
  if (dlgTerugNaar && dlgTerugNaar.focus) { dlgTerugNaar.focus(); }
  dlgTerugNaar = null;
}

// --- Het venster meldt zich bij de schil ---------------------------------------------------------
// Het venster is van de browser, de schil is het programma: die twee horen samen te stoppen. Deze
// pagina meldt zich daarom bij het laden met een eigen id en meldt zich af als het venster dichtgaat;
// de schil stopt als er geen enkel venster meer over is (na een korte wachttijd, zodat een verversing
// het programma niet stopt). De andere richting - Bestand > Afsluiten - staat hieronder in `sluitAf`.
const VENSTER_ID = (window.crypto && crypto.randomUUID)
  ? crypto.randomUUID()
  : "v" + Date.now() + Math.random().toString(16).slice(2);
// `pagehide` én `beforeunload`: bij het sluiten van een app-venster komen ze allebei langs (gemeten
// in Chromium), en welke het eerst komt verschilt per browser. `sendBeacon` komt ook aan als de
// pagina al weg is; een dubbele melding is onschadelijk.
const meldWeg = () => navigator.sendBeacon("/api/afgesloten?id=" + encodeURIComponent(VENSTER_ID));
function meldVensterstaat(nieuwMeten) {
  if (nieuwMeten === false && laatsteStaat) {
    try {
      fetch("/api/vensterstaat", { method: "POST", keepalive: true,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(laatsteStaat) }).catch(() => {});
    } catch (e) { /* zie hieronder */ }
    return;
  }
  const buiten = [Math.round(outerWidth), Math.round(outerHeight)];
  const binnen = [Math.round(innerWidth), Math.round(innerHeight)];
  const scherm = [Math.round(screen.width), Math.round(screen.height)];
  const beschikbaar = [Math.round(screen.availWidth), Math.round(screen.availHeight)];
  const vultScherm = (buiten[0] >= scherm[0] - 2 && buiten[1] >= scherm[1] - 2)
    || (binnen[0] >= scherm[0] - 8 && binnen[1] >= scherm[1] - 8);
  const vultWerkblad = beschikbaar[0] > 0 && buiten[1] >= beschikbaar[1] - 2;
  // Een meting telt pas als rustmaat als het venster gewoon staat, groot genoeg is om een venster te
  // zijn, én de schil klaar is met de opgeslagen stand. Dat laatste is de drie-secondenregel: in de
  // eerste seconden van een start meet de pagina de maat waarop de *browser* opende, niet de maat van
  // het programma. Wordt die bewaard, dan wordt het venster bij elke start een factor 1,2 kleiner
  if (!vultScherm && !vultWerkblad && buiten[0] >= 400 && buiten[1] >= 300
      && Date.now() - paginaStart > 3000) {
    laatsteRust = buiten;
  }
  const staat = { buiten: buiten, binnen: binnen, scherm: scherm, beschikbaar: beschikbaar,
                  links: [Math.round(screenX), Math.round(screenY)] };
  if (laatsteRust) { staat.rust = laatsteRust; }
  laatsteStaat = staat;
  try {
    fetch("/api/vensterstaat", { method: "POST", keepalive: true,
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(staat) }).catch(() => {});
  } catch (e) { /* de maat onthouden is een gemak, geen eis: zonder melding opent hij standaard */ }
}
let vensterTik = null;

// --- Afsluiten ----------------------------------------------------------------------------------
//
// Het programma is een eigen server: stoppen kan alleen door die server te laten stoppen. Daarom
// vraagt deze knop eerst toestemming (wat niet bewaard is, gaat verloren) en daarna zegt de pagina
// wat er gebeurd is. In de versie zonder consolevenster is dit de enige nette manier om te stoppen.
async function sluitAf() {
  const ja = await bericht({
    titel: "Afsluiten",
    tekst: "Weet je zeker dat je Astrologie Studio wilt afsluiten? Een horoscoop die je niet " +
           "bewaard hebt, gaat verloren.",
    ja: "Afsluiten", nee: "Annuleren"
  });
  if (!ja) { return; }
  try {
    const ant = await fetch("/api/afsluiten", { method: "POST" });
    const j = await ant.json().catch(() => ({}));
    if (!ant.ok) { throw new Error(j.fout || ("de server antwoordde " + ant.status)); }
  } catch (e) {
    await bericht({ titel: "Afsluiten", tekst: "Het programma wilde niet stoppen: " + e.message,
                    ja: "Sluiten", nee: "" });
    return;
  }
  // De schil stopt; dit venster hoort mee te stoppen. In een app-venster mag dat: `window.close()`
  // sluit een `--app`-venster (gemeten in Chromium). In een gewoon tabblad weigert de
  // browser, en dan blijft dit scherm staan als afsluiting.
  window.close();
  // De kop zegt het al; het antwoord van de server herhalen zou dubbelop lezen.
  const vlak = document.createElement("div");
  vlak.className = "afgesloten";
  vlak.innerHTML = "<div><h1>Astrologie Studio is afgesloten</h1>" +
    "<p>Je kunt dit venster sluiten.</p>" +
    "<p class='klein'>Je bewaarde horoscopen staan in de map die je bij Instellingen ziet.</p></div>";
  document.body.replaceChildren(vlak);
}

// --- Instellingen en Over als venster ------------------------------------------------------------

async function openInstellingen() {
  await laadInstellingen();          // de velden uit het bestand; laadInstellingen opent dit venster
  zetCursusVinkjes();                // de aangevinkte cursusjaren horen bij dit venster (T48)
  toonDialoog("dlg-instellingen");   // zelf ook openen als de instellingen gewoon gelezen zijn
  const eerste = document.getElementById("inst-plaats");
  if (eerste) { eerste.focus(); }
}

function openOver() {
  // Het versienummer komt van de schil (kern/versie.py), niet uit deze pagina: één waarheid.
  const cel = document.getElementById("over-versie");
  if (cel && !cel.textContent) {
    fetch("/api/leeft").then(a => a.json()).then(j => {
      if (j && j.versie) { cel.textContent = "Versie " + j.versie; }
    }).catch(() => {});
  }
  toonDialoog("dlg-over");
  const sluit = document.querySelector("#dlg-over [data-sluit]");
  if (sluit) { sluit.focus(); }
}

// --- De weergavegrootte --------------------------------------------------------------------------
//
// Eén knop in Beeld, vier standen. Het is een scherminstelling en geen eigenschap van de kaart of de
// locatie: hij staat daarom naast de sorteerkeuze in localStorage en niet in het instellingenbestand
// (dat bestand gaat over de locatie en wordt door `kern.instellingen.bewaar()` in zijn geheel
// herschreven — een schermstand daarin zou bij elke opslag weer weg zijn).
//
// `zoom` op de html schaalt de hele indeling mee, inclusief het wiel; alleen de letters vergroten zou
// de vaste maten breken. In de afdruk staat zoom weer op 1 (zie de printmedia).

const WEERGAVE = [100, 110, 125, 150];
let weergave = 100;

function zetWeergaveVinkjes() {
  document.querySelectorAll("[data-vink-weergave]").forEach(v => {
    v.style.visibility = Number(v.dataset.vinkWeergave) === weergave ? "visible" : "hidden";
  });
}

// De twee knoppen in de hoek van de statusbalk. Ze roepen dezelfde `zetWeergave()` aan
// als het Beeld-menu, zodat er één waarheid is over de stand — en de knop die niets meer kan wordt
// uitgegrijsd in plaats van dood te klikken.
function weergaveStap(stap) {
  const i = WEERGAVE.indexOf(weergave);
  if (i < 0) { return; }
  const nieuw = WEERGAVE[Math.min(WEERGAVE.length - 1, Math.max(0, i + stap))];
  if (nieuw !== weergave) { zetWeergave(nieuw); }
}

function zetWeergaveKnoppen() {
  const waarde = document.getElementById("wg-waarde");
  const min = document.getElementById("wg-min");
  const plus = document.getElementById("wg-plus");
  if (!waarde || !min || !plus) { return; }
  const i = WEERGAVE.indexOf(weergave);
  waarde.textContent = weergave + "%";
  min.disabled = i <= 0;
  plus.disabled = i >= WEERGAVE.length - 1;
}

function zetWeergave(pct) {
  pct = Number(pct);
  if (!WEERGAVE.includes(pct)) { pct = 100; }
  weergave = pct;
  document.documentElement.style.zoom = (pct === 100) ? "" : String(pct / 100);
  document.documentElement.dataset.weergave = String(pct);
  try { localStorage.setItem("astrologie-studio.weergave", String(pct)); } catch (e) { /* privémodus */ }
  zetWeergaveVinkjes();
  zetWeergaveKnoppen();
  // Het A4-voorbeeld is met de oude maat uitgerekend: opnieuw schalen als het in beeld staat.
  const tab = document.querySelectorAll(".tab.actief")[0];
  if (tab && tab.id === "tab-afdruk") { schaalAfdruk(); }
}

const dlgOpenen = document.getElementById("dlg-openen");

const toonAspectenVak = document.getElementById("toon-aspecten");
// Chiron aan of uit is een nieuwe berekening: de puntenlijst verandert immers. Stil, want de
// meldregel hoeft niet bij elke wissel "berekend" te zeggen.
const toonChironVak = document.getElementById("toon-chiron");
