// 10-invoer.js
//
// Het formulier: keuring, de plaatszoeker, het uitlegvak, de instellingen en de solaar.
//
// Alle bestanden delen één werkruimte en worden in deze volgorde geladen; 90-start.js
// komt achteraan en gebruikt wat hierboven staat.


async function laadProfiel() {
  // De aangevinkte cursusjaren (T48). Jaar 1 is het fundament en staat altijd aan; jaar 2
  // komt erbij als de gebruiker de module aanvinkt. De schil voegt de technieken van die jaren samen en
  // stuurt ze hierheen - de pagina kent geen eigen lijst met technieken.
  try {
    const j = await (await fetch("/api/technieken")).json();
    const p = j.profiel || {};
    profiel.jaren = (p.jaren && p.jaren.length) ? p.jaren.map(Number) : [Number(p.jaar) || 1];
    profiel.jaar = Math.max(...profiel.jaren);
    profiel.naam = p.naam || "";
    profiel.technieken = new Set((j.technieken || []).filter(t => t.aan !== false).map(t => t.id));
    // De namen en tekens waarmee de transits hun keuzes tonen (één bron: de schil, die ze uit
    // kern/formaat.py haalt - geen tweede tekentabel in de pagina).
    trVorm = j.vorm || null;
    // De standaardweergave van een techniek: staat Chiron in een aangevinkte module met
    // `standaard_zichtbaar`, dan begint het vinkje aan. Wie het daarna uitzet houdt het uit tot het
    // profiel opnieuw geladen wordt (bijvoorbeeld na het aanzetten van een module).
    const chiron = (j.technieken || []).find(t => t.id === "chiron");
    const vak = document.getElementById("toon-chiron");
    if (chiron && chiron.standaard_zichtbaar && vak) { vak.checked = true; }
  } catch (e) {
    // Geen profiel: dan blijft de jaar-1-stand staan (geen Chiron-vinkje, geen dominantmarkering).
  }
  // De cursusjaren staan op twee plekken: rechts in de menubalk en in de statusbalk. Ze horen hetzelfde
  // te zeggen, dus zet ze hier allebei - één bron (`profiel.jaren`), twee plekken.
  const jaarTekst = profiel.jaren.length === 1
    ? "cursusjaar " + profiel.jaren[0]
    : "cursusjaren " + profiel.jaren.join(" en ");
  ["kop-sub", "status-jaar"].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.textContent = jaarTekst; }
  });
  zetTitel(profiel.jaar);
  const mc = document.getElementById("menu-chiron");
  if (mc) { mc.classList.toggle("weg", !techniekAan("chiron")); }
  const ms = document.getElementById("menu-solaar");
  if (ms) { ms.classList.toggle("weg", !techniekAan("solaar")); }
  zetSolaarMenu();
  // De vijfde tab komt uit het register: staat de techniek niet in een aangevinkte module, dan is er
  // geen knop en geen vak (dan is jaar 1 ook letterlijk ongewijzigd).
  zetTransits(techniekAan("transits"));
  zetProgressies(techniekAan("progressies"));
  zetVinkjes();
}

// --- Een veld laat de standaardvorm zien zodra het te lezen is (standaardvorm) --------------------
// Verlaat je het datum- of tijdveld, dan vraagt de pagina de kern wat hij ervan maakt en schrijft
// dat stil terug: 19.7.1963 wordt 19-07-1963, 9u30 wordt 09:30:00. Zo staat er in het formulier
// dezelfde notatie als in het gegevensblok, de horoscopenlijst en op de A4 (één tijd, één vorm).
//
// De regel is bewust asymmetrisch: een lege of nog niet te lezen waarde laat alles zoals het is -
// geen markering, geen melding, geen herschrijving. Wie van datum naar tijd tabt terwijl de datum
// nog half ingevuld is, hoort geen aanmaning te krijgen; de keuring hoort bij Berekenen.
//
// De lezer staat in de kern (`kern/invoer.py`, route `/api/invoer`) en niet hier: een tweede set
// regels in de pagina loopt gegarandeerd uit de pas met de echte. De vraag kost ± 1 ms.
const KEURVELDEN = ["datum", "tijd"];

