// 00-basis.js
//
// De gedeelde toestand en de kleine helpers: esc, dms, glyfVan, de maandnamen.
//
// Alle bestanden delen één werkruimte en worden in deze volgorde geladen; 90-start.js
// komt achteraan en gebruikt wat hierboven staat.

// Het kenmerk waarmee de schil dit venster terugvindt. De schil opent de pagina met
// `?vt=<kenmerk>` en zoekt het venster daarna op in de titel: zonder kenmerk pakt ze bij twee
// vensters het verkeerde, en juist dan wordt de stand op het verkeerde venster toegepast.
let kenmerk = "";
// De titel noemt het cursusjaar van het jaarprofiel en houdt het kenmerk erin: de schil zoekt dit
// venster op dat kenmerk terug. Zonder die regel zou een latere titelzetting het
// kenmerk wissen en pakt de schil bij twee vensters het verkeerde.
function zetTitel(jaar) {
  document.title = "Astrologie Studio - cursusjaar " + jaar + (kenmerk ? " [" + kenmerk + "]" : "");
}
function techniekAan(id) { return profiel.technieken.has(id); }

// Getallen met duizendtallen, zoals de rest van het scherm.
function trGetal(n) {
  return Number(n || 0).toLocaleString("nl-NL");
}


let laatste = null;
// De let-op-regels van de laatste berekening, zodat het openen van een bewaarde horoscoop ze kan
// meenemen in één meldblok in plaats van ze aan een tekst vast te plakken.
let laatsteLetOp = [];

