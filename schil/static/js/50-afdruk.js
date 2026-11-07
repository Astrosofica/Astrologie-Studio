// 50-afdruk.js
//
// Het A4-blad, de bi-afdruk en de twee lijsten op papier.
// Alle bestanden delen één werkruimte en worden in deze volgorde geladen; 90-start.js
// komt achteraan en gebruikt wat hierboven staat.


// --- De naam die "Opslaan als PDF" voorstelt -----------------------------------
//
// Edge - het venster waarin het programma draait - vult het naamveld van "Opslaan als PDF" met de
// **venstertitel** van de pagina. Daarom zetten we hem vlak voor het printen om in
// de naam van het vel - wie, wat, wanneer - en daarna terug: het kenmerk van het venster zit in die
// titel en de schil zoekt het venster erop terug, dus hij moet precies terugkomen zoals hij was.
//
// Terugzetten gebeurt op `afterprint`, niet meteen na `window.print()`.
// Blijft `afterprint` uit, dan zet een tijdbewaking hem na twee minuten alsnog terug.
//
// Wat dit niet doet: het stuurprogramma van "Microsoft Print to PDF" vraagt zijn eigen bestandsnaam en
// neemt die niet van de pagina over.
function drukBestandsnaam(tekst) {
  // Wat Windows in een bestandsnaam weigert (en stuurtekens) wordt een spatie; daarna geen dubbele
  // spaties, geen punten of spaties aan de randen, en niet langer dan 120 tekens.
  return String(tekst || "")
    .replace(/[\\/:*?"<>|\u0000-\u001f]/g, " ")
    .replace(/\s+/g, " ")
    .replace(/^[\s.]+/, "")
    .slice(0, 120)
    .replace(/[\s.]+$/, "");
}

// Wie - wat wanneer. Eén streepje tussen persoon en vel, zodat alles van één persoon bij elkaar
// sorteert. Zonder naam valt hij terug op "zonder naam", precies zoals op papier.
function drukTitel(soort, periode) {
  const meta = (laatste && laatste.kaart && laatste.kaart.meta) || {};
  const wie = String(meta.naam || "").trim() || "zonder naam";
  const rest = String(periode || "").trim();
  return drukBestandsnaam(wie + " - " + [soort, rest].filter(deel => deel).join(" "));
}

// De twee veldjes van een tijdvak staan als DD-MM-JJJJ op het scherm. In een bestandsnaam zetten we
// jjjj-mm-dd: dat sorteert in Verkenner, en het is de vorm die de kaart zelf ook gebruikt.
function drukDatumIso(waarde) {
  const m = /^(\d{1,2})-(\d{1,2})-(\d{4})$/.exec(String(waarde || "").trim());
  return m ? m[3] + "-" + ("0" + m[2]).slice(-2) + "-" + ("0" + m[1]).slice(-2)
           : String(waarde || "").trim();
}

function drukPeriode(vanId, totId) {
  const lees = (id) => {
    const vak = document.getElementById(id);
    return vak ? drukDatumIso(vak.value) : "";
  };
  const van = lees(vanId), tot = lees(totId);
  // "tot" en niet "t/m": de schuine streep mag niet in een bestandsnaam (Windows leest hem als
  // scheiding tussen mappen), en dan zou er "2026-01-01 t m 2026-12-31" staan.
  return (van && tot) ? van + " tot " + tot : (van || tot);
}

// De titel omzetten, printen, en hem daarna terugzetten. Eén plek voor alle drie de afdrukken, zodat
// geen enkele route de titel kan vergeten (en er ook geen tweede regel kan ontstaan).
function drukAf(naam, werk) {
  const oud = document.title;
  const nieuw = drukBestandsnaam(naam);
  if (!nieuw || nieuw === oud) { werk(); return; }
  let klaar = false;
  const terug = () => { if (klaar) { return; } klaar = true; document.title = oud; };
  window.addEventListener("afterprint", terug, { once: true });
  setTimeout(terug, 120000);
  document.title = nieuw;
  try {
    werk();
  } catch (e) {
    terug();
    throw e;
  }
}

// De knop "Afdrukken…" (en de regel in het menu): het A4-blad. De naam volgt wat er op dat vel staat -
// de radix, of de bi-stand die in de keuzelijst bij de afdruk staat.
function drukA4Af() {
  const meta = (laatste && laatste.kaart && laatste.kaart.meta) || {};
  let soort = "horoscoop", periode = String(meta.datum || "");
  if (drukBi === "transits") {
    soort = "transits";
    const moment = (drukBeeld && drukBeeld.moment) || (typeof wmIso === "function" ? wmIso() : "");
    periode = String(moment || "").slice(0, 10);
  } else if (drukBi === "progressies") {
    soort = "progressies";
    periode = String((drukBeeld && drukBeeld.datum) || "");
  }
  drukAf(drukTitel(soort, periode), () => window.print());
}

// De transitlijst afdrukken. Een eigen route naast het A4-blad: `Bestand > Afdrukken`
// print het wiel en moet dat blijven doen. Wat hier op papier komt is de lijst zoals hij op dat moment
// op het scherm staat - hetzelfde tijdvak, dezelfde planeten, aspecten en radixpunten, dezelfde
// indeling. De klasse `druk-lijst` op de body zet de printregels om; hij gaat er in een `finally` weer
// af, ook als de gebruiker de afdruk afbreekt, zodat het scherm nooit in de afdrukstand blijft hangen.
function drukLijstAf() {
  const tabel = document.querySelector("#tr-scroll table.lijst");
  const heeftRijen = !!(tabel && tabel.querySelector("tbody tr"));
  zetTab("transits");
  if (!heeftRijen) {
    const vak = document.getElementById("tr-lijstvak");
    if (vak) {
      vak.innerHTML = "<h2>Exacte transits <span class='tr-bij'>nog niets om af te drukken</span></h2>" +
        "<p class='leegvlak'>Bereken eerst de lijst. Wat er dan staat, is wat er op papier komt.</p>";
    }
    return;
  }
  document.body.classList.add("druk-lijst");
  try {
    // De naam van het vel gaat mee.
    drukAf(drukTitel("transitlijst", drukPeriode("tr-van", "tr-tot")), () => window.print());
  } finally {
    document.body.classList.remove("druk-lijst");
  }
}

// De kop van het afgedrukte vel: wie, wanneer geboren, waar, welk stelsel - en daaronder het tijdvak,
// de selectie en de afdrukdatum. Zonder die twee regels is een los vel in een map niet te plaatsen.
function trDrukKop() {
  const meta = (laatste && laatste.kaart && laatste.kaart.meta) || {};
  const geboren = [alsNederlands(meta.datum || ""), (meta.tijd || "").slice(0, 5)]
    .filter(deel => deel && deel.trim()).join(" ");
  // Geen huizenstelsel: het programma rekent altijd met Koch en een
  // gegeven dat nooit anders is hoort niet in de kop van een vel.
  const regel1 = [meta.naam || "zonder naam", geboren, meta.plaats || ""]
    .filter(deel => deel && String(deel).trim()).join(" · ");
  // Geen "afgedrukt op": de printer of Windows zet zelf datum en tijd in de kop.
  // Wat je later wél wilt terugvinden is **welk tijdvak** er op dit vel staat - vandaar het tijdvak
  // vooraan, in lange vorm, met de selectie erachter.
  return "<span class='dk-naam'>" + esc(regel1) + "</span>" +
         "<span class='dk-rest'>" + esc(trInvoerTekst(true)) + "</span>";
}

// De afdruk van de progressielijst. Dezelfde route als `drukLijstAf()` bij de transits:
// één klasse op de body, printen, en de klasse er in een `finally` weer af. Wat er op papier komt is
// precies de lijst zoals hij op het scherm staat - zelfde tijdvak, zelfde lichamen, zelfde aspecten,
// zelfde indeling.
function prDrukLijstAf() {
  const tabel = document.querySelector("#pr-scroll table.lijst");
  const heeftRijen = !!(tabel && tabel.querySelector("tbody tr"));
  // Eerst naar deze tab: het afdrukvel toont alleen de **actieve** lijsttab (zie de CSS), en zonder
  // deze regel bleef het vel leeg als je de progressielijst vanaf een andere tab afdrukte
  // `drukLijstAf()` doet hetzelfde met de transits.
  zetTab("progressies");
  prStand("lijsten");
  if (!heeftRijen) {
    const vak = document.getElementById("pr-lijstvak");
    if (vak) {
      vak.innerHTML = "<h2>Exacte progressies <span class='tr-bij'>nog niets om af te drukken</span></h2>" +
        "<p class='leegvlak'>Bereken eerst de lijst. Wat er dan staat, is wat er op papier komt.</p>";
    }
    return;
  }
  // Een afgekapte lijst is geen lijst: dan mist er een tijdvak en zie je dat op papier niet meer.
  if (prUit && prUit.afgekapt) {
    zetMeld("let-op", ["De lijst is afgekapt op " + trGetal(prUit.grens) + " van " + trGetal(prUit.totaal) +
      " regels. Kies een korter tijdvak en druk dat af."]);
    return;
  }
  document.body.classList.add("druk-lijst");
  try {
    drukAf(drukTitel("progressielijst", drukPeriode("pr-van", "pr-tot")), () => window.print());
  } finally {
    document.body.classList.remove("druk-lijst");
  }
}

// De kop van het vel: wie, wanneer geboren, waar - en daaronder het tijdvak **in leeftijden** met de
// datums erbij, want dat is wat deze lijst anders maakt dan een transitlijst.
function prDrukKop() {
  const meta = (laatste && laatste.kaart && laatste.kaart.meta) || {};
  const geboren = [alsNederlands(meta.datum || ""), (meta.tijd || "").slice(0, 5)]
    .filter(deel => deel && deel.trim()).join(" ");
  const regel1 = [meta.naam || "zonder naam", geboren, meta.plaats || ""]
    .filter(deel => deel && String(deel).trim()).join(" \u00b7 ");
  const van = document.getElementById("pr-van"), tot = document.getElementById("pr-tot");
  const datums = (van && tot && van.value && tot.value) ? van.value + " tot " + tot.value : "";
  const uit = prUit || {};
  const leeftijden = (uit.van_leeftijd !== undefined && uit.tot_leeftijd !== undefined)
    ? "leeftijd " + prLeeftijd(uit.van_leeftijd) + " tot " + prLeeftijd(uit.tot_leeftijd) + " jaar"
    : "";
  const rest = [leeftijden, datums, prSelectieTekst()].filter(deel => deel).join(" \u00b7 ");
  return "<span class='dk-naam'>" + esc(regel1) + "</span>" +
         "<span class='dk-rest'>" + esc(rest) + "</span>";
}

// Het A4-blad als preview passend maken in het venster.
const A4_W = 210 / 25.4 * 96, A4_H = 297 / 25.4 * 96;
function schaalAfdruk() {
  const tab = document.getElementById("tab-afdruk");
  const vak = document.getElementById("afdruk");
  if (!tab || !vak || !tab.classList.contains("actief") || !vak.querySelector(".a4")) return;
  const stijl = getComputedStyle(tab);
  // De zoom **meten**, niet aannemen: zo volgt deze deling vanzelf als er een stand bij komt of de
  // schil hem anders zet. Zonder `zoom` geeft de browser 1.
  const zw = parseFloat(getComputedStyle(document.documentElement).zoom) || 1;
  const veld = vak.getBoundingClientRect();
  const onder = tab.getBoundingClientRect().bottom - veld.top - (parseFloat(stijl.paddingBottom) || 0);
  const breed = veld.width - 2 * (parseFloat(stijl.paddingLeft) || 0);
  // De bovengrens is 1: een voorbeeld hoort nooit groter te lijken dan het papier zelf;
  // de ondergrens is alleen een vangnet tegen nul, geen leesbaarheidsgrens.
  const zet = z => {
    tab.style.setProperty("--a4-zoom", Math.max(0.05, Math.min(1, z)).toFixed(3));
    void document.body.offsetHeight;   // reflow
  };
  zet(Math.min(onder / (A4_H * zw), breed / (A4_W * zw)));
  for (let i = 0; i < 2; i++) {
    const over = tab.scrollHeight - tab.clientHeight;
    if (over <= 0) return;
    const nu = parseFloat(tab.style.getPropertyValue("--a4-zoom")) || 0.5;
    zet(nu - (over + 1) / A4_H);
  }
}

// De aspecttabel op papier als **trap**.
function trapHTML(k) {
  const p = k.punten || [];
  if (!p.length) return "";
  const weg = wegPunt(k);
  const idx = p.map((x, i) => i).filter((i) => !weg.has(p[i].naam));
  const stuk = (c) => c ? "<span class='g'>" + c.glyf + "</span><span class='o'>" +
      orbDelen(c.orb).deg + "<span class='scheidend'>" + c.letter + "</span>" +
      orbDelen(c.orb).min + "</span>" : "";
  let t = "<table class='trap'><tr><td class='diag'>" + (GLYF[p[idx[0]].naam] || "?") + "</td></tr>";
  for (let a = 1; a < idx.length; a++) {
    t += "<tr>";
    for (let b = 0; b < a; b++) {
      const cel = ((k.matrix[idx[b]] || [])[idx[a]] || []);
      t += "<td class='cel'>" + (cel.length ? cel.map(stuk).join("<br>") : "") + "</td>";
    }
    t += "<td class='diag'>" + (GLYF[p[idx[a]].naam] || "?") + "</td></tr>";
  }
  return t + "</table>";
}

// De kop van het vel.
function a4KopHTML(g) {
  const regel = (s) => "<div>" + esc(s) + "</div>";
  const KNOOP_NL = { "True Node": "Ware knoop", "Mean Node": "Gemiddelde knoop" };
  return "<div class='a4-pers'>" +
      regel(g.naam) +
      regel(alsNederlands(g.datum)) +
      regel(g.tijd + " " + g.offset_label) +
      regel(g.plaats) +
      regel(dms(g.lat, "lat") + " " + dms(g.lon, "lon")) +
    "</div>" +
    "<div class='a4-tech'>" +
      regel(g.centrum) + regel(g.zodiactype) + regel(g.huizenstelsel_naam) +
      regel(KNOOP_NL[g.knoop] || g.knoop) +
      (g.efemeride && g.efemeride !== "Swiss Ephemeris" ? regel("Standen: " + g.efemeride) : "") +
    "</div>";
}

function afdrukHTML(j) {
  const k = j.kaart, svg = j.svg;
  return "<div class='a4'>" + a4KopHTML(k.meta) +
    "<div class='wiel geen-aspecten geen-tint a4-wiel'>" + svg + "</div>" +
    "<div class='a4-trap'>" + trapHTML(k) + "</div>" +
    "<div class='a4-toev'>" + toevoegingenHTML(j, true) + "</div>" +
    "</div>";
}

// --- Het vel van de bi-stand -------------------------------------------------------
function afdrukBiHTML(k, momentTekst, standen, svg, soort) {
  const progressief = soort === "progressies";
  const rijen = standen.map(x => {
    const t = x.positie || {};
    return "<tr><td>" + glyfVan(x.naam) + "</td><td>" + esc(x.naam) +
      (x.retrograde ? " <span class='retro'>\u211e</span>" : "") + "</td>" +
      "<td class='pos'>" + standTekst(x.lengte, t.glyf) + "</td>" +
      "<td class='huis'>huis " + esc(String(x.huis || "-")) + "</td></tr>";
  });
  const per = Math.ceil(rijen.length / 2);
  const kolommen = [rijen.slice(0, per), rijen.slice(per)]
    .filter(stuk => stuk.length)
    .map(stuk => "<table>" + stuk.join("") + "</table>").join("");
  return "<div class='a4'>" + a4KopHTML(k.meta) +
    "<div class='wiel geen-aspecten geen-tint a4-wiel groot'>" + svg + "</div>" +
    "<div class='a4-moment'><span class='wat'>stand van de " +
      (progressief ? "progressies" : "transits") + "</span> · " + esc(momentTekst) + "</div>" +
    "<div class='a4-transits'>" + kolommen + "</div>" +
    "<div class='a4-hint'>De planeten buiten de ring zijn de standen van de " +
      (progressief ? "progressies" : "transits") + "; de binnencirkel is de geboortehoroscoop.</div>" +
    "</div>";
}

function drukMomentTekst(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(String(iso || ""));
  if (!m) { return ""; }
  const datum = m[3] + "-" + m[2] + "-" + m[1];
  const ut = datum + " · " + m[4] + ":" + m[5] + " UT";
  const meta = (laatste && laatste.kaart && laatste.kaart.meta) ? laatste.kaart.meta : {};
  if (!meta.tijdzone_id) { return ut; }
  try {
    const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]));
    const delen = d.toLocaleString("nl-NL", { timeZone: meta.tijdzone_id, day: "2-digit",
      month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
      timeZoneName: "short" });
    const lokaalDatum = (delen.match(/\d{2}-\d{2}-\d{4}/) || [""])[0];
    const lokaalTijd = (delen.match(/\d{2}:\d{2}/) || [""])[0];
    const zone = (delen.split(/\s+/).pop() || "").replace(/[^A-Za-z]/g, "");
    const wijkt = lokaalDatum && lokaalDatum !== datum;
    return ut + " · " + (wijkt ? lokaalDatum + " " : "") + lokaalTijd + (zone ? " " + zone : "");
  } catch (e) { return ut; }
}