async function keurVeld(id) {
  const veld = document.getElementById(id);
  const waarde = veld.value.trim();
  if (!waarde) { return; }
  try {
    const r = await fetch("/api/invoer", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ [id]: waarde }) });
    if (!r.ok) { return; }
    const j = await r.json();
    // Alleen als het veld intussen niet veranderd is: wie verder typt terwijl het antwoord nog
    // onderweg is, houdt zijn eigen tekst.
    if (!j[id] || veld.value.trim() !== waarde) { return; }
    if (j[id] !== waarde) { veld.value = j[id]; }
    // Een eerder afgekeurd veld is nu leesbaar: dat spoor mag weg. Zolang er nog een veld
    // gemarkeerd staat blijft de melding staan; is dit het laatste, dan valt het blok leeg.
    veld.classList.remove("veld-fout");
    veld.removeAttribute("aria-invalid");
    const meld = document.getElementById("meld");
    if (meld && meld.classList.contains("fout") && !document.querySelector(".veld-fout")) {
      zetMeld("", []);
    }
  } catch (e) {
    // Zwijgen: dit is een leesregel, geen poort. Wat er niet doorkomt, keurt Berekenen alsnog.
  }
}

// `stil` is de tik van de klokstand: dan blijft de meldregel staan zoals hij stond,
// want "berekend" hoeft niet elke 20 seconden opnieuw gezegd te worden. De berekening zelf is
// precies dezelfde - er is geen tweede weg naar de kern.
// De vracht van het formulier, op één plek: `reken()` en de solaar sturen dezelfde velden, zodat
// een nieuwe horoscoop en een solaar niet uit elkaar kunnen lopen.
function vrachtFormulier() {
  return {
    naam: naam.value, datum: datum.value, tijd: tijd.value, plaats: plaats.value,
    lat: lat.value, lon: lon.value, tijdzone_id: tz.value,
    // Alleen voor het opzoeken van een lege tijdzone in de kern; hij verandert de berekening niet.
    land: laatsteLand,
    // Koch is het enige stelsel van de cursus: die keuze staat hier niet meer in het formulier.
    huizenstelsel: "Koch",
    tijdcorrectie: correctie.value || null,
    // Chiron hoort bij jaar 2: de techniek staat daar aan maar is standaard
    // verborgen, en het vinkje in het menu Beeld zet hem aan. In jaar 1 bestaat dat vinkje niet en
    // gaat er dus altijd `false` mee - precies zoals de uitgegeven versie het doet.
    met_chiron: techniekAan("chiron") &&
      !!(document.getElementById("toon-chiron") || {}).checked
  };
}

// De sporen van een afgekeurde vraag weghalen (na een geslaagde vraag, of vóór een nieuwe).
function wisFout() {
  document.querySelectorAll(".veld-fout").forEach(e => {
    e.classList.remove("veld-fout");
    e.removeAttribute("aria-invalid");
  });
  document.getElementById("vorige-kaart").textContent = "";
}

// Een afgekeurde vraag: de regels in gewone taal, het veld dat niet klopt (rood + focus), en de
// tekening die er nog staat blijft staan maar krijgt een regel — een oude kaart die zwijgt is erger
// dan een oude kaart met een etiket (etiketfout).
function toonFout(j) {
  const regels = (j.fouten && j.fouten.length) ? j.fouten : [j.fout || "onbekende fout"];
  zetMeld("fout", regels);
  wisFout();
  const velden = (j.velden || []).map(soort => VELD_IDS[soort])
    .filter(id => id && document.getElementById(id));
  velden.forEach(id => {
    const e = document.getElementById(id);
    e.classList.add("veld-fout");
    e.setAttribute("aria-invalid", "true");
  });
  if (document.querySelector("#wielvak svg")) {
    document.getElementById("vorige-kaart").textContent =
      "let op: de tekening hieronder is van de vorige horoscoop — deze vraag is niet berekend.";
  }
  if (velden.length) { document.getElementById(velden[0]).focus(); }
  return null;
}

// --- de plaatsenlijst: één zoeker voor het formulier én het instellingenscherm -----------------
//
// Eén functie voor beide schermen: je zet hem op met de id's van dat scherm (#plaats, #plaatsen,
// #lat, #lon, #tz). Twee keuzelijsten die uit elkaar lopen is precies wat je niet wil, en een
// tweede kopie zou onvermijdelijk gaan afwijken.

