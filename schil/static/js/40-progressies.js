// 40-progressies.js
//
// De progressies: de lijst, de prenatale stand en de maanfasen.
// Alle bestanden delen één werkruimte en worden in deze volgorde geladen; 90-start.js
// komt achteraan en gebruikt wat hierboven staat.


// Het jaarprofiel. De schil leest `technieken/<profiel>.json` en geeft het hier door;
// de pagina gebruikt het voor het cursusjaar in de kop en voor de technieken die aanstaan. Wat er
// niet in staat, bestaat ook niet in het scherm: jaar 1 kan dus geen jaar-2-knop tonen.
let profiel = { jaar: 1, naam: "", technieken: new Set() };


// --- Progressies --------------------------------------------------------------
// De kloon van de transits. Twee standen, net als daar: de momentopname (de progressieve kaart van
// vandaag, met de leeftijd) en de lijst met de momenten van exactheid.
//
// Wat anders is dan bij de transits, en waarom:
//   - de tijdas is de **leeftijd**; de datums zijn de vindplaats. Elke regel draagt allebei;
//   - de Ascendant en MC staan als bewegend lichaam in de lijst;
//   - er is een vierde soort regel bij: de teken-ingress.
const PR_ASPECT_UIT = [60, 120];
// Korte namen in de lijst: het glyph staat al in de kolom, en "Ascendant" duwt de kolom Stand in.
const PR_KORT = { "Ascendant": "Asc", "MC": "Midhemel", "Noordknoop": "Knoop" };
const prNaam = n => PR_KORT[n] || n;
// De lijstindeling van de progressielijst. `per dag` ontbreekt met opzet.
const PR_INDELING = [["geen", "geen"], ["maand", "per maand"], ["jaar", "per jaar"],
                     ["decennium", "per decennium"]];
let prScheiding = "jaar";
// De snelknoppen voor het tijdvak.
const PR_PERIODE_STANDAARD = 5;
let prPeriodeStand = PR_PERIODE_STANDAARD;
const PR_TERUG = [10, 20, 30, 50];
let prPrenJaren = 30;
let prPrenUit = null;
let prPrenBezig = false;
let prMaanAantal = 8;
let prMaanUit = null;
let prMaanBezig = false;
let prStart = "jaar";
function prBeginJanuari() { return prStart === "jaar"; }
let prGebouwd = false;
let prBezig = false;
let prUit = null;

// Mag deze gebruiker de progressiestand van het wiel?
function prMag() {
  return !!(laatste && laatste.kaart) && !klokStand() && techniekAan("progressies");
}

function zetProgressiesKnop() {
  const knop = document.querySelector(".tabs button[data-tab='progressies']");
  if (!knop) { return; }
  const mag = prMag();
  knop.classList.toggle("uit", !mag);
  knop.disabled = !mag;
  knop.title = mag ? "" : "De progressies horen bij een berekende horoscoop";
}

function zetProgressies(aan) {
  const balk = document.querySelector(".tabs");
  let knop = balk ? balk.querySelector("button[data-tab='progressies']") : null;
  if (aan && balk && !knop) {
    knop = document.createElement("button");
    knop.dataset.tab = "progressies";
    knop.textContent = "Progressies";
    balk.appendChild(knop);
    knop.addEventListener("click", () => zetTab("progressies"));
    const broer = document.getElementById("tab-transits") || document.getElementById("tab-aspecten");
    if (broer && broer.parentNode && !document.getElementById("tab-progressies")) {
      const vak = document.createElement("div");
      vak.className = "tab";
      vak.id = "tab-progressies";
      broer.parentNode.insertBefore(vak, broer.nextSibling);
    }
  } else if (!aan && knop) {
    const vak = document.getElementById("tab-progressies");
    if (vak && vak.classList.contains("actief")) { zetTab("wiel"); }
    if (vak) { vak.remove(); }
    knop.remove();
    zetAfdrukAchteraan();
    return;
  }
  if (aan) { bouwProgressies(); zetProgressiesKnop(); }
  zetAfdrukAchteraan();
}

function prWaarden(soort) {
  return Array.from(document.querySelectorAll("[data-pr-" + soort + "]"))
    .filter(x => x.checked).map(x => x.getAttribute("data-pr-" + soort));
}

