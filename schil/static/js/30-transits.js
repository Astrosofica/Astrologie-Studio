// 30-transits.js
//
// De transits: het formulier, de momentopname, de lijst en de telling.
//
// Alle bestanden delen één werkruimte en worden in deze volgorde geladen; 90-start.js
// komt achteraan en gebruikt wat hierboven staat.


// --- Transits (T49) ---
// De eerste techniek met een eigen formulier: het tijdvak en de selectie zijn **invoer**, geen
// weergave, dus hier hoort een eigen Berekenen-knop (de regel "een vinkje dat pas na Berekenen werkt"
// geldt voor weergavekeuzes). De lijst toont momenten van **exactheid** — geen orb — met drie soorten
// regels: aspect, huis ingress en station. De momentopname ernaast is van nu en heeft geen invoer.
const TR_STANDAARD = ["Jupiter", "Saturnus", "Uranus", "Neptunus", "Pluto"];
// De aspecten die bij het openen **niet** aanstaan.
// Dit is dus de **begintoestand van de vakjes**, geen bewaarde instelling: wie ze aanzet, ziet ze in deze
// sessie aan, en na een nieuwe start staat het weer zoals hier. De lijst is een uitsluitlijst en geen
// aanlijst, zodat een aspect dat later in de techniek bijkomt niet stil buiten de default valt.
const TR_ASPECT_UIT = [60, 120];
// Standaardperiode per lichaam, gekalibreerd op ±150-200 regels per lichaam.
// Het is een **invulhulp, geen plafond**; het tijdvak blijft vrij instelbaar.
const TR_PERIODE = { "Maan": 1 / 12, "Zon": 1, "Mercurius": 1, "Venus": 1, "Mars": 2,
                     "Jupiter": 10, "Saturnus": 20, "Uranus": 30, "Neptunus": 30, "Pluto": 30 };
const TR_TEKENS = ["Ram", "Stier", "Tweelingen", "Kreeft", "Leeuw", "Maagd", "Weegschaal",
                   "Schorpioen", "Boogschutter", "Steenbok", "Waterman", "Vissen"];
// Het glyph én de naam van MC zijn dezelfde afkorting; zonder deze regel staat er "MC MC" in de lijst.
const TR_NAAM = { "MC": "Midhemel" };
// De grens op de lijst woont in de schil (GRENS_LIJST) en komt mee als `grens`: de pagina tekent wat
// ze krijgt en zegt hoeveel er zijn. Eén grens, één bron.
let trVorm = null;               // namen en tekens van de schil (/api/technieken -> vorm)
let trGebouwd = false;
let trBezig = false;

// Eén notatie voor een stand, net als de rest van het scherm: graad (twee cijfers), tekenglyph, minuut.
function trPos(lengte) {
  const d = standenDMS(lengte);
  const naam = TR_TEKENS[Math.floor((((lengte % 360) + 360) % 360) / 30) % 12];
  return "<span class='pos'><span class='dg'>" + String(d.g).padStart(2, "0") + "</span>" +
         "<span class='sg'>" + (GLYF_TEKEN[naam] || "") + "</span>" +
         "<span class='mn'>" + String(d.m).padStart(2, "0") + "</span></span>";
}

// Het moment van een doorgang is UT plus de zone van de kaart; de lijst toont de kloktijd (uu:mm).
function trMoment(ut, offset) {
  const d = new Date(Date.parse(ut) + (Number(offset) || 0) * 1000);
  const twee = n => String(n).padStart(2, "0");
  return { datum: twee(d.getUTCDate()) + "-" + twee(d.getUTCMonth() + 1) + "-" + d.getUTCFullYear(),
           tijd: twee(d.getUTCHours()) + ":" + twee(d.getUTCMinutes()) };
}

// Nederlands datumformaat in het veld (de lezer van de kern aanvaardt het, en het is wat hij typt).
function trDatumVeld(d) {
  const twee = n => String(n).padStart(2, "0");
  return twee(d.getDate()) + "-" + twee(d.getMonth() + 1) + "-" + d.getFullYear();
}

// ---------------------------------------------------------------------------------------------
// Het tijdvak in één klik.
//
// Twee dingen horen bij elkaar: **waar het jaar begint** (vandaag of 1 januari) en **hoeveel jaar** je
// wilt. De twee datumvelden blijven voor wie iets specifieks bekijkt; deze knoppen zijn er om niet na
// te denken. Daarom vullen ze niet alleen de velden maar rekenen ze ook meteen.
// ---------------------------------------------------------------------------------------------
const PERIODE_LENGTES = { transits: [1, 2, 3, 5], progressies: [1, 5, 10, 20] };

function periodeVul(vanId, totId, lengte, beginJanuari) {
  const nu = new Date();
  let van, tot;
  if (beginJanuari) {
    // Een kalenderjaar is 1 januari tot en met 31 december: "1 jaar" vanaf 1 januari is het jaar zelf,
    // niet 1 januari van het volgende jaar (dat is dezelfde dag nog een keer).
    van = new Date(nu.getFullYear(), 0, 1);
    tot = new Date(nu.getFullYear() + Number(lengte) - 1, 11, 31);
  } else {
    van = new Date(nu.getFullYear(), nu.getMonth(), nu.getDate());
    tot = new Date(van.getTime());
    tot.setFullYear(tot.getFullYear() + Number(lengte));
  }
  const v = document.getElementById(vanId), t = document.getElementById(totId);
  if (v) { v.value = trDatumVeld(van); }
  if (t) { t.value = trDatumVeld(tot); }
}

// De schakelaar **waar het tijdvak begint** staat op de regel van de lengteknoppen, ervoor: hij hoort
// bij die knoppen en nergens anders. Wat overblijft is de plek waar hij iets doet: direct links van "1 jaar".
//
// En hij **rekent niet**: hij zet alleen de stand waarin de lengteknoppen beginnen. Rekenen doen de
// lengteknoppen zelf.
function periodeStartRegel(prefix) {
  const knop = (waarde, tekst) =>
    "<button type='button' class='tr-startknop' data-" + prefix + "-start='" + waarde + "'>" +
    tekst + "</button>";
  return "<span class='tr-start' role='group' aria-label='Waar het tijdvak begint'>" +
      "<span class='tr-startlabel'>begin bij</span>" +
      knop("jaar", "1 januari") + knop("vandaag", "vandaag") +
    "</span>" +
    "<span class='tr-scheider' aria-hidden='true'></span>";
}