function maakPlaatszoeker(cfg) {
  const veld = document.getElementById(cfg.veld);
  const lijstvak = document.getElementById(cfg.lijst);
  let timer = null;

  function kies(p) {
    // Het land van de gekozen plaats gaat mee in de vracht: daarmee zoekt de kern de tijdzone op
    // als het zoneveld leeg is. Zonder land zoekt hij over alle landen, en dan kan een
    // plaats net over de grens de verkeerde zone geven.
    laatsteLand = (p.land || "").toUpperCase();
    // Het **korte label** in het veld: de naam, en alleen waar die naam dubbel bestaat één niveau
    // weer teveel"* en alleen de naam soms te weinig - de lijst bepaalt de lengte (plaatsen.kort),
    // dus geen keuzemenu met formats. Wat hier in het veld staat, gaat ongewijzigd de kaart in, en
    // wie het anders wil typt er gewoon over heen.
    veld.value = p.kort || p.naam;
    document.getElementById(cfg.lat).value = p.lat;
    document.getElementById(cfg.lon).value = p.lon;
    document.getElementById(cfg.zone).value = p.zone;
    if (cfg.etiket) { document.getElementById(cfg.etiket).value = p.etiket || p.naam; }
    if (cfg.dms) coordDms(cfg.lat, cfg.lon, cfg.dms);
    // Een klik uit de lijst lost een klacht over de plaats op.
    veld.classList.remove("veld-fout");
    veld.removeAttribute("aria-invalid");
    lijstvak.innerHTML = "";
    // De coordinaten en de zone staan hier wél: in de meldregel controleer je of een buitenlandse
    // plaats de juiste zone kreeg. In de keuzelijst zelf staan ze niet (die zegt de gebruiker niets).
    cfg.meld("plaats gezet: " + (p.kort || p.naam) + " · " + p.lat.toFixed(4) + " / " + p.lon.toFixed(4) +
      " · " + p.zone + (p.eigen ? " · uit eigen-plaatsen.tsv" : ""));
  }

  function toon(lijst, tekst) {
    if (!lijst.length) {
      // GeoNames blijft de standaard; geeft die niets, dan kan OpenStreetMap uitkomst bieden. Nooit
      // automatisch: één klik, want het is een verzoek aan een ander systeem.
      lijstvak.innerHTML = (tekst && tekst.length >= 3) ? osmBlok(tekst, "") : "";
      const knop = lijstvak.querySelector(".osmzoek");
      if (knop) { knop.addEventListener("click", () => zoekOsm(tekst)); }
      return;
    }
    lijstvak.innerHTML = lijst.map((p, i) =>
      "<div class='plaatsrij'>" +
      "<button type='button' class='plaatskies' data-i='" + i + "'>" +
      "<span class='plaatsnaam'>" + esc(p.naam) + "</span>" +
      "<span class='plaatsmeta'>" + esc(p.onder || p.land) +
      (p.eigen ? " · eigen plaats" : "") + "</span></button>" +
      (p.eigen ? "<button type='button' class='plaatsweg' data-i='" + i +
                 "' title='Deze eigen plaats uit de lijst halen'>&times;</button>" : "") +
      "</div>").join("");
    lijstvak.querySelectorAll(".plaatskies").forEach(b =>
      b.addEventListener("click", () => kies(lijst[Number(b.dataset.i)])));
    lijstvak.querySelectorAll(".plaatsweg").forEach(b =>
      b.addEventListener("click", () => wegEigen(lijst[Number(b.dataset.i)])));
  }

  // --- OpenStreetMap: alleen als de eigen lijst niets geeft --------------------------------
  function osmBlok(tekst, melding) {
    return "<div class='osmblok'>" +
      (melding ? "<div class='osmmelding'>" + esc(melding) + "</div>" : "") +
      "<button type='button' class='osmzoek'>Zoek in OpenStreetMap</button>" +
      "<div class='osmbron'>© OpenStreetMap contributors (ODbL)</div></div>";
  }

  async function zoekOsm(tekst) {
    lijstvak.innerHTML = "<div class='osmblok'><div class='osmmelding'>zoeken in OpenStreetMap…</div></div>";
    try {
      const r = await fetch("/api/osm-zoek", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ q: tekst }) });
      const j = await r.json();
      if (!r.ok) {
        lijstvak.innerHTML = osmBlok(tekst, j.fout || "onbekende fout");
        lijstvak.querySelector(".osmzoek").addEventListener("click", () => zoekOsm(tekst));
        return;
      }
      const gevonden = j.plaatsen || [];
      if (!gevonden.length) {
        lijstvak.innerHTML = osmBlok(tekst, "OpenStreetMap kent dit ook niet. Typ de coördinaten dan zelf in.");
        lijstvak.querySelector(".osmzoek").addEventListener("click", () => zoekOsm(tekst));
        return;
      }
      lijstvak.innerHTML = gevonden.map((p, i) =>
        "<div class='plaatsrij'><button type='button' class='plaatskies' data-i='" + i + "'>" +
        "<span class='plaatsnaam'>" + esc(p.naam) + "</span>" +
        "<span class='plaatsmeta'>" + esc(p.onder || p.land) + " · OSM</span></button></div>").join("") +
        "<div class='osmbron'>© OpenStreetMap contributors (ODbL)</div>";
      lijstvak.querySelectorAll(".plaatskies").forEach(b =>
        b.addEventListener("click", () => kiesOsm(gevonden[Number(b.dataset.i)])));
    } catch (e) {
      lijstvak.innerHTML = osmBlok(tekst, "OpenStreetMap is niet bereikbaar.");
      lijstvak.querySelector(".osmzoek").addEventListener("click", () => zoekOsm(tekst));
    }
  }

  function kiesOsm(p) {
    const zoneveld = document.getElementById(cfg.zone);
    const oudeZone = zoneveld.value;
    kies(p);
    if (!p.zone) { zoneveld.value = oudeZone; }   // geen plaats in de buurt: dan blijft de oude staan
    cfg.meld("uit OpenStreetMap: " + p.naam + " · " + p.lat.toFixed(4) + " / " + p.lon.toFixed(4) +
      (p.zone ? " · " + p.zone + (p.zone_uit ? " (uit " + p.zone_uit + ")" : "")
              : " · kies zelf de tijdzone"));
    // En meteen de vraag of hij in de eigen lijst mag: dan hoeft het de volgende keer niet weer.
    lijstvak.innerHTML = "<div class='osmblok'><button type='button' class='osmbewaar'>" +
      "Bewaar als eigen plaats</button><div class='osmbron'>" + esc(p.onder || "") + "</div></div>";
    lijstvak.querySelector(".osmbewaar").addEventListener("click", () => bewaarEigen(p));
  }

  // Een eigen plaats uit het bestand halen. Bevestigen met de naam erin, zoals bij het
  // hernoemen van een kaart: dit is de enige plek waar iets uit de lijst verdwijnt dat je zelf hebt
  // toegevoegd, en het is niet terug te halen.
  async function wegEigen(p) {
    if (!await bericht({ titel: "Eigen plaats weghalen",
        tekst: "'" + p.naam + "' uit eigen-plaatsen.tsv halen? De plaats verdwijnt uit de keuzelijst. " +
          "Wat je in het formulier hebt staan blijft staan.",
        ja: "Weghalen", nee: "Annuleren" })) {
      return;
    }
    try {
      const r = await fetch("/api/eigenplaats", { method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ naam: p.naam, lat: p.lat, lon: p.lon }) });
      const j = await r.json();
      if (!r.ok) { cfg.meld("Niet verwijderd: " + (j.fout || "onbekende fout")); return; }
      cfg.meld("uit " + j.bestand + " gehaald: " + j.verwijderd);
      veld.dispatchEvent(new Event("input"));     // de lijst opnieuw, nu zonder die regel
    } catch (e) {
      cfg.meld("Niet verwijderd: " + e.message);
    }
  }

  async function bewaarEigen(p) {
    try {
      const r = await fetch("/api/eigenplaats", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ naam: p.naam, lat: p.lat, lon: p.lon, land: p.land, zone: p.zone,
          streek: p.streek, gemeente: p.gemeente,
          bron: p.osm ? "OpenStreetMap " + p.osm : "met de hand" }) });
      const j = await r.json();
      if (!r.ok) { cfg.meld("Niet bewaard: " + (j.fout || "onbekende fout")); return; }
      cfg.meld((j.bestond ? "stond er al in " : "bewaard in ") + j.bestand + ": " + j.plaats.etiket);
      lijstvak.innerHTML = "";
    } catch (e) {
      cfg.meld("Niet bewaard: " + e.message);
    }
  }

  veld.addEventListener("input", () => {
    const tekst = veld.value.trim();
    // Zelf getypt: het land van een eerder gekozen plaats geldt niet meer.
    laatsteLand = "";
    clearTimeout(timer);
    if (tekst.length < 2) { lijstvak.innerHTML = ""; return; }
    timer = setTimeout(async () => {
      try {
        const r = await fetch("/api/plaatsen?zoek=" + encodeURIComponent(tekst));
        const j = await r.json();
        toon(j.plaatsen || [], tekst);
      } catch (e) {
        lijstvak.innerHTML = "";
      }
    }, 150);
  });

  // Zelf een coordinaat intypen werkt ook: de DMS-regel volgt het veld.
  if (cfg.dms) {
    [cfg.lat, cfg.lon].forEach(id =>
      document.getElementById(id).addEventListener("input", () => coordDms(cfg.lat, cfg.lon, cfg.dms)));
  }

  return { kies };
}