function prLeeftijd(waarde) {
  const afgerond = Math.round(waarde * 10) / 10;
  return (Object.is(afgerond, -0) ? 0 : afgerond)
    .toLocaleString("nl-NL", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function prPeriode(aantal) {
  if (!document.getElementById("pr-van")) { return; }
  periodeVul("pr-van", "pr-tot", aantal, prBeginJanuari());
  prPeriodeStand = Number(aantal);
  prPeriodeToon();
}

function prPeriodeToon() {
  periodeKnoppenToon("pr", prPeriodeStand);
  periodeStartToon("pr", prStart);
}

function bouwProgressies() {
  const vak = document.getElementById("tab-progressies");
  if (!vak || prGebouwd || !trVorm) { return; }
  prGebouwd = true;
  const L = trVorm.lichamen || [], A = trVorm.aspecten || [], H = trVorm.hoeken || [];

  const vakje = (soort, waarde, glyf, aan, titel) =>
    "<label class='tr-vak' title='" + esc(titel) + "'><input type='checkbox' data-pr-" + soort +
    "='" + esc(waarde) + "'" + (aan ? " checked" : "") + "><span class='glyf" +
    (String(glyf).length > 1 ? " letters" : "") + "'>" + glyf + "</span></label>";
  const rij = (titel, soort, vakjes) =>
    "<tr><th>" + titel + "</th><td><div class='tr-rij2'>" +
      "<div class='tr-schakels'>" +
        "<button type='button' class='tr-schakel' data-pr-alle='" + soort + "'>alles aan</button>" +
        "<button type='button' class='tr-schakel' data-pr-geen='" + soort + "'>alles uit</button>" +
      "</div><div class='tr-vakken'>" + vakjes + "</div></div></td></tr>";

  vak.innerHTML =
    "<div class='tr-sub'>" +
      "<button type='button' data-pr-stand='nu' class='aan'>Huidige progressie</button>" +
      "<button type='button' data-pr-stand='lijsten'>Progressielijsten</button>" +
      "<button type='button' data-pr-stand='maanfasen'>Maanfasen</button>" +
      "<button type='button' data-pr-stand='prenataal'>Prenataal</button>" +
      "<div class='tr-subvul'></div>" +
    "</div>" +
    "<div class='tr-stand' id='pr-stand-nu'>" +
      "<div class='paneel tr-nu' id='pr-nuvak'></div>" +
    "</div>" +
    "<div class='tr-stand weg' id='pr-stand-lijsten'>" +
    "<div class='paneel tr-formulier' id='pr-formulier'>" +
      "<h2>Periode en selectie <span class='tr-bij'>de leeftijd waarop iets exact gebeurt</span></h2>" +
      "<table class='tr-tabel'>" +
        "<tr><th>Tijdvak</th><td>" +
          "<div class='tr-regel'>" +
            "<label for='pr-van'>Van</label>" +
            "<input id='pr-van' placeholder='DD-MM-JJJJ'>" +
            "<label for='pr-tot'>Tot</label>" +
            "<input id='pr-tot' placeholder='DD-MM-JJJJ'>" +
          "</div>" +
          "<div class='tr-regel'>" + periodeStartRegel("pr") +
            periodeKnoppen("progressies", "pr") +
          "</div>" +
        "</td></tr>" +
        rij("Progressief", "lichaam", L.concat(H).map(x => vakje("lichaam", x.naam, x.glyf, true,
             x.naam)).join("")) +
        rij("Aspecten", "hoek", A.map(x => vakje("hoek", x.hoek, x.glyf,
             PR_ASPECT_UIT.indexOf(Number(x.hoek)) < 0, x.naam)).join("")) +
        rij("Radix", "doel", L.concat(H).map(x => vakje("doel", x.naam, x.glyf, true,
             x.naam)).join("")) +
        "<tr><th>Aanvullingen</th><td><div class='tr-rij2'>" +
          "<label class='tr-optie'><input type='checkbox' id='pr-ingress'> Huis ingress</label>" +
          "<label class='tr-optie'><input type='checkbox' id='pr-teken'> Teken ingress</label>" +
          "<label class='tr-optie'><input type='checkbox' id='pr-stations' checked> Stations</label>" +
        "</div></td></tr>" +
        "<tr><th>Lijstindeling</th><td><div class='tr-rij2 tr-rij2-actie'>" +
          PR_INDELING.map(k => "<label class='tr-optie'><input type='radio' name='pr-scheiding' value='" +
            k[0] + "'" + (prScheiding === k[0] ? " checked" : "") + "> " + k[1] + "</label>").join("") +
          "<button type='button' id='pr-bereken' class='hoofd tr-bereken-inrij'>Berekenen</button>" +
        "</div></td></tr>" +
      "</table>" +
    "</div>" +
    "<div class='tr-rij'>" +
      "<div class='paneel tr-lijst' id='pr-lijstvak'></div>" +
    "</div>" +
    "</div>" +
    "<div class='tr-stand weg' id='pr-stand-maanfasen'>" +
      "<div class='pren-kop'>" +
        "<span class='tr-start' role='group' aria-label='Hoeveel maanfasen'>" +
          "<span class='tr-startlabel'>fasen</span>" +
          "<button type='button' class='tr-startknop' data-pr-maan-aantal='4'>4</button>" +
          "<button type='button' class='tr-startknop' data-pr-maan-aantal='8'>8</button>" +
        "</span>" +
        "<span class='pren-telling' id='pr-maan-telling'></span>" +
      "</div>" +
      "<div class='paneel tr-lijst' id='pr-maan-lijstvak'></div>" +
    "</div>" +
    "<div class='tr-stand weg' id='pr-stand-prenataal'>" +
      "<div class='pren-kop'>" +
        "<span class='tr-start' role='group' aria-label='Hoe ver terug'>" +
          "<span class='tr-startlabel'>terug</span>" + PR_TERUG.map(j =>
            "<button type='button' class='tr-startknop' data-pr-terug='" + j + "'>" + j + " jaar</button>"
          ).join("") +
        "</span>" +
        "<span class='pren-telling' id='pr-pren-telling'></span>" +
      "</div>" +
      "<div class='paneel tr-lijst' id='pr-pren-lijstvak'></div>" +
    "</div>";

  Array.from(vak.querySelectorAll("[data-pr-alle]")).forEach(alle => {
    const soort = alle.getAttribute("data-pr-alle");
    alle.addEventListener("click", () => {
      Array.from(vak.querySelectorAll("[data-pr-" + soort + "]")).forEach(x => { x.checked = true; });
    });
  });
  Array.from(vak.querySelectorAll("[data-pr-geen]")).forEach(geen => {
    const soort = geen.getAttribute("data-pr-geen");
    geen.addEventListener("click", () => {
      Array.from(vak.querySelectorAll("[data-pr-" + soort + "]")).forEach(x => { x.checked = false; });
    });
  });
  Array.from(vak.querySelectorAll("input[name='pr-scheiding']")).forEach(r =>
    r.addEventListener("change", () => {
      prScheiding = r.value;
      if (prUit) { prToon(prUit); }   // opnieuw tekenen zonder opnieuw te rekenen
    }));
  Array.from(vak.querySelectorAll("[data-pr-jaar]")).forEach(b =>
    b.addEventListener("click", () => prPeriode(b.getAttribute("data-pr-jaar"))));
  Array.from(vak.querySelectorAll("[data-pr-start]")).forEach(b =>
    b.addEventListener("click", () => periodeStartKies("pr", b.getAttribute("data-pr-start"))));
  // Vier kwartieren of alle acht fasen (les 20-II in twee stappen): elke klik rekent opnieuw.
  Array.from(vak.querySelectorAll("[data-pr-maan-aantal]")).forEach(b =>
    b.addEventListener("click", () => {
      prMaanAantal = Number(b.getAttribute("data-pr-maan-aantal"));
      prMaanUit = null;
      prMaanfasen();
    }));
  // Hoe ver terug de prenatale lijst kijkt: de gebruiker bepaalt dat, en elke klik rekent opnieuw.
  Array.from(vak.querySelectorAll("[data-pr-terug]")).forEach(b =>
    b.addEventListener("click", () => {
      prPrenJaren = Number(b.getAttribute("data-pr-terug"));
      prPrenUit = null;
      prPrenataal();
    }));
  // Zelf typen zet de knoppen uit: wat er dan staat is niet meer het tijdvak van een knop.
  ["pr-van", "pr-tot"].forEach(id => {
    const veld = document.getElementById(id);
    if (veld) { veld.addEventListener("input", () => { prPeriodeStand = null; prPeriodeToon(); }); }
  });
  document.getElementById("pr-bereken").addEventListener("click", berekenProgressies);
  Array.from(vak.querySelectorAll("[data-pr-stand]")).forEach(b =>
    b.addEventListener("click", () => prStand(b.getAttribute("data-pr-stand"))));
  prLijstKop();
  prPeriode(PR_PERIODE_STANDAARD);
  prStand("nu");
}

function prStand(naam) {
  const nu = naam === "nu";
  const a = document.getElementById("pr-stand-nu"), b = document.getElementById("pr-stand-lijsten");
  const c = document.getElementById("pr-stand-prenataal");
  if (a) { a.classList.toggle("weg", !nu); }
  if (b) { b.classList.toggle("weg", naam !== "lijsten"); }
  if (c) { c.classList.toggle("weg", naam !== "prenataal"); }
  const d = document.getElementById("pr-stand-maanfasen");
  if (d) { d.classList.toggle("weg", naam !== "maanfasen"); }
  Array.from(document.querySelectorAll("[data-pr-stand]")).forEach(k =>
    k.classList.toggle("aan", k.getAttribute("data-pr-stand") === naam));
  if (nu) { prNu(); }
  if (naam === "prenataal" && !prPrenUit && !prPrenBezig) { prPrenataal(); }
  if (naam === "maanfasen" && !prMaanUit && !prMaanBezig) { prMaanfasen(); }
}


function prStandNu() {
  const knop = document.querySelector("[data-pr-stand].aan");
  const naam = knop ? knop.getAttribute("data-pr-stand") : "nu";
  // Het tijdvak invullen zodra er een kaart is: bij het bouwen van de tab bestaat die nog niet, en dan
  // progressies - honderd jaar is honderd efemeridedagen, dus dat is geen dure vraag.
  const van = document.getElementById("pr-van"), tot = document.getElementById("pr-tot");
  if (van && tot && !van.value) { prPeriode(PR_PERIODE_STANDAARD); }
  if (naam === "nu") { prNu(); }
  else if (prUit) { prVouwIn(); }
}


function prVouwIn() {
  const vak = document.getElementById("pr-formulier");
  if (!vak) { return; }
  // Dezelfde klasse als bij de transits: `.tr-formulier.ingeklapt` verbergt de kop en de banden, en
  // `.tr-formulier:not(.ingeklapt) ~ .tr-rij` houdt de lijst juist verborgen zolang het formulier
  // openstaat. Eén mechanisme voor beide tabellen.
  vak.classList.add("ingeklapt");
  let strook = document.getElementById("pr-samenvatting");
  if (!strook) {
    strook = document.createElement("div");
    strook.className = "tr-samenvatting";
    strook.id = "pr-samenvatting";
    strook.innerHTML = "<span id='pr-samenvatting-tekst'></span>" +
      "<button type='button' id='pr-wijzig'>wijzigen</button>" +
      "<span class='tr-scheider' aria-hidden='true'></span>" +
      "<button type='button' id='pr-afdrukken'>afdrukken</button>";
    vak.insertBefore(strook, vak.firstChild);
    document.getElementById("pr-wijzig").addEventListener("click", prVouwUit);
    document.getElementById("pr-afdrukken").addEventListener("click", prDrukLijstAf);
  }
  strook.hidden = false;
  const van = document.getElementById("pr-van").value, tot = document.getElementById("pr-tot").value;
  const uit = prUit || {};
  const leeftijden = (uit.van_leeftijd !== undefined)
    ? "leeftijd " + prLeeftijd(uit.van_leeftijd) + " tot " + prLeeftijd(uit.tot_leeftijd) + " jaar \u00b7 "
    : "";
  document.getElementById("pr-samenvatting-tekst").textContent = leeftijden + van + " tot " + tot;
}

function prVouwUit() {
  const vak = document.getElementById("pr-formulier");
  if (!vak) { return; }
  vak.classList.remove("ingeklapt");
  const strook = document.getElementById("pr-samenvatting");
  if (strook) { strook.hidden = true; }
}

function prLijstKop(tekst) {
  const vak = document.getElementById("pr-lijstvak");
  if (!vak) { return; }
  vak.innerHTML = "<h2>Exacte progressies <span class='tr-bij' id='pr-telling'>" +
    esc(tekst || "nog niet berekend") + "</span></h2>" +
    "<div class='tr-grens' id='pr-grens' hidden></div>" +
    "<div class='tr-voortgang' id='pr-voortgang' hidden>" +
      "<div class='tr-balk'><div id='pr-balkvulling'></div></div>" +
      "<span class='tr-balktekst' id='pr-balktekst'></span></div>" +
    "<div class='tr-scroll' id='pr-scroll'></div>";
}

function prVoortgang(v) {
  const balk = document.getElementById("pr-voortgang");
  if (!balk) { return; }
  balk.hidden = false;
  document.getElementById("pr-balkvulling").style.width = v.procent + "%";
  document.getElementById("pr-balktekst").textContent =
    v.procent + "% \u00b7 " + v.lichaam + " \u00b7 " + trGetal(v.regels) + " progressies";
}

// De momentopname: de progressieve kaart van vandaag. Eén verzoek, geen tijdvak - en dus licht genoeg
// om hem bij elk bezoek aan de stand opnieuw te vragen (de leeftijd schuift immers op).
async function prNu() {
  const vak = document.getElementById("pr-nuvak");
  if (!vak || !laatste || !laatste.kaart) {
    if (vak) { vak.innerHTML = "<p class='leegvlak'>Bereken eerst een horoscoop.</p>"; }
    return;
  }
  try {
    const ant = await fetch("/api/progressies/nu", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kaart: laatste.kaart }) });
    const j = await ant.json();
    if (!ant.ok) { throw new Error(j.fout || "onbekende fout"); }
    const rijen = j.standen || [];
    // Dezelfde cellen als de momentopname van de transits (`glyfNaam`, `trPos`): twee tabellen die
    // naast elkaar staan horen er hetzelfde uit te zien. De Ascendant en MC staan er als drift bij.
    let h = "<h2>Secundaire progressies <span class='tr-bij'>leeftijd " + prLeeftijd(j.leeftijd) +
      " jaar \u00b7 " + esc(alsNederlands(j.datum || "")) + "</span></h2>" +
      "<table class='lijst'><thead><tr><th>Planeet</th><th>Stand</th><th>R</th>" +
      "<th class='r'>Huis</th></tr></thead><tbody>";
    rijen.forEach(p => {
      h += "<tr><td>" + glyfNaam(p.naam, prNaam(p.naam)) + "</td><td>" + trPos(p.lengte) +
        "</td><td class='scheidend'>" + p.richting + "</td><td class='r'>" + p.huis + "</td></tr>";
    });
    h += "</tbody></table>";
    vak.innerHTML = h;
  } catch (e) {
    vak.innerHTML = "<p class='leegvlak'>De progressieve standen konden niet berekend worden: " +
      esc(e.message) + "</p>";
  }
}