// De knoppen zelf: dezelfde vorm in beide technieken, want het is dezelfde vraag.
function periodeKnoppen(soort, prefix) {
  return PERIODE_LENGTES[soort].map(j =>
    "<button type='button' class='" + prefix + "-jaar' data-" + prefix + "-jaar='" + j + "'>" +
    j + " jaar</button>").join("");
}

function periodeKnoppenToon(prefix, actief) {
  Array.from(document.querySelectorAll("[data-" + prefix + "-jaar]")).forEach(b =>
    b.classList.toggle("aan", Number(b.getAttribute("data-" + prefix + "-jaar")) === actief));
}

function zetTransits(aan) {
  const balk = document.querySelector(".tabs");
  let knop = balk ? balk.querySelector("button[data-tab='transits']") : null;
  if (aan && balk && !knop) {
    knop = document.createElement("button");
    knop.dataset.tab = "transits";
    knop.textContent = "Transits";
    balk.appendChild(knop);
    knop.addEventListener("click", () => zetTab("transits"));
  } else if (!aan && knop) {
    const vak = document.getElementById("tab-transits");
    if (vak && vak.classList.contains("actief")) { zetTab("wiel"); }
    knop.remove();
    return;
  }
  if (aan) { bouwTransits(); }
  zetAfdrukAchteraan();
}

function trWaarden(soort) {
  return Array.from(document.querySelectorAll("[data-tr-" + soort + "]"))
    .filter(x => x.checked).map(x => x.getAttribute("data-tr-" + soort));
}

// De lijstindeling: waar de scheidingslijnen in de lijst komen. De standaardperioden-lijst staat
// hier niet: `trPeriodeInvullen()` vult het tijdvak wel, maar zwijgt erover.
function trScheidingRij() {
  const keuzes = [["geen", "geen"], ["dag", "per dag"], ["maand", "per maand"], ["jaar", "per jaar"]];
  return "<tr><th>Lijstindeling</th><td><div class='tr-rij2 tr-rij2-actie'>" +
    keuzes.map(k => "<label class='tr-optie'><input type='radio' name='tr-scheiding' value='" + k[0] +
      "'" + (trScheiding === k[0] ? " checked" : "") + "> " + k[1] + "</label>").join("") +
    // Achter de opties en niet aan de verre rand.
    "<button type='button' id='tr-bereken' class='hoofd tr-bereken-inrij'>Berekenen</button>" +
    "</div></td></tr>";
}