const zoekerFormulier = maakPlaatszoeker({
  veld: "plaats", lijst: "plaatsen", lat: "lat", lon: "lon", zone: "tz", dms: "dms",
  meld: (t) => zetMeld("", t)
});

// --- de instellingen: de huidige locatie ---------------------------

const zoekerInstellingen = maakPlaatszoeker({
  veld: "inst-plaats", lijst: "inst-plaatsen", lat: "inst-lat", lon: "inst-lon",
  zone: "inst-tz", etiket: "inst-etiket", dms: "inst-dms",
  meld: (t) => zetInstMelding(t)
});

function zetInstMelding(tekst, soort) {
  const m = document.getElementById("inst-meld");
  m.className = "meld" + (soort ? " " + soort : "");
  m.textContent = tekst;
}

// De plaatszoeker van het solaarvenster: dezelfde als in het formulier en de
// instellingen, met een eigen meldregel. De solaarplaats is niet de geboorteplaats - je kunt op
// vakantie zijn of de solaar voor iemand anders maken - dus hij begint op de huidige locatie en
// mag daarna alles worden.
const zoekerSolaar = maakPlaatszoeker({
  veld: "solaar-plaats", lijst: "solaar-plaatsen", lat: "solaar-lat", lon: "solaar-lon",
  zone: "solaar-zone",
  meld: (t) => zetSolaarMelding(t)
});