// Dezelfde stroomlezer voor beide berekeningen: de schil stuurt NDJSON, met voortgangsregels en
async function prStroom(vraag, bijVoortgang) {
  const ant = await fetch("/api/progressies", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(vraag)
  });
  if (!ant.ok) {
    const j = await ant.json().catch(() => ({}));
    throw new Error(j.fout || ("de schil antwoordde met " + ant.status));
  }
  const lezer = ant.body.getReader();
  const dec = new TextDecoder();
  let rest = "", klaar = null;
  for (;;) {
    const { value, done } = await lezer.read();
    if (done) { break; }
    rest += dec.decode(value, { stream: true });
    const regels = rest.split("\n");
    rest = regels.pop();
    for (const r of regels) {
      if (!r.trim()) { continue; }
      const j = JSON.parse(r);
      if (j.voortgang) { if (bijVoortgang) { bijVoortgang(j.voortgang); } }
      else if (j.fout) { throw new Error(j.fout); }
      else if (j.klaar) { klaar = j; }
    }
    if (klaar) { try { await lezer.cancel(); } catch (e) {} break; }
  }
  if (rest.trim()) {
    const j = JSON.parse(rest);
    if (j.fout) { throw new Error(j.fout); }
    if (j.klaar) { klaar = j; }
  }
  if (!klaar) { throw new Error("de berekening gaf geen uitkomst terug."); }
  return klaar;
}