function bouwTransits() {
  const vak = document.getElementById("tab-transits");
  if (!vak || trGebouwd || !trVorm) { return; }
  trGebouwd = true;
  const L = trVorm.lichamen || [], A = trVorm.aspecten || [], H = trVorm.hoeken || [];
  const vakje = (soort, waarde, glyf, aan, titel) =>
    // Ook in de vakjes van het formulier krijgen Ascendant en MC de klasse `letters`: hun afkorting is
    // bij 15 px bijna 20 px breed en dan past het vinkje (13) + 4 px lucht + het teken niet meer in het
    // vakje van 34 px (gemeten 36,8). Als letters zijn ze 10 px en past het wel.
    "<label class='tr-vak' title='" + esc(titel) + "'><input type='checkbox' data-tr-" + soort +
    "='" + esc(waarde) + "'" + (aan ? " checked" : "") + "><span class='glyf" +
    (String(glyf).length > 1 ? " letters" : "") + "'>" + glyf + "</span></label>";
  // Dezelfde tabelvorm als de progressies: de kop van een groep is de rijKOP, en de twee schakelaars
  // staan op de rij zelf. Twee gelijke knoppen ("alles aan" en "alles uit") en geen vinkje dat een
  // toestand vasthoudt.
  const rij = (titel, soort, vakjes) =>
    "<tr><th>" + titel + "</th><td><div class='tr-rij2'>" +
      "<div class='tr-schakels'>" +
        "<button type='button' class='tr-schakel' data-tr-alle='" + soort + "'>alles aan</button>" +
        "<button type='button' class='tr-schakel' data-tr-geen='" + soort + "'>alles uit</button>" +
      "</div><div class='tr-vakken'>" + vakjes + "</div></div></td></tr>";

  const vandaag = new Date();
  const overEenJaar = new Date(vandaag.getTime());
  overEenJaar.setFullYear(overEenJaar.getFullYear() + 1);

  vak.innerHTML =
    // Twee standen in één tab: het formulier met de lijst is een eigen instrument,
    // en de standen van dit moment staan daar los van. De strip kost 22 px en geeft de lijst de volle breedte en hoogte terug.
    "<div class='tr-sub'>" +
      "<button type='button' data-tr-stand='nu' class='aan'>Huidige transits</button>" +
      "<button type='button' data-tr-stand='lijsten'>Transitlijsten</button>" +
      "<div class='tr-subvul'></div>" +
    "</div>" +
    "<div class='tr-stand' id='tr-stand-nu'>" +
      "<div class='paneel tr-nu' id='tr-nuvak'></div>" +
    "</div>" +
    "<div class='tr-stand weg' id='tr-stand-lijsten'>" +
    "<div class='paneel tr-formulier' id='tr-formulier'>" +
      "<div class='tr-samenvatting' id='tr-samenvatting' hidden>" +
        "<span id='tr-samenvatting-tekst'></span>" +
        "<button type='button' id='tr-wijzig'>wijzigen</button>" +
        // Dezelfde ingang als in het menu, maar dan waar je hem zoekt. Een streepje
        // ertussen, want 'wijzigen' hoort bij het formulier en 'afdrukken' bij het vel.
        "<span class='tr-scheider' aria-hidden='true'></span>" +
        "<button type='button' id='tr-afdrukken'>afdrukken</button>" +
      "</div>" +
      "<h2>Periode en selectie <span class='tr-bij'>de momenten waarop iets exact gebeurt</span></h2>" +
      // **Drie banden**, in de volgorde waarin je leest: wanneer · wat · hoe. Alles in één kolom van
      // 182 px zetten propt tijdvak, regelsoorten en de knop Berekenen door elkaar, en de
      // lijstindeling - een keuze over de **uitvoer** - bepaalt dan de hoogte van de hele rij.
      // Gemeten op 1097 x 617: 329 px tegen 235.
      // **A - de blokkenkaart**. Drie gelijke kolommen, elk blok in zijn eigen cel,
      // de kaart 800 px breed: dan valt Berekenen rechtsonder de **kaart** en niet rechtsonder het venster,
      // en is er geen cel die leeg blijft. Het tijdvak staat over de volle breedte, want het is de vraag
      // waar alles onder hangt.
      // **De B-variant, voor beide technieken**. Een labelkolom links en per onderwerp één rij; de rijkoppen doen wat de groeps koppen deden.
      "<table class='tr-tabel'>" +
        "<tr><th>Tijdvak</th><td>" +
          // De labels Van/Tot staan **naast** de velden en niet erboven (16 px lager, en even duidelijk):
          // een plaatshouder in het veld valt weg zodra er een datum in staat, en dan zie je niet meer
          // welke van de twee "van" is.
          "<div class='tr-regel'>" +
            "<label for='tr-van'>Van</label>" +
            "<input id='tr-van' value='" + trDatumVeld(vandaag) + "' placeholder='DD-MM-JJJJ'>" +
            "<label for='tr-tot'>Tot</label>" +
            "<input id='tr-tot' value='" + trDatumVeld(overEenJaar) + "' placeholder='DD-MM-JJJJ'>" +
          "</div>" +
          "<div class='tr-regel'>" + periodeStartRegel("tr") +
            periodeKnoppen("transits", "tr") +
          "</div>" +
        "</td></tr>" +
        rij("Transit", "lichaam", L.map(x => vakje("lichaam", x.naam, x.glyf,
             TR_STANDAARD.indexOf(x.naam) >= 0, x.naam)).join("")) +
        // De begintoestand van de aspecten: zeshoek en driehoek staan uit (zie TR_ASPECT_UIT).
        rij("Aspecten", "hoek", A.map(x => vakje("hoek", x.hoek, x.glyf,
             TR_ASPECT_UIT.indexOf(Number(x.hoek)) < 0, x.naam)).join("")) +
        rij("Radix", "doel", L.concat(H).map(x => vakje("doel", x.naam, x.glyf, true, x.naam)).join("")) +
                "<tr><th>Aanvullingen</th><td><div class='tr-rij2'>" +
          "<label class='tr-optie'><input type='checkbox' id='tr-ingress'> Huis ingress</label>" +
          "<label class='tr-optie'><input type='checkbox' id='tr-stations'> Stations</label>" +
        "</div></td></tr>" +
        trScheidingRij() +
      "</table>" +
    "</div>" +
    "<div class='tr-rij'>" +
      "<div class='paneel tr-lijst' id='tr-lijstvak'></div>" +
    "</div>" +
    "</div>";

  // De groepen: twee gelijke knoppen per groep - "alles aan" en "alles uit". Er is geen vinkje meer dat
  // de toestand van de groep vasthoudt: de vakjes zélf zijn de toestand, en dat is precies wat je ziet.
  Array.from(vak.querySelectorAll("[data-tr-alle]")).forEach(alle => {
    const soort = alle.getAttribute("data-tr-alle");
    alle.addEventListener("click", () => {
      Array.from(vak.querySelectorAll("[data-tr-" + soort + "]")).forEach(x => { x.checked = true; });
      trPeriodeInvullen();
    });
  });
  Array.from(vak.querySelectorAll("[data-tr-geen]")).forEach(geen => {
    const soort = geen.getAttribute("data-tr-geen");
    geen.addEventListener("click", () => {
      Array.from(vak.querySelectorAll("[data-tr-" + soort + "]")).forEach(x => { x.checked = false; });
      if (soort === "lichaam") { trPeriodeInvullen(); }
    });
  });
  Array.from(vak.querySelectorAll("[data-tr-lichaam], [data-tr-hoek], [data-tr-doel]")).forEach(x => {
    x.addEventListener("change", () => {
      if (x.hasAttribute("data-tr-lichaam")) { trPeriodeInvullen(); }
    });
  });

  Array.from(vak.querySelectorAll("input[name='tr-scheiding']")).forEach(r =>
    r.addEventListener("change", () => { trScheiding = r.value; if (trUit) { trToon(trUit); } }));

  // Het huidige kalenderjaar, niet het geboortejaar van de kaart - die
  // afspraak zit nu in `periodeVul(..., beginJanuari = true)`.
  Array.from(vak.querySelectorAll("[data-tr-jaar]")).forEach(b =>
    b.addEventListener("click", () => {
      trPeriodeStand = Number(b.getAttribute("data-tr-jaar"));
      // Alleen de datums, geen berekening: de gebruiker drukt altijd eerst op Berekenen.
      periodeVul("tr-van", "tr-tot", trPeriodeStand, trBeginJanuari());
      periodeKnoppenToon("tr", trPeriodeStand);
    }));
  Array.from(vak.querySelectorAll("[data-tr-start]")).forEach(b =>
    b.addEventListener("click", () => periodeStartKies("tr", b.getAttribute("data-tr-start"))));
  // Eén luisteraar op het vak: de standen van nu worden bij elke tik opnieuw neergezet, dus knoppen
  // in die tabel zouden hun luisteraar met de tekening verliezen.
  vak.addEventListener("click", (e) => {
    const b = e.target.closest("[data-tr-sorteer]");
    if (!b) { return; }
    const gekozen = b.getAttribute("data-tr-sorteer");
    if (gekozen === trSortering) { return; }
    trSortering = gekozen;
    if (trLaatsteNu) { trNuTeken(trLaatsteNu); }
  });
  document.getElementById("tr-bereken").addEventListener("click", berekenTransits);
  document.getElementById("tr-wijzig").addEventListener("click", () => trVouwUit(true));
  document.getElementById("tr-afdrukken").addEventListener("click", () => drukLijstAf());
  // De twee standen: de stand is de schakelaar, net als bij "Nu" in het hoofdscherm.
  Array.from(vak.querySelectorAll("[data-tr-stand]")).forEach(b =>
    b.addEventListener("click", () => trStand(b.getAttribute("data-tr-stand"))));
  trLijstKop();
  // De beginstand is het kalenderjaar: 1 januari van dit jaar, één jaar. Vult de keuze van één
  // enkel lichaam het tijdvak met zijn eigen lengte, dan is er geen lengte gekozen en dooft de knop.
  trPeriodeStand = 1;
  periodeVul("tr-van", "tr-tot", 1, trBeginJanuari());
  periodeKnoppenToon("tr", trPeriodeStand);
  periodeStartToon("tr", trStart);
  if (trPeriodeInvullen(true)) {
    trPeriodeStand = null;
    periodeKnoppenToon("tr", null);
  }
  trStand("nu");
  zetTransitsKnop();
}