function zetSolaarMelding(tekst, soort) {
  const m = document.getElementById("solaar-meld");
  if (!m) { return; }
  m.className = "meld" + (soort ? " " + soort : "");
  m.textContent = tekst;
}

async function laadInstellingen() {
  let j = null;
  try {
    const r = await fetch("/api/instellingen");
    j = await r.json();
    if (!r.ok) {
      // Een bestand dat niet te lezen is (HTTP 400 met een regel in gewone taal): naar het
      // instellingenscherm, want daar is het te herstellen.
      document.getElementById("inst-bestand").textContent = j.bestand || "onbekend";
      toonDialoog("dlg-instellingen");
      zetInstMelding(j.fout || "onbekende fout", "fout");
      return null;
    }
  } catch (e) {
    toonDialoog("dlg-instellingen");
    zetInstMelding("De instellingen zijn niet op te vragen: " + e.message, "fout");
    return null;
  }
  document.getElementById("inst-bestand").textContent = j.bestand || "onbekend";
  if (!j.instellingen && !j.fout) {
    // Nog niets ingesteld: dan opent het programma op dit scherm met de vraag om de locatie
    toonDialoog("dlg-instellingen");
    zetInstMelding("Stel eerst je locatie in: typ de plaatsnaam en kies uit de lijst.", "let-op");
    return null;
  }
  if (j.fout) {
    // Een bestand dat niet te lezen is: ook hierheen, want op dit scherm is het te herstellen.
    toonDialoog("dlg-instellingen");
    zetInstMelding(j.fout, "fout");
    return null;
  }
  const i = j.instellingen;
  document.getElementById("inst-plaats").value = i.naam || "";
  document.getElementById("inst-etiket").value = i.etiket || "";
  document.getElementById("inst-lat").value = i.lat;
  document.getElementById("inst-lon").value = i.lon;
  document.getElementById("inst-tz").value = i.tijdzone_id || "";
  coordDms("inst-lat", "inst-lon", "inst-dms");
  zetInstMelding("huidige locatie: " + (i.etiket || i.naam) + " · " + i.lat.toFixed(4) + " / " +
    i.lon.toFixed(4) + " · " + i.tijdzone_id +
    (i.bijgewerkt ? " (bijgewerkt " + i.bijgewerkt.replace("T", " ") + ")" : ""));
  zetLocatieInFormulier(i);
  return { instellingen: i, nu: j.nu || null };
}

// De locatie van het programma in het invulformulier: dat is de plaats van een nieuwe kaart.
function zetLocatieInFormulier(i) {
  document.getElementById("plaats").value = i.naam || "";
  document.getElementById("lat").value = i.lat;
  document.getElementById("lon").value = i.lon;
  document.getElementById("tz").value = i.tijdzone_id || "";
  coordDms("lat", "lon", "dms");
}

// De openingsstand ("Nu"): naam "Nu", de datum en tijd van de **server**
// en de locatie uit de instellingen. Daarna wordt er gewoon gerekend, met dezelfde weg als elke
// andere kaart - geen eigen endpoint en geen eigen schermtoestand. Wie het formulier aanpast en op
// Rekenen drukt, ziet meteen zijn eigen kaart.
function vulNu(i, nu) {
  actiefId = null;            // "Nu" is een nieuwe kaart, geen bewaarde kaart die open staat
  zetBewaarKnop();
  document.getElementById("naam").value = "Nu";
  document.getElementById("datum").value = (nu && nu.datum) ? alsNederlands(nu.datum) : "";
  document.getElementById("tijd").value = (nu && nu.tijd) || "";
  zetLocatieInFormulier(i);
}