// --- Wat er op papier komt: de radix of de bi-stand --------------------------------
let drukBi = "";
let drukBeeld = null;
let drukBeurt = 0;

function zetDrukSchakel() {
  const keuze = document.getElementById("druk-schakel");
  if (!keuze) { return; }
  if (!keuze.options.length) {
    [["radix", "radix"], ["transits", "met transits"], ["progressies", "met progressies"]]
      .forEach(([waarde, tekst]) => {
        const o = document.createElement("option");
        o.value = waarde;
        o.textContent = tekst;
        keuze.appendChild(o);
      });
    keuze.addEventListener("change", (ev) => {
      drukBi = ev.target.value === "radix" ? "" : ev.target.value;
      zetAfdruk(laatste);
    });
  }
  const kanTransits = !!(laatste && laatste.kaart && laatste.svg) && trMag();
  const kanProgressies = !!(laatste && laatste.kaart && laatste.svg) && prMag();
  Array.from(keuze.options).forEach((o) => {
    o.disabled = (o.value === "transits" && !kanTransits) ||
                 (o.value === "progressies" && !kanProgressies);
  });
  if ((drukBi === "transits" && !kanTransits) || (drukBi === "progressies" && !kanProgressies)) {
    drukBi = "";
  }
  keuze.hidden = !(kanTransits || kanProgressies);
  keuze.value = drukBi || "radix";
  keuze.classList.toggle("aan", !!drukBi);
  keuze.title = !drukBi
    ? "Kies wat er op papier komt: de radix, of de radix met de transits of de progressies"
    : (drukBi === "progressies"
      ? "De afdruk toont de radix met de progressies eromheen, met hun standen en de leeftijd"
      : "De afdruk toont de radix met de transits eromheen, met hun standen");
}