// De standaardperiode is een invulhulp: staat er precies één lichaam aan, dan vult het tijdvak zich
// met de periode die bij dat lichaam hoort (±150-200 regels). Bij meer dan één lichaam blijft het
// tijdvak staan — één periode voor de hele lijst kan nu eenmaal niet bij elk lichaam passen.
function trPeriodeInvullen(begin) {
  const aan = trWaarden("lichaam");
  if (aan.length !== 1) { return false; }
  const jaren = TR_PERIODE[aan[0]];
  if (!jaren) { return false; }
  // Dezelfde schakelaar als de knoppen: begint het tijdvak op 1 januari, dan ook hier.
  const van = trBeginJanuari() ? new Date(new Date().getFullYear(), 0, 1) : new Date();
  const tot = new Date(van.getTime());
  tot.setTime(van.getTime() + jaren * 365.2425 * 86400000);
  const v = document.getElementById("tr-van"), t = document.getElementById("tr-tot");
  if (v) { v.value = trDatumVeld(van); }
  if (t) { t.value = trDatumVeld(tot); }
  return true;
}

function trLijstKop(tekst) {
  const vak = document.getElementById("tr-lijstvak");
  if (!vak) { return; }
  // "Exacte transits" is precies wat deze lijst onderscheidt
  // van een gewone transitlijst. De tab erboven heet al Transitlijsten, dus "Transits" alleen zou het
  // tabwoord herhalen en juist het onderscheidende woord weglaten.
  vak.innerHTML = "<h2>Exacte transits <span class='tr-bij' id='tr-telling'>" +
    esc(tekst || "nog niet berekend") + "</span></h2>" +
    "<div class='tr-grens' id='tr-grens' hidden></div>" +
    "<div class='tr-voortgang' id='tr-voortgang' hidden>" +
      "<div class='tr-balk'><div id='tr-balkvulling'></div></div>" +
      "<span class='tr-balktekst' id='tr-balktekst'></span></div>" +
    "<div class='tr-scroll' id='tr-scroll'></div>";
}

function trVoortgang(v) {
  const balk = document.getElementById("tr-voortgang");
  if (!balk) { return; }
  balk.hidden = false;
  document.getElementById("tr-balkvulling").style.width = v.procent + "%";
  document.getElementById("tr-balktekst").textContent =
    v.procent + "% · " + v.lichaam + " · " + trGetal(v.regels) + " transits";
}

async function berekenTransits() {
  if (trBezig) { return; }
  if (!laatste || !laatste.kaart) {
    zetMeld("let-op", ["Bereken eerst een horoscoop: de transits horen bij een radix."]);
    return;
  }
  const lichamen = trWaarden("lichaam");
  if (!lichamen.length) {
    zetMeld("let-op", ["Kies ten minste één transitplaneet."]);
    return;
  }
  const aspecten = trWaarden("hoek").map(Number);
  const doelen = trWaarden("doel");
  const ingress = document.getElementById("tr-ingress").checked;
  const stations = document.getElementById("tr-stations").checked;
  if (!aspecten.length && !doelen.length && !ingress && !stations) {
    zetMeld("let-op", ["Er valt niets te berekenen: kies aspecten of radixpunten, of zet huis ingress of stations aan."]);
    return;
  }
  const van = document.getElementById("tr-van").value;
  const tot = document.getElementById("tr-tot").value;

  trBezig = true;
  const knop = document.getElementById("tr-bereken");
  const oud = knop.textContent;
  knop.disabled = true;
  knop.textContent = "bezig…";
  trLijstKop("bezig…");
  // De balk verschijnt pas na 250 ms: een snelle lijst (0,2 s) hoort niet te flikkeren.
  let balkTimer = setTimeout(() => {
    const b = document.getElementById("tr-voortgang");
    if (b) { b.hidden = false; }
  }, 250);
  try {
    const ant = await fetch("/api/transits", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kaart: laatste.kaart, van: van, tot: tot, lichamen: lichamen,
                             aspecten: aspecten, doelen: doelen,
                             huis_ingress: ingress, stations: stations })
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
        if (j.voortgang) { trVoortgang(j.voortgang); }
        else if (j.fout) { throw new Error(j.fout); }
        else if (j.klaar) { klaar = j; }
      }
      // De laatste regel is het einde: niet wachten tot de verbinding sluit (die kan met keep-alive
      // open blijven, en dan hing de balk op 100%).
      if (klaar) { try { await lezer.cancel(); } catch (e) {} break; }
    }
    if (rest.trim()) {
      const j = JSON.parse(rest);
      if (j.fout) { throw new Error(j.fout); }
      if (j.klaar) { klaar = j; }
    }
    if (!klaar) { throw new Error("de berekening gaf geen uitkomst terug."); }
    // Eerst het meldblok leegmaken, dan tekenen. `trToon` zet zelf een wenk als één lichaam de
    // lijst laat overlopen, en die mag niet direct weer gewist worden.
    zetMeld("", []);
    trToon(klaar);
    trVouwIn();     // de lijst krijgt de hoogte die het formulier niet meer nodig heeft
  } catch (e) {
    zetMeld("let-op", ["De transits konden niet berekend worden: " + e.message]);
    const tel = document.getElementById("tr-telling");
    if (tel) { tel.textContent = "niet berekend"; }
  } finally {
    clearTimeout(balkTimer);
    trBezig = false;
    knop.disabled = false;
    knop.textContent = oud;
    const b = document.getElementById("tr-voortgang");
    if (b) { b.hidden = true; }
  }
}