// Het vinkje van jaar 2 volgt de stand van het programma: één waarde in het instellingenbestand, hier
// alleen getoond (T48).
function zetCursusVinkjes() {
  const jaar2 = document.getElementById("cursus-jaar2");
  if (jaar2) { jaar2.checked = profiel.jaren.includes(2); }
}

async function bewaarInstellingen() {
  const knop = document.getElementById("inst-bewaar");
  knop.disabled = true;
  zetInstMelding("opslaan...");
  try {
    const r = await fetch("/api/instellingen", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        naam: document.getElementById("inst-plaats").value,
        etiket: document.getElementById("inst-etiket").value,
        lat: document.getElementById("inst-lat").value,
        lon: document.getElementById("inst-lon").value,
        tijdzone_id: document.getElementById("inst-tz").value,
        // De cursusjaren reizen mee met hetzelfde verzoek (T48): één venster, één knop. Jaar 1 gaat
        // altijd mee; jaar 2 alleen als het vinkje aan staat.
        modules: [1].concat(document.getElementById("cursus-jaar2").checked ? [2] : [])
      })});
    const j = await r.json();
    if (!r.ok) {
      // Hetzelfde als bij Rekenen: het veld dat niet klopt aanwijzen en de focus erheen.
      const ids = { plaats: "inst-plaats", breedte: "inst-lat", lengte: "inst-lon" };
      const velden = (j.velden || []).map(soort => ids[soort]).filter(id => id && document.getElementById(id));
      velden.forEach(id => {
        const e = document.getElementById(id);
        e.classList.add("veld-fout");
        e.setAttribute("aria-invalid", "true");
      });
      if (velden.length) { document.getElementById(velden[0]).focus(); }
      zetInstMelding(j.fout || "onbekende fout", "fout");
      return;
    }
    document.querySelectorAll(".instellingen .veld-fout").forEach(e => {
      e.classList.remove("veld-fout");
      e.removeAttribute("aria-invalid");
    });
    const i = j.instellingen;
    // De cursusjaren meteen toepassen, en vóór het eventuele opnieuw rekenen hieronder: anders wordt
    // de kaart van nu nog met de oude modules berekend.
    const wasJaar2 = profiel.jaren.includes(2);
    const isJaar2 = (i.modules || [1]).includes(2);
    await laadProfiel();
    zetCursusVinkjes();
    document.getElementById("inst-bestand").textContent = j.bestand || "onbekend";
    // De locatie is de plaats van een nieuwe kaart: meteen in het formulier zetten. Staat er nog
    // geen kaart in het wiel, of staat de kaart van nu er (naam "Nu"), dan rekenen we die meteen
    // opnieuw met de nieuwe locatie; een kaart die de gebruiker zelf open heeft blijft staan.
    zetLocatieInFormulier(i);
    const naamveld = document.getElementById("naam").value.trim();
    if (!document.querySelector("#wielvak svg") || naamveld === "" || naamveld === "Nu") {
      vulNu(i, j.nu);
      await reken();
    }
    // Wat er aan de modules veranderd is hoort de gebruiker te lezen, want de gevolgen zijn zichtbaar
    // in het scherm (tekens erbij of eraf) en in de menu's.
    const jaarRegel = (isJaar2 && !wasJaar2)
      ? " Jaar 2 staat aan: Chiron, de dominantmarkering en Solaar zijn beschikbaar — druk op F9 om " +
        "deze kaart opnieuw te berekenen."
      : (!isJaar2 && wasJaar2)
        ? " Jaar 2 staat uit: de tekens van jaar 2 zijn verborgen, de kaart zelf blijft zoals hij is."
        : "";
    let regel = (j.nieuw ? "nieuw bewaard: " : "bijgewerkt: ") + j.bestand;
    if (j.waarschuwingen && j.waarschuwingen.length) {
      zetInstMelding(regel + " - let op: " + j.waarschuwingen.join(" "), "let-op");
    } else {
      // Zonder waarschuwing sluit het venster, zoals een Windows-dialoog: de uitkomst staat daarna
      // in de meldregel van het hoofdvenster. Mét waarschuwing blijft het open, anders leest hij die
      // regel nooit.
      const samenvatting = (i.etiket || i.naam) + " · " + i.lat.toFixed(4) + " / " +
        i.lon.toFixed(4) + " · " + i.tijdzone_id;
      zetInstMelding(regel + " · " + samenvatting + jaarRegel);
      sluitDialoog();
      zetMeld(jaarRegel ? "let-op" : "", "instellingen bewaard: " + samenvatting + jaarRegel);
    }
  } catch (e) {
    zetInstMelding("Opslaan lukte niet: " + e.message, "fout");
  } finally {
    knop.disabled = false;
  }
}