// --- Prenataal --------------------------------------------------------------
// De techniek: de secundaire directies terugwaarts vóór de geboorte, en dan alleen de **assen**. Dus:
// Ascendant en MC als de bewegende punten, 0° en 180°, en als doel de natale planeten - zo zie je
// wanneer de Ascendant of het MC vóór de geboorte over een planeet schoof.
//
// Geen formulier: alles komt uit de radix. Alleen de vraag hoe ver terug. Dertig jaar is de standaard,
// en dat is in wezen dertig dagen transits: je gaat dertig jaar jouw familiegeschiedenis in.
function prPrenDatum(datum, jaren) {
  const [jaar, maand, dag] = String(datum).split("-").map(Number);
  const twee = n => String(n).padStart(2, "0");
  return twee(dag) + "-" + twee(maand) + "-" + String(jaar - Number(jaren));
}

function prPrenAfstand(leeftijd) {
  // De afstand in maanden en jaren; de datum ernaast is exact, ook als een brontekst vaag blijft over
  // een maand of seizoen in dat jaar.
  let maanden = Math.round(Math.abs(leeftijd) * 12);
  const jaren = Math.floor(maanden / 12);
  maanden -= jaren * 12;
  return jaren + " j" + (maanden ? " " + maanden + " mnd" : "");
}

