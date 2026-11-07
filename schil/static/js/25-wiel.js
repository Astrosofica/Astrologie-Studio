// 25-wiel.js
//
// Het wiel: de standen, de tijdstapper, de leeftijdsstapper en het PNG.
//
// Alle bestanden delen één werkruimte en worden in deze volgorde geladen; 90-start.js
// komt achteraan en gebruikt wat hierboven staat.


// ---------------------------------------------------------------------------------------------
//
// De knop hangt boven de tekening in de hoek die de cirkel leeg laat. Het is géén laag
// over een laag - de twee standen hebben andere stralen (canvas 1000 tegen 1092), dus de ringen zouden
// niet samenvallen; de knop vervangt de tekening. De prijs is dat de radix 8,4 % krimpt, en dat is
// precies wat de gebruiker ziet gebeuren als hij klikt.
// ---------------------------------------------------------------------------------------------
// (`wielBi`), maar met een derde stand is waar/niet waar te weinig: de tekening, het tijdveld, de
// bestandsnaam en de afdruk hangen allemaal aan **welke** stand het is.
let wielStand = "radix";

// De standen van het hoofd wiel. Vandaag twee: de radix en de transits. De progressies komen er in
// dezelfde vorm bij (de maker: "de progressies zullen we vrijwel identiek gaan aanpakken") en
// in jaar 3 de synastrie — daarom een keuzelijst en geen vinkje, en daarom staan ze hier als lijst
// in plaats van als tekst op de knop. Een stand die nog niet bestaat komt er niet in: dan toont het
// scherm een functie die er niet is.
// De keuzelijst wordt bij elk gebruik opnieuw samengesteld uit wat deze gebruiker kan: jaar 1 heeft
// geen transits en geen progressies, dus dan blijft er één stand over en is er niets te kiezen.
const WIELSTANDEN = [["radix", "radix"], ["transits", "transits"], ["progressies", "progressie"]];

function zetWielSchakel() {
  const vak = document.getElementById("wielvak");
  if (!vak) { return; }
  let keuze = document.getElementById("wiel-schakel");
  if (!keuze) {
    keuze = document.createElement("select");
    keuze.id = "wiel-schakel";
    keuze.className = "wielschakel";
    keuze.setAttribute("aria-label", "Stand van het wiel");
    WIELSTANDEN.forEach(([waarde, tekst]) => {
      const o = document.createElement("option");
      o.value = waarde;
      o.textContent = tekst;
      keuze.appendChild(o);
    });
    keuze.addEventListener("change", wielStandWissel);
    vak.appendChild(keuze);
  }
  // De standkeuze hoort bij de techniek: staat een module uit (jaar 1), dan is die stand er ook niet.
  const mag = !!(laatste && laatste.svg);
  const standen = WIELSTANDEN.filter(([waarde]) =>
    waarde === "radix" || (waarde === "transits" && trMag()) ||
    (waarde === "progressies" && prMag()));
  if (!mag || standen.length < 2) { wielStand = "radix"; }
  const nodig = standen.map(([waarde]) => waarde).join(",");
  if (Array.from(keuze.options).map(o => o.value).join(",") !== nodig) {
    keuze.innerHTML = "";
    standen.forEach(([waarde, tekst]) => {
      const o = document.createElement("option");
      o.value = waarde;
      o.textContent = tekst;
      keuze.appendChild(o);
    });
  }
  keuze.hidden = !(mag && standen.length > 1);
  keuze.value = wielStand;
  keuze.classList.toggle("aan", wielStand !== "radix");
  keuze.title = {
    radix: "Kies de stand van het wiel: de radix, of de radix met een techniek eromheen",
    transits: "De transits van het gekozen moment staan in de buitenring",
    progressies: "De progressieve standen van de gekozen leeftijd staan in de buitenring"
  }[wielStand];
  zetHoverLeesregel();
  zetWielMoment();
  zetWielLeeftijd();
}