function vulFormulier(m) {
  naam.value = m.naam || "";
  datum.value = alsNederlands(m.datum);
  tijd.value = m.tijd || "";
  plaats.value = m.plaats || "";
  lat.value = m.lat === undefined ? "" : m.lat;
  lon.value = m.lon === undefined ? "" : m.lon;
  coordDms("lat", "lon", "dms");
  tz.value = m.tijdzone_id || "Europe/Amsterdam";
  correctie.value = (m.tijdcorrectie === "utc" || m.tijdcorrectie === "lmt") ? m.tijdcorrectie : "";
  // Programmatisch gevulde velden zijn geen typwerk: de vlag voor "nog niet bewaard" gaat uit.
  vies = false;
  // Chiron heeft geen vinkje meer in jaar 1. Een oude kaart die er tóch een heeft, wordt zonder
  // gerekend en dat zegt de meldregel (zie openKaart) - stil een ander getal tonen is erger.
}

// Het uitlegvak van een invulveld staat vast aan het venster (zie de CSS): rechts van het formulier
// en op de hoogte van zijn eigen veld. Het mag nooit in de buurt van de rand verdwijnen.
function plaatsUitlegvak(vak) {
  const veld = vak.closest(".veld");
  if (!veld) { return; }
  // De zoom **meten**, niet aannemen. `getBoundingClientRect()` geeft beeldpunten *na*
  // de zoom, maar `left`/`top` op dit `position: fixed`-vak leest de browser *vóór* de zoom: dan
  // wordt het vak twee keer geschaald. Gemeten op 150 %: 269 px naast het formulier in plaats van 14,
  // en 75 px te laag. Delen door de gemeten zoom zet dat recht — dezelfde truc als in `schaalAfdruk()`.
  const zw = parseFloat(getComputedStyle(document.documentElement).zoom) || 1;
  const anker = veld.getBoundingClientRect();
  const formulier = document.getElementById("form").getBoundingClientRect();
  // De hoogte in **beeldpunten**, net als `innerHeight`: `offsetHeight` is de maat vóór de zoom en dan
  // klopte de ondergrens op 150 % niet meer.
  const hoogte = vak.getBoundingClientRect().height || 60;
  let top = anker.top - 2;
  if (top + hoogte > innerHeight - 8) { top = innerHeight - hoogte - 8; }
  vak.style.top = Math.round(Math.max(8, top) / zw) + "px";
  vak.style.left = Math.round((formulier.right + 14) / zw) + "px";
}

// --- De solaar  ----------------------------------------------------------------

// De solaar begint bij de Zon van een **berekende** horoscoop. Staat het scherm op de horoscoop van
// dit moment, dan is er geen natal Zon om naar terug te keren: dezelfde grendel als bij de transits-
// tab en de progressies. De regel blijft staan maar is uitgegrijsd, zodat je ziet dat hij bestaat en
// waarom hij nu niets doet.
function zetSolaarMenu() {
  const b = document.getElementById("menu-solaar");
  if (!b) { return; }
  const mag = !!(laatste && laatste.kaart) && !klokStand() && techniekAan("solaar");
  b.disabled = !mag;
  b.title = mag ? "" : "De solaar hoort bij een berekende horoscoop, niet bij de horoscoop van dit moment";
}

//
// Het venster vraagt twee dingen: een jaar (welke terugkeer) en een plaats (waar je dan bent). De
// schil zoekt het moment - Newton op de Zonsnelheid, zie `kern/solaar.py` - en geeft de kloktijd van
// die plaats terug. Daarna gaat alles door de gewone weg: velden vullen, `reken()`, klaar. Er is
// geen tweede soort horoscoop en geen eigen scherm; daarom staat hier ook geen eigen weergave.