async function prPrenataal() {
  if (prPrenBezig) { return; }
  if (!laatste || !laatste.kaart) {
    zetMeld("let-op", ["Bereken eerst een horoscoop: de prenatale progressies horen bij een radix."]);
    return;
  }
  prPrenBezig = true;
  const vak = document.getElementById("pr-pren-lijstvak");
  const tel = document.getElementById("pr-pren-telling");
  if (tel) { tel.textContent = "bezig\u2026"; }
  if (vak) { vak.innerHTML = "<p class='lijst-noot'>De assen worden teruggezet\u2026</p>"; }
  try {
    const klaar = await prStroom({
      kaart: laatste.kaart,
      van: prPrenDatum(laatste.kaart.meta.datum, prPrenJaren),
      tot: prPrenDatum(laatste.kaart.meta.datum, 0),
      lichamen: ["Ascendant", "MC"],
      aspecten: [0, 180],
      doelen: ((trVorm && trVorm.lichamen) || []).map(x => x.naam),
      huis_ingress: false, teken_ingress: false, stations: false
    });
    prPrenUit = klaar;
    prPrenToon(klaar);
    zetMeld("", []);
  } catch (e) {
    zetMeld("let-op", ["De prenatale progressies konden niet berekend worden: " + e.message]);
    if (tel) { tel.textContent = "mislukt"; }
  } finally {
    prPrenBezig = false;
  }
}

function prPrenToon(uit) {
  const vak = document.getElementById("pr-pren-lijstvak");
  if (!vak) { return; }
  // De verste gebeurtenis bovenaan: je leest de familiegeschiedenis vooruit naar de geboorte toe.
  const rijen = (uit.doorgangen || []).slice().sort((a, b) => a.leeftijd - b.leeftijd);
  // Een oppositie met de Ascendant is de conjunctie met de Descendant; met het MC die met het IC.
  const EIND = { "Ascendant": { 0: "Ascendant", 180: "Descendant" },
                 "MC": { 0: "MC", 180: "IC" } };
  let h = "";
  if (rijen.length) {
    h += "<table class='lijst pren-lijst'><thead><tr><th>Datum</th><th>Vóór geboorte</th>" +
      "<th>As</th><th>Aspect</th><th>Natale planeet</th><th></th></tr></thead><tbody>";
    rijen.forEach((r, i) => {
      const eind = (EIND[r.lichaam] || {})[Number(r.hoek)] || r.lichaam;
      h += "<tr" + ((i % 2) ? " class='rij-b'" : "") + "><td>" + esc(alsNederlands(r.datum)) + "</td>" +
        "<td title='" + esc(String(r.leeftijd)) + " jaar'>" + prPrenAfstand(r.leeftijd) + "</td>" +
        "<td>" + esc(eind) + "</td><td>conjunctie</td><td>" +
        "<span class='seg seg-radix'>" + glyfVan(r.doel) +
        "<span class='naam'>" + esc(prNaam(r.doel)) + "</span>" +
        (r.doel_lengte === null || r.doel_lengte === undefined ? "<span></span>" : trPos(r.doel_lengte)) +
        "</span></td><td class='leeg'></td></tr>";
    });
    h += "</tbody></table>";
  } else {
    h += "<p class='lijst-noot'>Geen conjuncties van de assen met de natale planeten in deze " +
      prPrenJaren + " jaar.</p>";
  }
  vak.innerHTML = "<h2>Prenatale progressies <span class='tr-bij'>de assen vóór de geboorte</span></h2>" +
    "<div class='tr-scroll'>" + h + "</div>";
  const tel = document.getElementById("pr-pren-telling");
  if (tel) {
    tel.textContent = trGetal(rijen.length) + (rijen.length === 1 ? " moment" : " momenten") +
      " in " + prPrenJaren + " jaar";
  }
  Array.from(document.querySelectorAll("[data-pr-terug]")).forEach(b =>
    b.classList.toggle("aan", Number(b.getAttribute("data-pr-terug")) === prPrenJaren));
}