function trToon(uit) {
  const rijen = uit.doorgangen || [];
  trUit = uit;            // voor de lijstindeling: opnieuw tekenen zonder opnieuw te rekenen
  const totaal = uit.totaal || rijen.length;
  const grens = uit.grens || totaal;
  const meldingen = [];
  const sn = uit["standen"] || [];
  const glyfAspect = {};
  if (trVorm) { (trVorm.aspecten || []).forEach(a => { glyfAspect[String(a.hoek)] = a.glyf; }); }

  // De momentopname is een eigen stand ("Huidige transits"), maar een berekening
  // werkt hem bij: de huizen komen uit dezelfde radix.
  trNuTeken(uit);

  // De lijst: drie soorten regels op één tijdlijn. De schil heeft hem al afgekapt op `grens`.
  //
  // De scheidingslijnen. Elke groep is een **eigen tbody**: dan begint de zebra
  // per groep opnieuw en is de scheidingsregel zelf nooit gestreept.
  const zichtbaar = rijen;
  const TR_MAAND = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
                    "september", "oktober", "november", "december"];
  // De datum in de lijst is "13 nov" en niet "13-11-2026". Voor de lijn "vandaag" is er de lange
  // vorm. Zie ook `trKorteDatum` in de titel van de cel, zodat de volle datum niet verdwijnt.
  const TR_MAAND_KORT = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];
  const trKorteDatum = d => {
    const [dg, mm] = d.split("-");
    return Number(dg) + " " + (TR_MAAND_KORT[Number(mm) - 1] || mm);
  };
  const sleutelVan = d => {
    const [dg, mm, jr] = d.split("-");
    return jr + "-" + String(mm).padStart(2, "0") + "-" + String(dg).padStart(2, "0");
  };
  const nu = new Date();
  const vandaagSleutel = nu.getFullYear() + "-" + String(nu.getMonth() + 1).padStart(2, "0") + "-" +
    String(nu.getDate()).padStart(2, "0");
  // Het tijdvak komt uit de twee datums van het formulier: die bepalen de lijst, ook als de eerste
  // doorgang pas weken later valt. Zonder die velden (theoretisch) valt hij terug op de lijst zelf.
  const vanVeld = document.getElementById("tr-van"), totVeld = document.getElementById("tr-tot");
  const eersteSleutel = zichtbaar.length
    ? sleutelVan(trMoment(zichtbaar[0].ut, zichtbaar[0].offset_sec).datum) : "";
  const laatsteSleutel = zichtbaar.length
    ? sleutelVan(trMoment(zichtbaar[zichtbaar.length - 1].ut,
                          zichtbaar[zichtbaar.length - 1].offset_sec).datum) : "";
  const vanSleutel = (vanVeld && vanVeld.value) ? sleutelVan(vanVeld.value) : eersteSleutel;
  const totSleutel = (totVeld && totVeld.value) ? sleutelVan(totVeld.value) : laatsteSleutel;
  const vandaagTekst = "vandaag · " + nu.getDate() + " " + TR_MAAND[nu.getMonth()] + " " +
    nu.getFullYear();
  const binnenTijdvak = !!zichtbaar.length && vandaagSleutel >= vanSleutel &&
    vandaagSleutel <= totSleutel;
  let vandaagGeweest = false;
  const verledenInLijst = vanSleutel < vandaagSleutel;
  const groepVan = datum => {
    const [dg, mm, jr] = datum.split("-");
    const maand = TR_MAAND[Number(mm) - 1] || mm;
    if (trScheiding === "jaar") { return { sleutel: jr, naam: jr }; }
    if (trScheiding === "maand") { return { sleutel: jr + "-" + mm, naam: maand + " " + jr }; }
    return { sleutel: datum, naam: Number(dg) + " " + maand + " " + jr };
  };
  const groepen = [];                  // [{naam, rijen: [html]}]
  // De zebra telt **alleen gegevensrijen**. De groepskop en de lijn "vandaag" staan ook in
  // de tbody, en met `nth-child(even)` telden die mee: in een groep mét "vandaag" viel de eerste regel
  // daardoor op wit waar een groep zonder die regel op grijs begon. De telling begint per groep opnieuw,
  // maar de kop en de vandaag-regel doen niet mee.
  let zebra = 0;
  if (trScheiding === "geen") { groepen.push({ naam: "", rijen: [] }); }
  let vorigeSleutel = null;
  zichtbaar.forEach(e => {
    const m = trMoment(e.ut, e.offset_sec);
    if (trScheiding !== "geen") {
      const g = groepVan(m.datum);
      if (g.sleutel !== vorigeSleutel) {
        vorigeSleutel = g.sleutel;
        groepen.push({ naam: g.naam, rijen: [] });
        zebra = 0;
      }
    }
    // Het aspect staat er als glyph én als woord, want cursisten moeten de tekens kennen en herkennen.
    // Wat er in één regel staat: het moment, **waar de transitplaneet staat** (`punt_lengte`,
    // met ℞ als hij terugloopt), het aspect **als glyph én als woord**, het radixpunt met zijn eigen graad
    // (`doel_lengte`) en het huis waarin dat punt staat. Er is geen kolom "Stand" of "R": de stand
    // hoort bij het punt waar hij bij hoort, en de richting is één teken achter de planeet -
    // dezelfde notatie als in het wiel.
    let asp, radix;
    // **Vaste segmenten**: [glyph][℞][graad] en [glyph][naam][graad]. Het ℞-vak is
    // er ook als er geen ℞ staat, en de graad van het radixpunt staat in een vak van vaste breedte -
    // daardoor begint (transit) en eindigt (radix) elk getal op dezelfde plek, ook als de ene planeet
    // terugloopt, de andere niet, of de naam van het radixpunt lang is. Zonder die vakken schuift de
    // graad per regel op, en dat leest onrustig.
    const seg = (klasse, delen) => "<span class='seg " + klasse + "'>" + delen.join("") + "</span>";
    const leegvak = "<span></span>";
    // **Het huis hoort bij de transitplaneet** en staat daarom achter hem, in een eigen smal vakje
    // zodat "H9" niet als graad leest. Bij een huis-ingress staat het huis al in de zin ernaast, dus
    // daar niet nog eens - en bij een **station** ook niet: daar staat in de radixkolom "gaat
    // retrograde/direct" en een huis erbij maakt van twee soorten regels één pot nat. De station-tak
    // zet daarom geen `huis`: `huis` is een `const`, en een toewijzing eraan laat elke lijst met
    // stations omvallen ("Assignment to constant variable").
    const huis = (e.soort === "huis_ingress" || e.soort === "station" ||
                  e.huis === undefined || e.huis === null || e.huis === "")
      ? leegvak
      : "<span class='pr-huis' title='de transitplaneet staat in radixhuis " + esc(String(e.huis)) +
        "'>H" + esc(String(e.huis)) + "</span>";
    const transit = seg("seg-transit", [
      glyfVan(e.lichaam),
      e.richting === "R" ? "<span class='retro'>\u211e</span>" : leegvak,
      trPos(e.punt_lengte),
      huis]);
    if (e.soort === "station") {
      asp = "<span class='naam'>stationair</span>";
      radix = seg("seg-radix", [leegvak,
        "<span class='naam'>" + (e.richting === "R" ? "gaat retrograde" : "gaat direct") + "</span>",
        leegvak]);
    } else if (e.soort === "huis_ingress") {
      // Het huis dat je **binnenkomt**, niet de cusp die je kruist. Bij een
      // retrograde doorgang is dat het vorige huis — een commercieel programma schrijft het zo, en een
      // cursist hoeft dan
      // de richting niet zelf om te rekenen. De kern rekent het uit (`huis`): welke richting je in
      // welk huis brengt is vakinhoud, geen weergave.
      const naar = (e.huis === undefined || e.huis === null) ? null : e.huis;
      // "gaat naar" hoort bij het werkwoord in de aspectkolom en "huis 5" is het doel; met "in" erachter
      // las de rij als twee zinnen die door de kolomgrens heen aan elkaar geplakt waren.
      asp = "<span class='naam'>gaat naar</span>";
      radix = seg("seg-radix", [leegvak,
        "<span class='naam'>" + (naar === null ? "over " + esc(e.doel) : "huis " + naar) + "</span>",
        leegvak]);
    } else {
      asp = "<span class='glyf'>" + (glyfAspect[String(e.hoek)] || "") + "</span><span class='naam'>" +
        esc(String(e.aspect || "").toLowerCase()) + "</span>";
      radix = seg("seg-radix", [glyfVan(e.doel),
        "<span class='naam'>" + esc(TR_NAAM[e.doel] || e.doel) + "</span>",
        trPos(e.doel_lengte)]);
    }
    // De lijn "vandaag": alleen als het tijdvak vandaag omsluit, anders is hij een raadsel.
    // De lijn "vandaag" alleen als er **verleden** in de lijst staat. Hij markeert de grens tussen wat
    // geweest is en wat komt; begint het tijdvak vandaag - de standaard - dan staat er niets boven
    // en is het een streep zonder betekenis. Dan blijft hij weg.
    if (verledenInLijst && !vandaagGeweest && binnenTijdvak && sleutelVan(m.datum) >= vandaagSleutel) {
      vandaagGeweest = true;
      groepen[groepen.length - 1].rijen.push(
        "<tr class='vandaagrij'><td colspan='6'>" + vandaagTekst + "</td></tr>");
    }
    groepen[groepen.length - 1].rijen.push(
      "<tr" + ((zebra++ % 2) ? " class='rij-b'" : "") + "><td title='" + m.datum + "'>" +
      trKorteDatum(m.datum) + "</td><td>" + m.tijd + "</td><td>" +
      transit + "</td><td class='aspvak'>" + asp + "</td><td>" + radix +
      "</td><td class='leeg'></td></tr>");
  });
  // De eerste regel van de thead is de **kop van het vel** en staat alleen op papier (zie de CSS:
  // `tr.drukkop` is op het scherm verborgen). Hij staat in de thead en niet boven de tabel, omdat de
  // browser een thead op elke pagina herhaalt - dan weet je ook op pagina 3 nog van wie deze lijst is
  // en met welke invoer hij gemaakt is.
  let h = "<table class='lijst'><thead>" +
          "<tr class='drukkop'><td colspan='6'>" + trDrukKop() + "</td></tr>" +
          "<tr><th>Datum</th><th>Tijd</th><th>Transit</th><th>Aspect</th>" +
          "<th>Radix</th><th></th></tr></thead>";
  groepen.forEach(g => {
    h += "<tbody>";
    if (g.naam) {
      h += "<tr class='scheidingsrij'><td colspan='6'>" + esc(g.naam) + "</td></tr>";
    }
    h += g.rijen.join("") + "</tbody>";
  });
  h += "</table>";

  // Het woord bij de telling volgt de inhoud. Standaard staan huis-ingressen en stations uit,
  // en dan bestaat de lijst volledig uit aspecten - dan heet het ook zo. Zet je die twee aan, dan
  // zijn het echt geen aspecten meer en blijft het "momenten": één scherm hoort niet te liegen
  // over wat er in de lijst staat.
  const eenheid = (zichtbaar.length && zichtbaar.every(e => e.soort === "aspect")) ? "aspecten" : "momenten";
  let telling = trGetal(totaal) + " " + eenheid;
  let grensTekst = "";
  if (uit.afgekapt && zichtbaar.length) {
    const laatste = trMoment(zichtbaar[zichtbaar.length - 1].ut, zichtbaar[zichtbaar.length - 1].offset_sec);
    telling = trGetal(zichtbaar.length) + " van " + trGetal(totaal) + " " + eenheid +
      " · de lijst stopt bij " + laatste.datum;
    // De grens staat **boven** de lijst en zegt het in gewone taal: het aantal
    // kantjes is het argument, niet het jargon van doelen en aspecten.
    grensTekst = "De lijst stopt bij " + trGetal(grens) + " van de " + trGetal(totaal) + " " + eenheid +
      " — dat zijn er al ±" + Math.round(grens / TR_REGELS_VEL) + " kantjes. Neem een korter " +
      "tijdvak, of kies minder transitplaneten.";
  }
  const kop = document.querySelector("#tr-lijstvak h2");
  const tel = document.getElementById("tr-telling");
  if (tel) { tel.textContent = telling; }
  if (kop && !tel) { kop.innerHTML = "Exacte transits <span class='tr-bij'>" + esc(telling) + "</span>"; }
  document.getElementById("tr-scroll").innerHTML = h;

  // Eén lichaam dat de lijst laat overlopen, met naam erbij: geen stille beperking, wel een wenk.
  // De telling komt uit de schil en gaat over de **hele** lijst, niet over het zichtbare deel. Alleen
  // de grootste wordt genoemd: twee namen in één zin leest als een opsomming van fouten.
  const perLichaam = uit.per_lichaam || {};
  const drukte = Object.keys(perLichaam).filter(n => perLichaam[n] > 2000)
    .sort((a, b) => perLichaam[b] - perLichaam[a]);
  if (drukte.length) {
    grensTekst += " De " + drukte[0] + " alleen al geeft " + trGetal(perLichaam[drukte[0]]) +
      " regels; zet die uit als je de rest wilt zien.";
  }
  // De wenk staat boven de lijst en niet in het meldblok: één plek, en op de plek waar je hem leest.
  const grensvak = document.getElementById("tr-grens");
  if (grensvak) { grensvak.textContent = grensTekst; grensvak.hidden = !grensTekst; }
  if (uit.let_op) { meldingen.push(uit.let_op); }
  zetMeld(meldingen.length ? "let-op" : "", meldingen);
}