async function wielStandWissel(ev) {
  const gekozen = ev.target.value;
  if (gekozen === "transits" && !trMag()) { return; }
  if (gekozen === "progressies" && !prMag()) { return; }
  wielStand = gekozen;
  zetWielSchakel();
  // Het eerste bezoek aan een stand vult zijn eigen tijd: het moment bij de transits, de leeftijd van
  // vandaag bij de progressies. Kom je terug, dan blijft wat je zelf koos - het staat in het veld,
  // dus het kan niet ongezien verouderen.
  if (wielStand === "transits" && !wielMoment) { wmNu(); return; }
  await wielTeken();
}

// De leesregel hangt aan het wielvak en niet aan de knopen: die verdwijnen bij elke nieuwe tekening,
// en luisteraars op de knopen verdwijnen daarmee mee. De tekst komt kant en klaar uit de tekening
// (`data-tip` op het raakvlak), dus de pagina rekent niets en er is één bron voor de notatie.
function zetHoverLeesregel() {
  const vak = document.getElementById("wielvak");
  if (!vak || vak.dataset.hover === "1") { return; }
  vak.dataset.hover = "1";
  vak.addEventListener("mouseover", (e) => {
    const vlak = e.target.closest ? e.target.closest(".transit-vlak") : null;
    if (vlak) { zetLeesregel(vlak.getAttribute("data-tip") || ""); }
  });
  vak.addEventListener("mouseout", (e) => {
    const vlak = e.target.closest ? e.target.closest(".transit-vlak") : null;
    if (vlak) { zetLeesregel(""); }
  });
}

function zetLeesregel(tekst) {
  const cel = document.getElementById("status-hover");
  if (!cel) { return; }
  cel.textContent = tekst || "";
  cel.classList.toggle("aan", !!tekst);
}

// 2019/365 invoegen (in Word 2016 staat het niet eens in de lijst) en zet het bij het opslaan als pdf
// vaak alsnog om naar een plaatje. PNG opent overal. Waarom geen JPG: die legt zijn ruis juist om de
// dunne tikjes en de glyph-randen - precies waar deze tekening scherp moet blijven - en wordt hier niet
// kleiner. Waarom de browser en niet de server: dit is een web-app; een bestand dat de server schrijft
// komt op t640 terecht, niet in de map waar de gebruiker Word opent.
//
// De maat is 1024 eenheden: de glyph wordt dan 27 px en de kleinste stukjes (de minuut op 20 pt)
// 20 px - leesbaar zonder in te zoomen. 2000 zou 52 px geven; dat is voor drukwerk op A4-breedte
// (295 dpi), niet voor een plaatje in een verslag.
const EXPORT_PX = 1024;

async function bewaarWielAlsPng() {
  const svg = document.querySelector("#wielvak svg");
  if (!svg) {
    zetLeesregel("Nog geen wiel om te bewaren: bereken eerst een horoscoop");
    setTimeout(() => zetLeesregel(""), 4000);
    return;
  }
  // De tekening zoals hij in het vak staat, dus met de stand die op dit moment open is: het enkele wiel
  // of de bi-stand met de transits. De raakvlakken van de leesregel gaan mee, maar die hebben geen
  // vulling en tekenen dus niets.
  const bron = svg.outerHTML;
  const url = URL.createObjectURL(new Blob([bron], { type: "image/svg+xml;charset=utf-8" }));
  const beeld = new Image();
  try {
    await new Promise((klaar, mis) => { beeld.onload = klaar; beeld.onerror = mis; beeld.src = url; });
    const doek = document.createElement("canvas");
    doek.width = EXPORT_PX; doek.height = EXPORT_PX;
    const kwast = doek.getContext("2d");
    // Papier, geen doorzichtige achtergrond: het wiel is een tekening op wit, en een transparante PNG
    // komt in Word op een gekleurde pagina anders lelijk uit.
    kwast.fillStyle = "#ffffff";
    kwast.fillRect(0, 0, EXPORT_PX, EXPORT_PX);
    kwast.drawImage(beeld, 0, 0, EXPORT_PX, EXPORT_PX);
    const koppeling = document.createElement("a");
    koppeling.href = doek.toDataURL("image/png");
    koppeling.download = wielBestandsnaam();
    koppeling.click();
  } catch (fout) {
    // De enige echte faalweg: verwijst de tekening naar iets buiten de svg, dan weigert de browser het
    // doek te bewaren (een "getint" doek). `ijk-biwiel` bewaakt dat de tekening nergens naar buiten wijst.
    zetLeesregel("Opslaan mislukt: " + (fout && fout.message ? fout.message : "onbekende fout"));
    setTimeout(() => zetLeesregel(""), 6000);
  } finally {
    URL.revokeObjectURL(url);
  }
}