async function drukBiBeeld() {
  if (!laatste || !laatste.kaart) { return null; }
  if (drukBi === "progressies") {
    const sleutel = "progressies|" + (wlGekozen ? wlWaarde() : "nu");
    if (drukBeeld && drukBeeld.sleutel === sleutel) { return drukBeeld; }
    const vracht = { kaart: laatste.kaart, met_standen: true, krap: true };
    if (wlGekozen) { vracht.leeftijd = wlWaarde(); }
    try {
      const r = await fetch("/api/progressies/nu", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(vracht) });
      if (!r.ok) { return null; }
      const j = await r.json();
      if (!j.svg) { return null; }
      drukBeeld = { sleutel: sleutel, leeftijd: j.leeftijd, datum: j.datum, svg: j.svg,
                    standen: j.standen || [] };
      return drukBeeld;
    } catch (e) { return null; }
  }
  if (!wielMoment) { wmNu(); }
  const moment = wmIso();
  if (!moment) { return null; }
  if (drukBeeld && drukBeeld.sleutel === "transits|" + moment) { return drukBeeld; }
  try {
    const r = await fetch("/api/transits/nu", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kaart: laatste.kaart, moment: moment, met_standen: true,
                             krap: true }) });
    if (!r.ok) { return null; }
    const j = await r.json();
    if (!j.svg) { return null; }
    drukBeeld = { sleutel: "transits|" + moment, moment: moment, svg: j.svg,
                  standen: j.standen || [] };
    return drukBeeld;
  } catch (e) { return null; }
}