// --- de twee standen van de Transits-tab ---------------------------------------------------------
// Het formulier met de lijst staat los van de standen van nu: een strip van 22 px binnen de tab,
// met de standen van dit moment vooraan - die zijn ook de basis van het latere bi-wheel.
// Eén keer per minuut. In twintig seconden schuift de Maan 0,55' en de Zon 0,035', en deze kolommen
// tonen hele minuten: vaker verversen levert geen zichtbaar ander beeld op. De tik valt op de :00 van
// de klok, zodat de kop niet "37 seconden na de laatste tik" zegt.
const TR_TIK_MS = 60000;
const TR_REGELS_VEL = 45;     // regels op één A4 in de opmaak van dit programma (gemeten)
let trStandNu = true;         // staat "Huidige transits" vooraan?
let trTikTimer = null;
let trLijstSleutel = "";      // bij welke radix de lijst hoort
let trScheiding = "maand";    // waar de scheidingslijnen in de lijst komen: geen | dag | maand | jaar
let trPeriodeStand = null;    // de gekozen lengte in jaren (null zolang er zelf datums staan)
let trStart = "jaar";         // "jaar" = 1 januari van dit jaar, "vandaag" = vanaf vandaag
let trSortering = "planeet";  // volgorde van de standen van nu: planeet | volgend
let trLaatsteNu = null;       // de laatste standen, zodat de volgorde wisselt zonder verzoek
function trBeginJanuari() { return trStart === "jaar"; }