function wielBestandsnaam() {
  const meta = (laatste && laatste.kaart && laatste.kaart.meta) ? laatste.kaart.meta : {};
  const veilig = (s) => String(s || "").toLowerCase()
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  const naam = veilig(meta.naam) || "horoscoop";
  const datum = veilig(meta.datum) || veilig(new Date().toISOString().slice(0, 10));
  return "wiel-" + naam + "-" + datum + "-" + wielStand + ".png";
}

// Wat er in het wielvak staat: de radix zelf, of dezelfde radix met de transits in de buitenring.
// Zonder transits komt `laatste.svg` terug — de tekening die de server bij het berekenen maakte, dus
// niets wordt opnieuw gerekend en het jaar-1-wiel blijft wat het was.
//
// De tekening woont in een eigen laag (`.wielbeeld`), zodat de bediening in het vak
// blijft staan: de standkeuze en de datumstapper zijn broertjes van de tekening, geen kinderen. Vult
// `wielTeken()` het hele vak, dan verliest de datumstapper bij elke toetsaanslag zijn focus - en dan
// kun je niet twee keer achter elkaar op het pijltje drukken.
function zetWielBeeld(inhoud) {
  const vak = document.getElementById("wielvak");
  if (!vak) { return; }
  let beeld = vak.querySelector(".wielbeeld");
  if (!beeld) {
    beeld = document.createElement("div");
    beeld.className = "wielbeeld";
    vak.appendChild(beeld);
  }
  beeld.innerHTML = inhoud;
  zetWielSchakel();
  zetWielMoment();
}

// --- de datumstapper bij het bi-wheel --------------------------------------------------------
//
// Het bi-wheel **bevriest de tijd**: geen dynamische tik van 20 seconden, want die geldt alleen voor de
// NU-chart. In plaats daarvan zet je het moment zelf: pijltjes omhoog/omlaag hogen het segment op waar
// de cursor staat (uur, dag, maand of jaar) met gewone datumrekenkunde — de laatste dag van de maand
// + 1 dag is de eerste van de nieuwe maand, en de laatste dag van de maand + 1 maand is de laatste dag
// van februari, niet de derde van maart. Typen overschrijft het segment.
//
// **UT en niet de plaatselijke tijd.** Een transitmoment is een berekend ogenblik, geen burgerklok:
// met UT is een uur altijd een uur, ook in de nacht van de zomertijd toen de klok 02:30 oversloeg of
// twee keer aanwees. De plaatselijke tijd van de kaart staat in de tooltip, als etiket.
let wielMoment = null;   // Date met UTC-getters, of null zolang de stand niet gekozen is
// De leeftijd van de progressiestand. **Eén** getal als waarheid en de twee veldjes als weergave: de
// schil rekent met een leeftijd en geeft de datum terug die erbij hoort, dus de staat moet dezelfde
// vorm hebben - anders lopen beeld en datum een halve maand uit elkaar gemeten: "63 jaar
// 04 mnd" naast de datum van 3,57 maanden).
let wlLeeftijd = 0;
let wlSegment = 0;       // 0 = jaren, 1 = maanden (welk deel de pijltjes raken)
let wlBuffer = "";
let wlGekozen = false;   // heeft de gebruiker zelf een leeftijd gezet?
let wlLaatste = null;    // het laatste antwoord van de schil, voor de datum ernaast
let wmSegment = 0;       // 0 dag, 1 maand, 2 jaar, 3 uur, 4 minuut
let wmBuffer = "";       // wat er in het actieve segment getypt is
let wmVerzoek = 0;       // het laatste antwoord van de server wint (snel achter elkaar stappen)
let wmStempel = "";      // welke kaart het moment liet bevriezen