function esc(s) { return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;"); }

// Coördinaten in graden/minuten/seconden. Het veld blijft decimaal, dit is
// alleen weergave. De lezer van de invoer aanvaardt ook `51°40' N`, dus die vorm wordt hier ook
// gelezen - anders valt de regel weg zodra hij zelf een graden/minuten-waarde typt.
function dms(waarde, as) {
  const tekst = String(waarde === undefined || waarde === null ? "" : waarde).trim();
  if (!tekst) return "";
  let n = Number(tekst.replace(",", "."));
  if (!isFinite(n)) {
    const m = tekst.match(/^([+-]?\d+)\s*°\s*([\d.,]*)\s*'?\s*([NSEOZW])?$/i);
    if (!m) return "";
    n = Math.abs(Number(m[1])) + (Number((m[2] || "0").replace(",", ".")) || 0) / 60;
    if (m[3] && /[ZW]/i.test(m[3])) n = -n;
  }
  const teken = n < 0 ? (as === "lat" ? "Z" : "W") : (as === "lat" ? "N" : "O");
  let rest = Math.abs(n);
  let graden = Math.floor(rest);
  rest = (rest - graden) * 60;
  let minuten = Math.floor(rest);
  let seconden = Math.round((rest - minuten) * 60);
  if (seconden === 60) { seconden = 0; minuten += 1; }
  if (minuten === 60) { minuten = 0; graden += 1; }
  const twee = (x) => (x < 10 ? "0" : "") + x;
  // Ook de graden twee cijfers, dezelfde standaard als bij de
  // zodiacstanden: elke weergave van een positie lijnt zo uit.
  return twee(graden) + "°" + twee(minuten) + "'" + twee(seconden) + '" ' + teken;
}

// De leesregel onder de twee coordinatenvelden van een scherm bijwerken.
function coordDms(latId, lonId, doelId) {
  const doel = document.getElementById(doelId);
  if (!doel) return;
  const breedte = dms(document.getElementById(latId).value, "lat");
  const lengte = dms(document.getElementById(lonId).value, "lon");
  doel.textContent = (breedte && lengte) ? (breedte + " · " + lengte) : "";
}

// Welke id hoort bij welke soort gegeven: de kern noemt het gegeven,
// de pagina weet welk invulveld daarbij hoort. Eén tabel, zodat formulier en instellingen niet
// uit elkaar kunnen lopen als er een veld bij komt.
// --- Het meldblok onder het formulier ---------------------------------------------------------
// Eén blok met een kop (het soort) en daaronder één regel per melding, in plaats van één lange zin
// met "·" als enige structuur. Het soort staat als woord
// in de kop, zodat het niet meer alleen aan de kleur te zien is. De hoogte staat in de CSS begrensd.
const MELD_KOP = { "let-op": "Let op", fout: "Niet gelukt" };

function zetMeld(soort, regels) {
  const m = document.getElementById("meld");
  m.className = "meld" + (soort ? " " + soort : "");
  m.innerHTML = "";
  const lijst = (Array.isArray(regels) ? regels : [regels])
    .map(t => String(t == null ? "" : t).trim()).filter(Boolean);
  if (!lijst.length) { return; }
  if (MELD_KOP[soort]) {
    const kop = document.createElement("div");
    kop.className = "meldkop";
    kop.textContent = MELD_KOP[soort];
    m.appendChild(kop);
  }
  lijst.forEach(t => {
    const regel = document.createElement("div");
    regel.className = "meldregel";
    regel.textContent = t;
    m.appendChild(regel);
  });
}

const VELD_IDS = { datum: "datum", tijd: "tijd", breedte: "lat", lengte: "lon",
                   plaats: "plaats", tijdcorrectie: "correctie" };

// --- de bewaarde kaarten: openen, bewaren, verwijderen ---------------------------------------

let kaarten = [];

// De volgorde van dit paneel is laatst bewaard, en het toont
// alleen de nieuwste acht: het vak is 380 px en daar passen acht ruime rijen plus de regel "Alle
// horoscopen…" precies in. Sorteren op naam hoort niet in dit paneel maar in het venster
// met alle horoscopen. `kaarten` zelf houdt de volgorde van de index aan: `data-i` verwijst daar
// naar bij openen en verwijderen, dus er wordt gesorteerd op een kopie met de oorspronkelijke
// index erbij.
const RECENT_MAX = 8;

// Welke bewaarde kaart er open staat: het **id** van de kaart, niet de bestandsnaam —
// die volgt uit datum en naam en verandert dus als je de kaart hernoemt. `null` betekent: er staat
// geen bewaarde kaart open, dus de knop heet Bewaren en maakt een nieuwe kaart.
let actiefId = null;
// Het land van de gekozen plaats, voor het opzoeken van de tijdzone.
let laatsteLand = "";

// De datum in Nederlandse volgorde. De lezer van de invoer aanvaardt
// allebei, dus dit is alleen weergave; de kaart zelf houdt zijn ISO-datum.
function alsNederlands(datum) {
  const m = String(datum || "").trim().match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  return m ? m[3] + "-" + m[2] + "-" + m[1] : String(datum || "");
}

// Het UT-moment uit de kaart in Nederlandse volgorde, met de tijd erachter.
function alsUtNederlands(utc) {
  const m = String(utc || "").trim().match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}:\d{2}:\d{2})$/);
  return m ? m[3] + "-" + m[2] + "-" + m[1] + " " + m[4] : String(utc || "");
}

const GLYF_TEKEN = {"Ram":"♈","Stier":"♉","Tweelingen":"♊","Kreeft":"♋","Leeuw":"♌","Maagd":"♍",
  "Weegschaal":"♎","Schorpioen":"♏","Boogschutter":"♐","Steenbok":"♑","Waterman":"♒","Vissen":"♓"};
function glyfTeken(t) { return "<span class='glyf'>" + (GLYF_TEKEN[t] || "?") + "</span>"; }

// De twee aanvullingen van jaar 1: element/kruisverdeling en heerschappen.
// De kruisen komen uit kern/elementen.py met de Engelse naam (Cardinal/Fixed/Mutable); op het scherm
// staan ze in het Nederlands. De sleutel in de kaart-JSON blijft Engels: dat is het contract.
const KRUIS_NL = {"Cardinal": "Hoofd", "Fixed": "Vast", "Mutable": "Beweeglijk"};