// De twee standen van de kopregel: één knop licht op, en de andere doet hetzelfde werk andersom.
function periodeStartToon(prefix, waarde) {
  Array.from(document.querySelectorAll("[data-" + prefix + "-start]")).forEach(b =>
    b.classList.toggle("aan", b.getAttribute("data-" + prefix + "-start") === waarde));
}

// Alleen de stand zetten. Geen berekening en ook de datumvelden niet: die horen bij de lijst die er
// staat, en de volgende klik op een lengte zet ze op de nieuwe beginstand.
function periodeStartKies(prefix, waarde) {
  if (prefix === "tr") { trStart = waarde; } else { prStart = waarde; }
  periodeStartToon(prefix, waarde);
}
let trUit = null;             // de laatste berekening, zodat de indeling wisselt zonder herrekenen

// De techniek bestaat alleen mét radix. Toont het scherm de horoscoop van dit moment, dan valt elk
// lichaam samen met zichzelf en valt er niets te transitieren; dan is de tab uitgegrijsd in plaats
// van gevuld met onzin.
function trMag() {
  // De techniek "transits" hoort bij jaar 2 (T48/T50) en jaar 3 bouwt erop voort;
  // staat die module uit (jaar 1), dan bestaat de tab niet en hoort deze standkeuze er ook niet te zijn.
  // De bron is hetzelfde profiel als de tabbalk, dus er kan niets uit elkaar lopen.
  return !!(laatste && laatste.kaart) && !klokStand() && techniekAan("transits");
}

function zetTransitsKnop() {
  const knop = document.querySelector(".tabs button[data-tab='transits']");
  if (!knop) { return; }
  const mag = trMag();
  knop.classList.toggle("uit", !mag);
  knop.disabled = !mag;
  knop.title = mag ? "" : "De transits horen bij een berekende horoscoop";
}

function trStand(naam) {
  const vak = document.getElementById("tab-transits");
  if (!vak) { return; }
  trStandNu = (naam !== "lijsten");
  Array.from(vak.querySelectorAll("[data-tr-stand]")).forEach(b =>
    b.classList.toggle("aan", (b.getAttribute("data-tr-stand") === "nu") === trStandNu));
  const nu = document.getElementById("tr-stand-nu"), lij = document.getElementById("tr-stand-lijsten");
  if (nu) { nu.classList.toggle("weg", !trStandNu); }
  if (lij) { lij.classList.toggle("weg", trStandNu); }
  if (trStandNu) { trNu(); }
  trKlok();
}

// De tik: alleen terwijl deze stand zichtbaar is én de tab actief is. De stand is de schakelaar,
// net als bij "Nu" in het hoofdscherm.
function trKlok() {
  if (trTikTimer !== null) { clearTimeout(trTikTimer); trTikTimer = null; }
  const tab = document.getElementById("tab-transits");
  if (!trStandNu || !tab || !tab.classList.contains("actief") || !trMag()) { return; }
  trTikTimer = setTimeout(trTik, TR_TIK_MS - (Date.now() % TR_TIK_MS) + 40);
}

async function trTik() {
  trTikTimer = null;
  await trNu();
  trKlok();
}

async function trNu() {
  if (!trMag()) { return; }
  try {
    const r = await fetch("/api/transits/nu", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kaart: laatste.kaart }) });
    if (!r.ok) { return; }
    trNuTeken(await r.json());
  } catch (e) {
    // Een gemiste tik is geen storing: de volgende komt over twintig seconden.
  }
}

// Eerst het volgende aspect per lichaam. Het wiel zelf staat op
// het hoofd wiel: de schakelaar daar zet dezelfde radix met de transits in de buitenring.
//
// Zeven kolommen, elk met een eigen vaste breedte: aspect en radixpunt zijn **twee** kolommen en niet
// één. De breedtes komen van de gemeten tekst op 13 px: "Noordknoop" 74, "anderhalfvierkant" 100,
// "14-02-2030 06:53" 101 px, plus 16 px celrand. De lege sluitkolom vangt de rest van de breedte - dezelfde regel als in de lijst,
// want zonder die kolom rekt de laatste kolom mee en dan danst hij op een breed scherm.
function trNuTeken(uit) {
  const vak = document.getElementById("tr-nuvak");
  if (!vak) { return; }
  const sn = uit["standen"] || [];
  const volgend = uit["volgend"] || {};
  const jaren = uit["volgend_horizon_jaren"] || 5;
  const glyfAspect = {};
  if (trVorm) { (trVorm.aspecten || []).forEach(a => { glyfAspect[String(a.hoek)] = a.glyf; }); }
  let nu = "<h2 class='met-sorteer'>Standen van nu <span class='tr-bij'>" + esc((uit.nu || {}).tijd || "") +
    "</span>" + trSorteerKeuze() + "</h2>" +
    // De **vulkolom** tussen "Huis" en het blok met het eerstvolgende aspect.
    // Het is de enige kolom zonder vaste breedte: hij krijgt wat er overblijft tot de tabel zijn
    // `max-width` raakt, en krimpt als eerste zodra het paneel smaller wordt. Een lege sluitkolom aan
    // het eind van de regel is er niet: daar leest hij als een gat.
    "<table class='lijst'><thead><tr><th>Planeet</th><th>Stand</th><th>R</th><th class='r'>Huis</th>" +
    "<th class='vul'></th><th>Eerstvolgend aspect</th><th>Radixpunt</th><th class='r'>Wanneer</th>" +
    "</tr></thead><tbody>";
  // Op "Eerstvolgend aspect" staat de rij waarvan het volgende aspect het eerst komt bovenaan. Een rij
  // zonder eerstvolgend aspect (binnen de horizon, of de Noordknoop) zakt naar onderen, en bij
  // gelijke datums blijft de planeetvolgorde staan - de sortering is stabiel.
  const rijen = sn.slice();
  if (trSortering === "volgend") {
    rijen.sort((a, b) => {
      const ua = (volgend[a.naam] || {}).ut, ub = (volgend[b.naam] || {}).ut;
      if (ua && ub) { return ua < ub ? -1 : (ua > ub ? 1 : 0); }
      return ua ? -1 : (ub ? 1 : 0);
    });
  }
  rijen.forEach(x => {
    const v = volgend[x.naam] || null;
    // De knoop is een stand en geen aspectdoel (T49): die rij houdt het streepje, en de titel zegt
    // waarom - anders lijkt het of de berekening hem vergeten is.
    let asp = "<td class='leegvak' title='de Noordknoop doet niet mee aan aspecten'>—</td>";
    let punt = "<td></td>";
    let wanneer = "<td class='leegvak'>—</td>";
    if (v) {
      const m = trMoment(v.ut, v.offset_sec);
      asp = "<td class='aspvak'><span class='glyf'>" + (glyfAspect[String(v.hoek)] || "") + "</span>" +
            "<span class='naam'>" + esc(v.aspect || "") + "</span></td>";
      punt = "<td class='puntvak'>" + glyfNaam(v.doel, v.doel) + "</td>";
      // Altijd met het jaar. De lijst laat het jaar weg omdat de scheidingsband het noemt;
      // hier is er geen band.
      wanneer = "<td class='r'>" + m.datum + " " + m.tijd + "</td>";
    } else if (x.naam !== "Noordknoop") {
      asp = "<td class='leegvak' title='geen exact aspect binnen " + jaren + " jaar'>—</td>";
      wanneer = "<td class='leegvak'>—</td>";
    }
    nu += "<tr><td>" + glyfNaam(x.naam, x.naam) + "</td><td>" +
      trPos(x.lengte) + "</td><td class='scheidend'>" + x.richting + "</td><td class='r'>" + x.huis +
      "</td><td class='vul'></td>" + asp + punt + wanneer + "</tr>";
  });
  nu += "</tbody></table>";
  trLaatsteNu = uit;
  vak.innerHTML = nu;
}