const WM_DELEN = [
  { naam: "dag", lengte: 2, min: 1, max: 31 },
  { naam: "maand", lengte: 2, min: 1, max: 12 },
  { naam: "jaar", lengte: 4, min: 1800, max: 2400 },
  { naam: "uur", lengte: 2, min: 0, max: 23 },
  { naam: "minuut", lengte: 2, min: 0, max: 59 },
];

function wmDagenInMaand(jaar, maand) {
  return new Date(Date.UTC(jaar, maand, 0)).getUTCDate();   // maand 1-12; dag 0 = laatste van de vorige
}

function wmTwee(n) { return String(n).padStart(2, "0"); }

function wmIso() {
  if (!wielMoment) { return ""; }
  return wielMoment.getUTCFullYear() + "-" + wmTwee(wielMoment.getUTCMonth() + 1) + "-" +
         wmTwee(wielMoment.getUTCDate()) + "T" + wmTwee(wielMoment.getUTCHours()) + ":" +
         wmTwee(wielMoment.getUTCMinutes());
}

// De enige weg waarlangs het moment verandert: hier wordt het begrensd (1800-2400, en de dag op de
// maandlengte), hier wordt het getekend, en hier gaat de vraag naar de server.
function wmZetMoment(d) {
  if (!(d instanceof Date) || isNaN(d.getTime())) { return; }
  const jaar = Math.min(WM_DELEN[2].max, Math.max(WM_DELEN[2].min, d.getUTCFullYear()));
  const maand = Math.min(11, Math.max(0, d.getUTCMonth()));
  const dag = Math.min(wmDagenInMaand(jaar, maand + 1), Math.max(1, d.getUTCDate()));
  wielMoment = new Date(Date.UTC(jaar, maand, dag, d.getUTCHours(), d.getUTCMinutes()));
  // De invoerbuffer blijft staan: bij het typen van "15" wordt na de 1 immers al een keer getekend, en
  // die tussenstand mag de 5 niet wissen (in de proef werd "15" 05).
  wmToon();
  wielTeken();
}

function wmNu() {
  wmBuffer = "";
  const d = new Date();
  wmZetMoment(new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(),
                                d.getUTCHours(), d.getUTCMinutes())));
}

function wmStap(richting) {
  if (!wielMoment) { return; }
  const d = new Date(wielMoment.getTime());
  if (wmSegment === 3) { d.setUTCHours(d.getUTCHours() + richting); }
  else if (wmSegment === 4) { d.setUTCMinutes(d.getUTCMinutes() + richting); }
  else if (wmSegment === 0) { d.setUTCDate(d.getUTCDate() + richting); }
  else {
    // Eerst de dag op 1 zetten en hem daarna terugzetten: anders wordt de laatste dag van de maand + 1 maand
    // de derde van maart (JavaScript laat de dag doorlopen in de volgende maand).
    const dag = d.getUTCDate();
    d.setUTCDate(1);
    if (wmSegment === 1) { d.setUTCMonth(d.getUTCMonth() + richting); }
    else { d.setUTCFullYear(d.getUTCFullYear() + richting); }
    d.setUTCDate(Math.min(dag, wmDagenInMaand(d.getUTCFullYear(), d.getUTCMonth() + 1)));
  }
  wmZetMoment(d);
}