function drukLeeftijdTekst(leeftijd, datum) {
  if (leeftijd === null || leeftijd === undefined) { return alsNederlands(datum || ""); }
  const getal = Number(leeftijd).toLocaleString("nl-NL", { minimumFractionDigits: 1,
    maximumFractionDigits: 1 });
  return getal + " jaar" + (datum ? " \u00b7 " + alsNederlands(datum) : "");
}

async function zetAfdruk(j) {
  const vak = document.getElementById("afdruk");
  if (!vak || !j || !j.kaart) { return; }
  const magBi = drukBi === "progressies" ? prMag() : (drukBi === "transits" ? trMag() : false);
  if (!magBi) {
    vak.innerHTML = afdrukHTML(j);
    zetDrukSchakel();
    schaalAfdruk();
    return;
  }
  const beurt = ++drukBeurt;
  const beeld = await drukBiBeeld();
  zetDrukSchakel();
  if (beurt !== drukBeurt) { return; }        // een nieuwer verzoek is al onderweg
  if (!beeld) { vak.innerHTML = afdrukHTML(j); schaalAfdruk(); return; }
  if (drukBi === "progressies") {
    const lichamen = (beeld.standen || []).filter(x => x.naam !== "Ascendant" && x.naam !== "MC");
    vak.innerHTML = afdrukBiHTML(j.kaart, drukLeeftijdTekst(beeld.leeftijd, beeld.datum), lichamen,
                                 beeld.svg, "progressies");
    schaalAfdruk();
    return;
  }
  vak.innerHTML = afdrukBiHTML(j.kaart, drukMomentTekst(beeld.moment), beeld.standen, beeld.svg,
                               "transits");
  schaalAfdruk();
}