// De maanfasen: alleen de hoek tussen de progressieve Zon en Maan onderling - geen radixpunten.
// Acht grenzen van 45 graden, en elke nieuwe maan begint een nieuwe cyclus.
async function prMaanfasen() {
  if (prMaanBezig) { return; }
  if (!laatste || !laatste.kaart) {
    zetMeld("let-op", ["Bereken eerst een horoscoop: de maanfasen horen bij een radix."]);
    return;
  }
  prMaanBezig = true;
  const vak = document.getElementById("pr-maan-lijstvak");
  const tel = document.getElementById("pr-maan-telling");
  if (tel) { tel.textContent = "bezig\u2026"; }
  if (vak) { vak.innerHTML = "<p class='lijst-noot'>De maanfasen worden berekend\u2026</p>"; }
  try {
    const ant = await fetch("/api/maanfasen", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kaart: laatste.kaart, fasen: prMaanAantal })
    });
    if (!ant.ok) {
      const j = await ant.json().catch(() => ({}));
      throw new Error(j.fout || ("de schil antwoordde met " + ant.status));
    }
    const uit = await ant.json();
    prMaanUit = uit;
    prMaanToon(uit);
    zetMeld("", []);
  } catch (e) {
    zetMeld("let-op", ["De maanfasen konden niet berekend worden: " + e.message]);
    if (tel) { tel.textContent = "mislukt"; }
  } finally {
    prMaanBezig = false;
  }
}

function prMaanToon(uit) {
  const vak = document.getElementById("pr-maan-lijstvak");
  if (!vak) { return; }
  const rijen = uit.fasen || [];
  if (!rijen.length) {
    vak.innerHTML = "<p class='lijst-noot'>Geen maanfasen gevonden.</p>";
    return;
  }
  let h = "<table class='lijst maan-lijst'><thead><tr><th>Datum</th><th class='r'>Leeftijd</th>" +
    "<th>Fase</th><th>Stand</th><th>Sleutelwoord</th><th></th></tr></thead>";
  let vorigeCyclus = 0;
  rijen.forEach((r, i) => {
    if (r.cyclus !== vorigeCyclus) {
      if (vorigeCyclus) { h += "</tbody>"; }
      // Bij de eerste cyclus ligt die vóór de geboorte; dat staat er dan ook bij.
      const start = rijen.filter(x => x.cyclus === r.cyclus && x.hoek === 0)[0] || r;
      const voor = r.cyclus === 1 && start.leeftijd < 0
        ? " \u00b7 " + prPrenAfstand(start.leeftijd) + " v\u00f3\u00f3r de geboorte" : "";
      h += "<tbody><tr class='scheidingsrij'><td colspan='6'>Cyclus " + r.cyclus +
        " \u00b7 nieuwe maan " + esc(alsNederlands(start.datum)) + voor + "</td></tr>";
      vorigeCyclus = r.cyclus;
    }
    h += "<tr" + ((i % 2) ? " class='rij-b'" : "") + ">" +
      "<td>" + esc(alsNederlands(r.datum)) + "</td>" +
      "<td class='r' title='" + esc(String(r.leeftijd)) + " jaar'>" + prLeeftijd(r.leeftijd) + "</td>" +
      "<td>" + esc(r.naam) + " <span class='maan-hoek'>" + r.hoek + "\u00b0</span></td>" +
      "<td title='" + esc((r.positie.graad + 1) + "e graad van " + r.positie.teken) +
        "'><span class='seg seg-radix'>" + glyfVan("Maan") +
        "<span class='naam'>" + esc(r.positie.teken) + "</span>" +
        "<span class='pos'>" + String(r.positie.graad).padStart(2, "0") + "\u00b0" +
        String(r.positie.minuut).padStart(2, "0") + "'</span></span></td>" +
      "<td class='maan-sleutel'>" + esc(r.sleutelwoord) + "</td><td class='leeg'></td></tr>";
  });
  h += "</tbody></table>";
  const nu = uit.nu;
  const kop = nu
    ? "<p class='maan-nu'>Nu: <b>fase " + nu.fase.nummer + " \u00b7 " + esc(nu.fase.naam) + "</b>" +
      " \u2014 " + Math.round(nu.graden) + "\u00b0 in de cyclus, sinds " +
      esc(alsNederlands(nu.fase.datum)) + " (cyclus " + nu.fase.cyclus + ")</p>"
    : "";
  // De knop heet "fasen 4 / 8" en de kop zegt hetzelfde: vier of acht fasen, cyclus na cyclus - geen
  // "kwartieren", want dat is een ander woord voor hetzelfde.
  vak.innerHTML = "<h2>Progressieve maanfasen <span class='tr-bij'>" +
    (prMaanAantal === 4 ? "de vier fasen" : "de acht fasen") + ", cyclus na cyclus</span></h2>" +
    kop + "<div class='tr-scroll'>" + h + "</div>";
  const tel = document.getElementById("pr-maan-telling");
  if (tel) {
    tel.textContent = trGetal(rijen.length) + " fasen in " + trGetal(vorigeCyclus) +
      (vorigeCyclus === 1 ? " cyclus" : " cycli");
  }
  Array.from(document.querySelectorAll("[data-pr-maan-aantal]")).forEach(b =>
    b.classList.toggle("aan", Number(b.getAttribute("data-pr-maan-aantal")) === prMaanAantal));
}