function wmPasToe(waarde, klaar) {
  if (!wielMoment) { return; }
  const deel = WM_DELEN[wmSegment];
  const w = Math.min(deel.max, Math.max(deel.min, waarde));
  let jaar = wielMoment.getUTCFullYear(), maand = wielMoment.getUTCMonth() + 1;
  let dag = wielMoment.getUTCDate();
  let uur = wielMoment.getUTCHours(), minuut = wielMoment.getUTCMinutes();
  if (deel.naam === "dag") { dag = w; }
  else if (deel.naam === "maand") { maand = w; }
  else if (deel.naam === "jaar") { jaar = w; }
  else if (deel.naam === "uur") { uur = w; }
  else { minuut = w; }
  dag = Math.min(dag, wmDagenInMaand(jaar, maand));
  if (klaar) {
    wmBuffer = "";
    wmSegment = Math.min(WM_DELEN.length - 1, wmSegment + 1);
  }
  wmZetMoment(new Date(Date.UTC(jaar, maand - 1, dag, uur, minuut)));
}

function wmType(cijfer) {
  const deel = WM_DELEN[wmSegment];
  let buffer = (wmBuffer + cijfer).slice(-deel.lengte);
  let waarde = parseInt(buffer, 10);
  // "13" in de maand is geen 13: dan begint de invoer opnieuw bij de 3.
  if (waarde > deel.max) { buffer = cijfer; waarde = parseInt(buffer, 10); }
  wmBuffer = buffer;
  // Een jaar pas toepassen bij vier cijfers: 1, 19 en 198 zijn geen jaartal.
  if (deel.naam === "jaar" && buffer.length < 4) { wmToon(); return; }
  wmPasToe(waarde, buffer.length >= deel.lengte);
}

function wmToets(ev) {
  const k = ev.key;
  if (k === "ArrowUp" || k === "ArrowDown") {
    ev.preventDefault();
    wmBuffer = "";
    wmStap(k === "ArrowUp" ? 1 : -1);
    return;
  }
  if (k === "ArrowLeft" || k === "ArrowRight") {
    ev.preventDefault();
    wmBuffer = "";
    wmSegment = Math.min(WM_DELEN.length - 1,
      Math.max(0, wmSegment + (k === "ArrowRight" ? 1 : -1)));
    wmToon();
    return;
  }
  if (k === "Home" || k === "End") {
    ev.preventDefault();
    wmBuffer = "";
    wmSegment = k === "Home" ? 0 : WM_DELEN.length - 1;
    wmToon();
    return;
  }
  if (/^[0-9]$/.test(k)) { ev.preventDefault(); wmType(k); return; }
  if (k === "Backspace" || k === "Delete") { ev.preventDefault(); wmBuffer = ""; wmToon(); }
}

function wmKlik(ev) {
  const seg = ev.target && ev.target.closest ? ev.target.closest(".wm-seg") : null;
  if (!seg) { return; }
  wmSegment = Number(seg.getAttribute("data-seg"));
  wmBuffer = "";
  wmToon();
  const veld = document.getElementById("wielmoment");
  if (veld) { veld.focus(); }
}