// De glyphs voor de lijst en de groepenlijsten. Ascendant en MC hebben geen eigen
// Unicode-teken; daar staat de leesbare afkorting, net als in een gewone kaart. Die twee zijn dus
// letters en geen tekens, en dat verschil is te zien: een glyph is 7-12 px breed, "AC" is er 16.
// Daarom krijgen ze de klasse `letters` (kleiner, uit het gewone lettertype) en staat elk teken in een
// vast vak van 16 px met 4 px lucht erna, zodat alle namen op één lijn beginnen.
const GLYF = {"Zon":"☉", "Maan":"☽", "Mercurius":"☿", "Venus":"♀", "Mars":"♂", "Jupiter":"♃",
  "Saturnus":"♄", "Uranus":"♅", "Neptunus":"♆", "Pluto":"♇", "Noordknoop":"☊", "Chiron":"⚷",
  "Dagpars":"⊗", "Ascendant":"AC", "MC":"MC"};
function glyfVan(n) {
  const g = GLYF[n] || "?";
  return "<span class='glyf" + (g.length > 1 ? " letters" : "") + "'>" + g + "</span>";
}
// Teken en naam als één paar: het teken in het vaste vak, daarachter de naam. Overal waar een glyph
// door een naam gevolgd wordt loopt het hierlangs, zodat er geen losse spaties meer nodig zijn.
function glyfNaam(naam, label) {
  return "<span class='glyfvak'>" + glyfVan(naam) + "</span><span class='naam'>" + esc(label) + "</span>";
}

// Een datum uit een gegevensbestand voluit in het Nederlands.
// Alleen voor de Over-tekst; de gewone datums in het programma gaan door `alsNederlands()`.
const MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
                 "september", "oktober", "november", "december"];
function langeDatum(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ""));
  if (!m) { return String(iso || ""); }
  const maand = MAANDEN[Number(m[2]) - 1] || m[2];
  return Number(m[3]) + " " + maand + " " + m[1];
}


// --- Nieuw en Openen ---------------------------------------------------------------
//
// Nieuw zet het formulier terug op de kaart van dit moment (met de locatie uit de instellingen) en
// rekent opnieuw — dezelfde weg als het openen van het programma, dus geen tweede waarheid.
// Openen… toont de bewaarde kaarten in een dialoogvenster en roept `openKaart()` aan: precies wat een
// klik in de kolom rechts doet.
//
// `vies` onthoudt of er sinds de laatste berekening iets in het formulier is getypt. Zonder die vlag
// zou Nieuw stil werk weggooien; met die vlag vraagt hij het, zoals een Windows-programma hoort te doen.

let vies = false;

// Voor waarden in een attribuut: `esc` dekt & en <, maar een naam met een aanhalingsteken zou het
// attribuut openbreken. Vandaar een eigen hulpje voor title.
function attr(s) { return esc(s).replace(/"/g, "&quot;"); }

// De maten van het venster: de schil opent de volgende start hetzelfde venster. Drie
// getallen - de buitenmaat van het venster, de schermmaat en de schermmaat zonder taakbalk - want
// daaruit leidt de schil af of je in volledig scherm, gemaximaliseerd of in een gewoon venster
// werkt.
//
// Het vierde getal, `rust`, is de maat waar het venster naar terug moet als de gebruiker op
// "kleiner" klikt. Dat is niet de buitenmaat: in volledig scherm is die de schermmaat zelf. Daarom
// onthouden we apart de laatste maat waarin het venster NIET schermvullend was.
//
// `keepalive` zodat de melding ook aankomt als het venster juist dichtgaat; bij een maatwijziging
// gaat er één melding na 600 ms, niet één per pixel.
// Twee signalen, niet één: op Windows-Edge blijft `outerWidth/outerHeight` in app-modus volledig
// scherm op de venstermaat staan, terwijl het beeldvlak dan wel het hele scherm vult. Op Linux
// is het omgekeerd: daar groeit `buiten` mee en blijft `binnen` een stukje onder de schermhoogte.
// Daarom melden we allebei, en beslist de schil.
//
// `laatsteStaat` bestaat omdat een venster dat sluit eerst uit volledig scherm gehaald kan worden:
// dan meldt de pagina bij het sluiten de rustmaat in plaats van de stand waarin je hem wegklikte. Op
// `pagehide` gaat daarom de laatst gemeten stand mee, niet een nieuwe meting.
let laatsteRust = null;
let laatsteStaat = null;
const paginaStart = Date.now();