// De volgorde van de tabel: op planeet (de volgorde van de berekening) of op de datum van het
// eerstvolgende aspect. Zonder die keuze antwoordt elke rij wel wat er komt, maar niet wat het eerst
// komt - en dat is de vraag waarmee je naar deze tabel kijkt.
function trSorteerKeuze() {
  const knop = (waarde, tekst) => "<button type='button' class='tr-startknop" +
    (trSortering === waarde ? " aan" : "") + "' data-tr-sorteer='" + waarde + "'>" + tekst + "</button>";
  return "<span class='sorteer'><span class='sorteerlabel'>Sorteren op</span>" +
    knop("planeet", "Planeet") + knop("volgend", "Eerstvolgend aspect") + "</span>";
}

// De lijst hoort bij een radix (besluit T49): hij blijft staan als je van stand wisselt
// en is leeg zodra de getoonde horoscoop een andere is. De sleutel gaat over de **gegevens** en niet
// over het kaart-id, want de klok van "Nu" maakt bij elke tik een nieuwe kaart met een nieuw id.
function trKaartSleutel() {
  const m = (laatste && laatste.kaart && laatste.kaart.meta) || null;
  return m ? [m.naam, m.datum, m.tijd, m.lat, m.lon].join("|") : "";
}

function trActualiseer() {
  zetTransitsKnop();
  zetProgressiesKnop();     // dezelfde grendel, dezelfde gebeurtenis (6 nov 2026)
  const sleutel = trKaartSleutel();
  if (sleutel !== trLijstSleutel) {
    trLijstSleutel = sleutel;
    trLijstKop();          // de lijst hoort bij de vorige radix en gaat weg
    trVouwUit(false);      // en het formulier komt terug: de invoer is weer aan de orde
  }
  if (trStandNu) { trNu(); }
  trKlok();
}

// Het formulier in- en uitklappen. Ingeklapt staat er één regel met de invoer waar de lijst bij
// hoort, met "wijzigen" ernaast; dat is dezelfde gedachte als de kop van de lijst die het tijdvak
// noemt.
// De invoer in één regel, zoals de gebruiker hem in het formulier ziet. Twee plekken gebruiken hem - 
// de ingeklapte strook op het scherm en de kop van het afgedrukte vel - en ze mogen nooit uit elkaar lopen.
// Het tijdvak zoals de gebruiker het invulde, of in lange vorm voor papier: "van 3 november 2026 
// tot 3 november 2027". Op een vel dat later uit een map komt, is "03-11-2026" te makkelijk te lezen 
// als 11 maart.
function trPeriodeTekst(lang) {
  const van = document.getElementById("tr-van").value;
  const tot = document.getElementById("tr-tot").value;
  if (!lang) { return van + " t/m " + tot; }
  const mooi = (s) => {
    const m = /^(\d{1,2})-(\d{1,2})-(\d{4})$/.exec(String(s).trim());
    if (!m) { return s; }
    return new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]))
      .toLocaleDateString("nl-NL", { day: "numeric", month: "long", year: "numeric" });
  };
  return "van " + mooi(van) + " tot " + mooi(tot);
}

function trInvoerTekst(lang) {
  const aantal = (soort, enkel, meer) => {
    const n = trWaarden(soort).length;
    return n + " " + (n === 1 ? enkel : meer);
  };
  const extra = [];
  if (document.getElementById("tr-ingress").checked) { extra.push("huis ingress"); }
  if (document.getElementById("tr-stations").checked) { extra.push("stations"); }
  // De samenvatting heet de dingen zoals de gebruiker ze in het formulier ziet: de
  // groepen heten "Transit" en "Radix", dus "transitplaneten" en "radixpunten" - niet "lichamen" en
  // "doelen". "Punten" en niet "planeten" omdat de radixkant ook Asc, MC, knoop en Chiron bevat.
  return trPeriodeTekst(lang) +
    " · " + aantal("lichaam", "transitplaneet", "transitplaneten") + " · " +
    aantal("hoek", "aspect", "aspecten") + " · " +
    aantal("doel", "radixpunt", "radixpunten") + (extra.length ? " · " + extra.join(" · ") : "");
}

function trVouwIn() {
  const f = document.getElementById("tr-formulier"), s = document.getElementById("tr-samenvatting");
  if (!f || !s) { return; }
  document.getElementById("tr-samenvatting-tekst").textContent = trInvoerTekst();
  f.classList.add("ingeklapt");
  s.hidden = false;
}

function trVouwUit(zetFocus) {
  const f = document.getElementById("tr-formulier"), s = document.getElementById("tr-samenvatting");
  if (!f || !s) { return; }
  f.classList.remove("ingeklapt");
  s.hidden = true;
  if (zetFocus) {
    const van = document.getElementById("tr-van");
    if (van) { van.focus(); }
  }
}