function standenDMS(lengte) {
  const in_teken = ((lengte % 30) + 30) % 30;
  const g = Math.floor(in_teken);
  const m = Math.floor((in_teken - g) * 60);
  const s = Math.floor(((in_teken - g) * 60 - m) * 60);
  return { g: g, m: m, s: s };
}

function standTekst(lengte, glyf) {
  const d = standenDMS(lengte);
  return String(d.g).padStart(2, "0") + "° " + (glyf || "") + " " +
    String(d.m).padStart(2, "0") + "' " + String(d.s).padStart(2, "0") + "\"";
}

function standenHTML(k, nkol) {
  const p = k.punten || [];
  if (!p.length) return "";
  const NAAM = { "MC": "Midhemel" };
  const rijen = p.map(x => {
    const t = x.positie || {};
    return "<tr><td>" + glyfVan(x.naam) + "</td><td>" + esc(NAAM[x.naam] || x.naam) +
      (x.retrograde ? " <span class='retro'>℞</span>" : "") + "</td>" +
      "<td class='n pos'>" + standTekst(x.lengte, t.glyf) + "</td>" +
      "<td class='n'>huis " + (x.huis || "-") + "</td></tr>";
  });
  nkol = nkol || 3;
  const per = Math.ceil(rijen.length / nkol);
  let h = "<h2>Planeetstanden</h2><div class='kolommen'>";
  for (let i = 0; i < nkol; i++) {
    const stuk = rijen.slice(i * per, (i + 1) * per);
    if (!stuk.length) break;
    h += "<div><table>" + stuk.join("") + "</table></div>";
  }
  return h + "</div>";
}