async function openSolaar() {
  if (!laatste || !laatste.kaart || klokStand()) {
    zetMeld("let-op", "Bereken eerst een horoscoop; de solaar begint bij de Zon van die horoscoop.");
    return;
  }
  const zon = (laatste.kaart.punten || []).find(p => p.naam === "Zon");
  if (zon) {
    const b = zon.positie;
    document.getElementById("dlg-solaar-uitleg").textContent =
      "De Zon staat in deze horoscoop op " + String(b.graad).padStart(2, "0") + "° " +
      b.teken + " " + String(b.minuut).padStart(2, "0") + "' — ik zoek het moment waarop zij " +
      "daar terug is.";
  }
  const jaarVeld = document.getElementById("solaar-jaar");
  if (!jaarVeld.value) { jaarVeld.value = String(new Date().getFullYear()); }
  // De plaats begint op de huidige locatie van het programma. Alleen lezen, niet opslaan: het
  // instellingenbestand blijft waar het is (en het formulier houdt zijn eigen plaats).
  if (!document.getElementById("solaar-lat").value) {
    try {
      const j = await (await fetch("/api/instellingen")).json();
      const i = j && j.instellingen;
      if (i) {
        zoekerSolaar.kies({ naam: i.naam, etiket: i.etiket, lat: i.lat, lon: i.lon,
                            zone: i.tijdzone_id, land: i.land });
      }
    } catch (e) { /* dan blijft de plaats leeg en kiest de gebruiker er een */ }
  }
  zetSolaarMelding("");
  toonDialoog("dlg-solaar");
  jaarVeld.focus();
}

async function berekenSolaar() {
  const jaar = String(document.getElementById("solaar-jaar").value || "").trim();
  const plaats = document.getElementById("solaar-plaats").value.trim();
  const lat = document.getElementById("solaar-lat").value.trim();
  const lon = document.getElementById("solaar-lon").value.trim();
  const zone = document.getElementById("solaar-zone").value.trim();
  if (!jaar) { zetSolaarMelding("Vul een jaartal in, bijvoorbeeld " + new Date().getFullYear() + ".", "let-op"); return; }
  if (!lat || !lon || !zone) {
    zetSolaarMelding("Kies een plaats uit de lijst; dan weet het programma de coördinaten en de tijdzone.", "let-op");
    return;
  }
  const knop = document.getElementById("dlg-solaar-ok");
  knop.disabled = true;
  zetSolaarMelding("het moment zoeken…");
  try {
    const vraag = vrachtFormulier();
    vraag.jaar = jaar;
    vraag.solaar_plaats = plaats;
    vraag.solaar_lat = lat;
    vraag.solaar_lon = lon;
    vraag.solaar_zone = zone;
    const r = await fetch("/api/solaar", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(vraag) });
    const j = await r.json();
    if (!r.ok) { zetSolaarMelding(j.fout || "onbekende fout", "fout"); return; }
    sluitDialoog();
    await vulSolaar(j, jaar, plaats);
  } catch (e) {
    zetSolaarMelding("De solaar kon niet berekend worden: " + e.message, "fout");
  } finally {
    knop.disabled = false;
  }
}

async function vulSolaar(j, jaar, plaats) {
  const m = j.solaar;
  // De naam krijgt er "(Solaar 2026)" achter, zoals in het eigen PHP-programma: het is daarna een
  // gewone horoscoop die je kunt bewaren. Staat het er al, dan komt het er niet twee keer op.
  const naamVeld = document.getElementById("naam");
  const basis = String(naamVeld.value || "").replace(/\s*\(Solaar \d{4}\)\s*$/, "").trim();
  naamVeld.value = (basis || "Solaar") + " (Solaar " + jaar + ")";
  document.getElementById("datum").value = alsNederlands(m.datum);
  document.getElementById("tijd").value = m.tijd;
  document.getElementById("plaats").value = plaats;
  document.getElementById("lat").value = m.lat;
  document.getElementById("lon").value = m.lon;
  document.getElementById("tz").value = m.tijdzone_id;
  document.getElementById("correctie").value = "";     // de geldende zonetijd van de plaats
  coordDms("lat", "lon", "dms");
  actiefId = null;        // een solaar is een nieuwe horoscoop, geen bewaarde kaart die open staat
  zetBewaarKnop();
  klokStop();
  const antwoord = await reken(true);
  if (!antwoord) { return; }
  const zon = (laatste.kaart.punten || []).find(p => p.naam === "Zon");
  const stand = zon ? String(zon.positie.graad).padStart(2, "0") + "° " + zon.positie.teken + " " +
    String(zon.positie.minuut).padStart(2, "0") + "'" : "";
  const regels = ["solaar van " + jaar + ": de Zon terug op " + stand + " — " +
    alsNederlands(m.datum) + " " + m.tijd + " " + m.offset_label + " (" + m.utc + " UT), " +
    "berekend voor " + plaats + "."];
  if (String(m.datum.slice(0, 4)) !== String(jaar)) {
    regels.push("Die terugkeer valt op " + alsNederlands(m.datum) + ": dat is de terugkeer die " +
      "het dichtst bij je verjaardag in " + jaar + " ligt.");
  }
  regels.push(...laatsteLetOp, ...(j.waarschuwingen || []));
  zetMeld(laatsteLetOp.length || (j.waarschuwingen || []).length ? "let-op" : "", regels);
}