async function berekenProgressies() {
  if (prBezig) { return; }
  if (!laatste || !laatste.kaart) {
    zetMeld("let-op", ["Bereken eerst een horoscoop: de progressies horen bij een radix."]);
    return;
  }
  const lichamen = prWaarden("lichaam");
  const aspecten = prWaarden("hoek").map(Number);
  const doelen = prWaarden("doel");
  const ingress = document.getElementById("pr-ingress").checked;
  const teken = document.getElementById("pr-teken").checked;
  const stations = document.getElementById("pr-stations").checked;
  if (!lichamen.length) {
    zetMeld("let-op", ["Kies ten minste \u00e9\u00e9n progressief lichaam."]);
    return;
  }
  if (!aspecten.length && !doelen.length && !ingress && !teken && !stations) {
    zetMeld("let-op", ["Er valt niets te berekenen: kies aspecten of radixpunten, of zet een aanvulling aan."]);
    return;
  }
  const van = document.getElementById("pr-van").value;
  const tot = document.getElementById("pr-tot").value;

  prBezig = true;
  const knop = document.getElementById("pr-bereken");
  const oud = knop.textContent;
  knop.disabled = true;
  knop.textContent = "bezig\u2026";
  prLijstKop("bezig\u2026");
  let balkTimer = setTimeout(() => {
    const b = document.getElementById("pr-voortgang");
    if (b) { b.hidden = false; }
  }, 250);
  try {
      const klaar = await prStroom({
      kaart: laatste.kaart, van: van, tot: tot, lichamen: lichamen,
      aspecten: aspecten, doelen: doelen,
      huis_ingress: ingress, teken_ingress: teken, stations: stations
    }, prVoortgang);
    zetMeld("", []);
    prToon(klaar);
    prVouwIn();     // de lijst krijgt de hoogte die het formulier niet meer nodig heeft
  } catch (e) {
    zetMeld("let-op", ["De progressies konden niet berekend worden: " + e.message]);
    const tel = document.getElementById("pr-telling");
    if (tel) { tel.textContent = "niet berekend"; }
  } finally {
    clearTimeout(balkTimer);
    knop.disabled = false;
    knop.textContent = oud;
    prBezig = false;
    const b = document.getElementById("pr-voortgang");
    if (b) { b.hidden = true; }
  }
}

// Wat er in de selectie staat, in één regel: hoeveel lichamen, welke aspecten, welke aanvullingen en
// hoe de lijst is ingedeeld. Zonder die regel is een los vel in een map niet te plaatsen.
function prSelectieTekst() {
  const lichamen = prWaarden("lichaam"), hoeken = prWaarden("hoek"), doelen = prWaarden("doel");
  const aanvulling = [];
  const aan = (id) => { const e = document.getElementById(id); return !!(e && e.checked); };
  if (aan("pr-ingress")) { aanvulling.push("huis ingress"); }
  if (aan("pr-teken")) { aanvulling.push("teken ingress"); }
  if (aan("pr-stations")) { aanvulling.push("stations"); }
  const indeling = PR_INDELING.filter(k => k[0] === prScheiding).map(k => k[1])[0] || "";
  const delen = [lichamen.length + (lichamen.length === 1 ? " lichaam" : " lichamen")];
  if (hoeken.length && doelen.length) {
    delen.push("aspecten " + hoeken.join(", ") + " op " + doelen.length + " radixpunten");
  } else if (hoeken.length) { delen.push("aspecten " + hoeken.join(", ")); }
  else if (doelen.length) { delen.push(doelen.length + " radixpunten"); }
  if (aanvulling.length) { delen.push(aanvulling.join(", ")); }
  delen.push("indeling " + indeling);
  return delen.join(" \u00b7 ");
}