// De plaatselijke tijd van de kaart als etiket in de tooltip: het moment is UT, maar een mens leest
// zijn eigen klok. De zone komt uit de kaart (`tijdzone_id`), niet uit de instellingen - een kaart uit
// Lissabon houdt zijn eigen zone.
function wmLokaal() {
  const meta = (laatste && laatste.kaart && laatste.kaart.meta) ? laatste.kaart.meta : {};
  if (!meta.tijdzone_id || !wielMoment) { return ""; }
  try {
    const tekst = wielMoment.toLocaleString("nl-NL", { timeZone: meta.tijdzone_id, day: "2-digit",
      month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
    return " · plaatselijk " + tekst + " (" + meta.tijdzone_id + ")";
  } catch (e) { return ""; }
}

function wmToon() {
  const veld = document.getElementById("wielmoment");
  if (!veld) { return; }
  veld.hidden = !(wielStand === "transits" && laatste);
  if (!wielMoment) { return; }
  const waarden = [wmTwee(wielMoment.getUTCDate()), wmTwee(wielMoment.getUTCMonth() + 1),
                   String(wielMoment.getUTCFullYear()),
                   wmTwee(wielMoment.getUTCHours()), wmTwee(wielMoment.getUTCMinutes())];
  Array.from(veld.querySelectorAll(".wm-seg")).forEach((s) => {
    const i = Number(s.getAttribute("data-seg"));
    // Wat er getypt is, staat er zolang het nog niet compleet is: anders zie je bij het jaar drie
    // toetsaanslagen lang niets gebeuren.
    s.textContent = (i === wmSegment && wmBuffer) ? wmBuffer : waarden[i];
    s.classList.toggle("actief", i === wmSegment);
  });
  veld.title = "Moment van de transits, in UT" + wmLokaal() +
    " — pijltjes omhoog/omlaag hogen het gemarkeerde deel op";
}

function zetWielMoment() {
  const vak = document.getElementById("wielvak");
  if (!vak) { return; }
  let veld = document.getElementById("wielmoment");
  if (!veld) {
    veld = document.createElement("div");
    veld.id = "wielmoment";
    veld.className = "wielmoment";
    veld.tabIndex = 0;
    veld.setAttribute("role", "group");
    veld.setAttribute("aria-label", "Moment van de transits, in UT");
    veld.innerHTML =
      '<span class="wm-seg" data-seg="0"></span><span class="wm-streep">-</span>' +
      '<span class="wm-seg" data-seg="1"></span><span class="wm-streep">-</span>' +
      '<span class="wm-seg" data-seg="2"></span>' +
      '<span class="wm-seg wm-tijd" data-seg="3"></span><span class="wm-streep">:</span>' +
      '<span class="wm-seg" data-seg="4"></span><span class="wm-ut">UT</span>' +
      '<button type="button" class="wm-stap" data-stap="-1" aria-label="Een stap terug" ' +
        'title="Een stap terug met het gemarkeerde deel (pijltje omlaag)">\u2212</button>' +
      '<button type="button" class="wm-stap" data-stap="1" aria-label="Een stap verder" ' +
        'title="Een stap verder met het gemarkeerde deel (pijltje omhoog)">+</button>' +
      '<button type="button" class="wm-nu" title="Zet het moment op nu">nu</button>';
    veld.addEventListener("keydown", wmToets);
    veld.addEventListener("click", wmKlik);
    veld.addEventListener("blur", () => { wmBuffer = ""; });
    veld.querySelector(".wm-nu").addEventListener("click", (ev) => {
      ev.stopPropagation();
      wmNu();
      veld.focus();
    });
    Array.from(veld.querySelectorAll(".wm-stap")).forEach((knop) => {
      knop.addEventListener("click", (ev) => {
        ev.stopPropagation();
        wmBuffer = "";
        wmStap(Number(knop.getAttribute("data-stap")));
        // De knop geeft de beurt terug aan het veld, zodat muis en toetsenbord door elkaar te
        // gebruiken zijn: na een klik op + doet het pijltje meteen hetzelfde.
        veld.focus();
      });
    });
    vak.appendChild(veld);
  }
  wmToon();
}

// ---------------------------------------------------------------------------------------------
// De leeftijd van de progressiestand: twee veldjes (jaren, maanden) en **dezelfde** pijltjes als het
// momentveld - één stel knoppen voor beide standen, en ze raken het deel dat gemarkeerd is.
// ---------------------------------------------------------------------------------------------
function zetWielLeeftijd() {
  const vak = document.getElementById("wielvak");
  if (!vak) { return; }
  let veld = document.getElementById("wielleeftijd");
  if (!veld) {
    veld = document.createElement("div");
    veld.id = "wielleeftijd";
    veld.className = "wielmoment";       // dezelfde look als het momentveld, geen tweede stijl
    veld.tabIndex = 0;
    veld.setAttribute("role", "group");
    veld.setAttribute("aria-label", "Leeftijd voor de progressie, in jaren en maanden");
    veld.innerHTML =
      '<span class="wl-seg" data-seg="0"></span><span class="wl-eenheid">jaar</span>' +
      '<span class="wl-seg" data-seg="1"></span><span class="wl-eenheid">mnd</span>' +
      '<span class="wl-datum" id="wl-datum"></span>' +
      '<button type="button" class="wm-stap" data-stap="-1" aria-label="Een stap terug" ' +
        'title="Een stap terug met het gemarkeerde deel (pijltje omlaag)">\u2212</button>' +
      '<button type="button" class="wm-stap" data-stap="1" aria-label="Een stap verder" ' +
        'title="Een stap verder met het gemarkeerde deel (pijltje omhoog)">+</button>' +
      '<button type="button" class="wm-nu" title="Zet de leeftijd op vandaag">nu</button>';
    veld.addEventListener("keydown", wlToets);
    veld.addEventListener("click", wlKlik);
    veld.addEventListener("blur", () => { wlBuffer = ""; });
    veld.querySelector(".wm-nu").addEventListener("click", (ev) => {
      ev.stopPropagation();
      wlNu();
      veld.focus();
    });
    Array.from(veld.querySelectorAll(".wm-stap")).forEach((knop) => {
      knop.addEventListener("click", (ev) => {
        ev.stopPropagation();
        wlBuffer = "";
        wlStap(Number(knop.getAttribute("data-stap")));
        veld.focus();
      });
    });
    vak.appendChild(veld);
  }
  wlToon();
}

function wlWaarde() { return wlLeeftijd; }

// De twee veldjes uit de ene waarheid: afgerond op hele maanden, want dat is wat er staat. Een leeftijd
// van 63,30 jaar leest als "63 jaar 4 mnd" en de datum ernaast hoort bij 63,30 - niet bij 63,33.
function wlDelen() {
  const totaal = Math.round(wlLeeftijd * 12);
  const jaar = Math.floor(totaal / 12);
  return { jaar: jaar, maand: totaal - jaar * 12 };
}

function wlZet(leeftijd) {
  wlLeeftijd = Math.min(120, Math.max(0, Number(leeftijd) || 0));
}

function wlToon() {
  const veld = document.getElementById("wielleeftijd");
  if (!veld) { return; }
  veld.hidden = !(wielStand === "progressies" && laatste);
  if (veld.hidden) { return; }
  const delen = wlDelen();
  Array.from(veld.querySelectorAll(".wl-seg")).forEach((seg) => {
    const i = Number(seg.getAttribute("data-seg"));
    // Wat er getypt is, staat er zolang het nog niet is toegepast: anders zie je bij de jaren twee
    // toetsaanslagen lang niets gebeuren.
    if (i === 0) {
      seg.textContent = (wlSegment === 0 && wlBuffer) ? String(Number(wlBuffer)) : String(delen.jaar);
    } else {
      seg.textContent = (wlSegment === 1 && wlBuffer)
        ? wlBuffer : String(delen.maand).padStart(2, "0");
    }
    seg.classList.toggle("actief", i === wlSegment);
  });
  const datum = document.getElementById("wl-datum");
  if (datum) {
    datum.textContent = (wlLaatste && wlLaatste.datum) ? "\u2192 " + alsNederlands(wlLaatste.datum) : "";
    datum.title = "De kalenderdatum die bij deze leeftijd hoort";
  }
  veld.title = "Leeftijd voor de progressie" +
    (wlLaatste && wlLaatste.datum ? " (de kaart van " + alsNederlands(wlLaatste.datum) + ")" : "") +
    " \u2014 pijltjes omhoog/omlaag hogen het gemarkeerde deel op, links/rechts wisselt van deel";
}

// Er wordt op hele maanden afgerond voordat er
// gestapt wordt: anders sleep je de afronding mee en loopt het beeld na twaalf klikken een maand voor.
function wlStap(richting) {
  const totaal = Math.round(wlLeeftijd * 12) + richting * (wlSegment === 0 ? 12 : 1);
  wlLeeftijd = Math.min(120 * 12, Math.max(0, totaal)) / 12;
  wlGekozen = true;
  wlToon();
  wielTeken();
}

function wlNu() {
  wlBuffer = "";
  wlGekozen = false;        // de schil rekent de leeftijd van vandaag uit en die komt terug
  wielTeken();
}

function wlType(cijfer) {
  wlBuffer = (wlBuffer + cijfer).slice(-(wlSegment === 0 ? 3 : 2));
  const delen = wlDelen();
  if (wlSegment === 0) {
    wlLeeftijd = Math.min(120, Number(wlBuffer)) + delen.maand / 12;
  } else {
    wlLeeftijd = delen.jaar + Math.min(11, Number(wlBuffer)) / 12;
  }
  wlGekozen = true;
  wlToon();
  wielTeken();
}

function wlToets(ev) {
  const k = ev.key;
  if (k === "ArrowUp" || k === "ArrowDown") {
    ev.preventDefault(); wlBuffer = ""; wlStap(k === "ArrowUp" ? 1 : -1); return;
  }
  if (k === "ArrowLeft" || k === "ArrowRight" || k === "Tab") {
    ev.preventDefault(); wlBuffer = ""; wlSegment = wlSegment === 0 ? 1 : 0; wlToon(); return;
  }
  if (k === "Home") { ev.preventDefault(); wlSegment = 0; wlBuffer = ""; wlToon(); return; }
  if (k === "End") { ev.preventDefault(); wlSegment = 1; wlBuffer = ""; wlToon(); return; }
  if (/^[0-9]$/.test(k)) { ev.preventDefault(); wlType(k); return; }
  if (k === "Backspace" || k === "Delete") { ev.preventDefault(); wlBuffer = ""; wlToon(); }
}

function wlKlik(ev) {
  const seg = ev.target && ev.target.closest ? ev.target.closest(".wl-seg") : null;
  if (!seg) { return; }
  wlSegment = Number(seg.getAttribute("data-seg"));
  wlBuffer = "";
  wlToon();
  const veld = document.getElementById("wielleeftijd");
  if (veld) { veld.focus(); }
}

async function wielTeken() {
  const vak = document.getElementById("wielvak");
  if (!vak || !laatste) { return; }
  // De leesregel hoort bij wat er in het vak staat: bij een nieuwe tekening gaat hij leeg, anders blijft
  // de stand van een glyph staan die er niet meer is (een vervangen knoop stuurt geen `mouseout`).
  if (typeof zetLeesregel === "function") { zetLeesregel(""); }
  if (wielStand === "radix") {
    zetWielBeeld(laatste.svg);
    return;
  }
  const vracht = { kaart: laatste.kaart };
  let pad = "/api/transits/nu";
  if (wielStand === "transits") {
    if (wielMoment) { vracht.moment = wmIso(); }
  } else {
    pad = "/api/progressies/nu";
    // De leeftijd gaat mee zoals de twee veldjes hem dragen; is er nog niets gekozen, dan rekent de
    // schil de leeftijd van vandaag uit en komt die in het antwoord terug.
    if (wlGekozen) { vracht.leeftijd = wlWaarde(); }
  }
  const beurt = ++wmVerzoek;
  let antwoord = null;
  try {
    const r = await fetch(pad, { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(vracht) });
    if (r.ok) { antwoord = await r.json(); }
  } catch (e) {
    // Geen antwoord: dan blijft de radix staan en gaat de schakelaar terug.
  }
  if (beurt !== wmVerzoek) { return; }   // er is al een nieuwer verzoek onderweg: dit antwoord is oud
  if (!antwoord || !antwoord.svg) {
    wielStand = "radix"; zetWielSchakel(); zetWielBeeld(laatste.svg); return;
  }
  if (wielStand === "progressies") {
    wlLaatste = antwoord;
    if (!wlGekozen) { wlZet(antwoord.leeftijd); }   // de eerste tekening: de leeftijd van vandaag
    wlToon();
  }
  zetWielBeeld(antwoord.svg);
}