// De lijst. Kolommen in de volgorde waarin je leest: wanneer (datum en leeftijd), wie, wat, waar.
// De scheidingen gaan over **leeftijd** en niet over de kalender: bij progressies is de leeftijd de
// maat. Standaard per decennium (tien banden over een leven); per jaar en per maand zijn er voor een
// kort tijdvak, want dan is een decennium één band. `geen` laat de lijst doorlopen.
function prToon(uit) {
  prUit = uit;
  const rijen = uit.doorgangen || [];
  const totaal = uit.totaal || rijen.length;
  const vak = document.getElementById("pr-scroll");
  if (!vak) { return; }

  const glyfAspect = {};
  if (trVorm) { (trVorm.aspecten || []).forEach(a => { glyfAspect[String(a.hoek)] = a.glyf; }); }
  const MAAND = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
                 "september", "oktober", "november", "december"];
  // De leeftijd blijft staan waar hij hoort: in de kolom, op de plek waar de transits de tijd hebben.
  // Een band "leeftijd 60-69" zou daar een tweede indeling naast zetten,
  const groepVan = (datum) => {
    const [jr, mm] = String(datum).split("-");
    if (prScheiding === "decennium") {
      const dec = Math.floor(Number(jr) / 10) * 10;
      return { sleutel: String(dec), naam: dec + "\u2013" + (dec + 9) };
    }
    if (prScheiding === "maand") {
      return { sleutel: jr + "-" + mm, naam: (MAAND[Number(mm) - 1] || mm) + " " + jr };
    }
    return { sleutel: jr, naam: jr };
  };

  // Eén tbody per groep, net als bij de transits: dan begint de zebra per groep opnieuw en is de
  // groepskop zelf nooit gestreept. De zebra telt alleen de gegevensrijen.
  const groepen = [];
  let zebra = 0, vorige = null;
  if (prScheiding === "geen") { groepen.push({ naam: "", rijen: [] }); }
  rijen.forEach(r => {
    if (prScheiding !== "geen") {
      const g = groepVan(r.datum);
      if (g.sleutel !== vorige) {
        vorige = g.sleutel;
        groepen.push({ naam: g.naam, rijen: [] });
        zebra = 0;
      }
    }
    // Dezelfde vaste segmenten als de transitlijst: [glyph][℞][graad] en [glyph][naam][graad]. Daardoor
    // begint elk getal op dezelfde plek, ook als de ene planeet terugloopt en de andere niet.
    const seg = (klasse, delen) => "<span class='seg " + klasse + "'>" + delen.join("") + "</span>";
    const leegvak = "<span></span>";
    const graad = (r.punt_lengte === null || r.punt_lengte === undefined) ? leegvak : trPos(r.punt_lengte);
    // **Het huis hoort bij de progressieve stand**, en staat daarom achter de progressieve planeet en
    // huizen van de progressieve planeten tonen en misschien ook achter de progressieve planeet en niet
    // achter de radix planeet."*). "H5" in een eigen smal vakje, zodat het getal niet als graad leest.
    // Bij een huis-ingress staat het huis al in de zin ernaast ("gaat naar | huis 12"), dus daar geen
    // tweede keer hetzelfde getal.
    const huis = (r.soort === "huis_ingress" || r.huis === undefined || r.huis === null || r.huis === "")
      ? leegvak
      : "<span class='pr-huis' title='de progressieve stand valt in radixhuis " + esc(String(r.huis)) +
        "'>H" + esc(String(r.huis)) + "</span>";
    const progressief = seg("seg-transit", [
      glyfVan(r.lichaam),
      r.richting === "R" ? "<span class='retro'>\u211e</span>" : leegvak,
      graad,
      huis]);
    let asp, radix = "";
    if (r.soort === "station") {
      asp = "<span class='naam'>stationair</span>";
      radix = seg("seg-radix", [leegvak,
        "<span class='naam'>" + (r.richting === "R" ? "gaat retrograde" : "gaat direct") + "</span>",
        leegvak]);
    } else if (r.soort === "huis_ingress") {
      // "gaat naar" in de aspectkolom, het doel in de radixkolom - dezelfde vorm als bij de transits.
      asp = "<span class='naam'>gaat naar</span>";
      radix = seg("seg-radix", [leegvak,
        "<span class='naam'>" + (r.huis ? "huis " + r.huis : "over " + esc(r.doel)) + "</span>",
        leegvak]);
    } else if (r.soort === "teken_ingress") {
      // Alleen bij de progressies (de transits kennen geen teken-ingress): "gaat naar | Boogschutter".
      // "teken Boogschutter in" zei hetzelfde drie keer.
      asp = "<span class='naam'>gaat naar</span>";
      radix = seg("seg-radix", [leegvak,
        "<span class='naam'>" + esc(r.doel) + "</span>", leegvak]);
    } else {
      asp = "<span class='glyf'>" + (glyfAspect[String(r.hoek)] || "") + "</span>" +
        "<span class='naam'>" + esc(String(r.aspect || "").toLowerCase()) + "</span>";
      radix = seg("seg-radix", [glyfVan(r.doel),
        "<span class='naam'>" + esc(prNaam(r.doel)) + "</span>",
        (r.doel_lengte === null || r.doel_lengte === undefined) ? leegvak : trPos(r.doel_lengte)]);
    }
    groepen[groepen.length - 1].rijen.push(
      "<tr" + ((zebra++ % 2) ? " class='rij-b'" : "") + "><td>" +
      esc(alsNederlands(r.datum)) + "</td><td class='r'>" + prLeeftijd(r.leeftijd) + "</td><td>" + progressief +
      "</td><td class='aspvak'>" + asp + "</td><td>" + radix + "</td><td class='leeg'></td></tr>");
  });

  // Zes kolommen: Datum, Leeftijd (waar de transits Tijd hebben), Progressief (met het huis van die
  // stand), Aspect, Radix en een lege sluitkolom. Er is geen kolom "Huis": dat getal hoort bij de
  // progressieve planeet en staat daar achter.
  let h = "<table class='lijst pr-lijst'><thead>" +
    "<tr class='drukkop'><td colspan='6'>" + prDrukKop() + "</td></tr>" +
    "<tr><th>Datum</th><th class='r'>Leeftijd</th><th>Progressief</th><th>Aspect</th>" +
    "<th>Radix</th><th></th></tr></thead>";
  groepen.forEach(g => {
    h += "<tbody>";
    if (g.naam) { h += "<tr class='scheidingsrij'><td colspan='6'>" + esc(g.naam) + "</td></tr>"; }
    h += g.rijen.join("") + "</tbody>";
  });
  h += "</table>";
  vak.innerHTML = h;

  // Het woord bij de telling volgt de inhoud, net als bij de transits: staan er alleen aspecten in,
  // dan heet het ook zo.
  const eenheid = (rijen.length && rijen.every(r => r.soort === "aspect")) ? "aspecten" : "momenten";
  const tel = document.getElementById("pr-telling");
  if (tel) { tel.textContent = trGetal(totaal) + " " + eenheid; }
  const grens = document.getElementById("pr-grens");
  if (grens) {
    if (uit.afgekapt) {
      grens.hidden = false;
      grens.textContent = "De lijst stopt bij " + trGetal(uit.grens) + " van de " + trGetal(totaal) +
        " " + eenheid + ". Neem een korter tijdvak of kies minder lichamen.";
    } else if (uit.let_op) {
      grens.hidden = false;
      grens.textContent = uit.let_op;
    } else {
      grens.hidden = true;
      grens.textContent = "";
    }
  }
}
