// 20-kaart.js
//
// De kaart: berekenen, tonen, het overzicht, de aspecten en de bewaarde horoscopen.
//
// Alle bestanden delen één werkruimte en worden in deze volgorde geladen; 90-start.js
// komt achteraan en gebruikt wat hierboven staat.


async function reken(stil) {
  if (!stil) { zetMeld("", "berekenen…"); }
  const vraag = vrachtFormulier();
  try {
    const r = await fetch("/api/rekenen", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(vraag) });
    const j = await r.json();
    if (!r.ok) { return toonFout(j); }
    laatste = j;
    wisFout();
    toon(j);
    zetBewaarKnop();   // er is nu iets te bewaren (en: Aanpassen als er een bewaarde kaart open staat)
    // De twee velden laten zien wat de kern gelezen heeft: met F9 verlaat je geen
    // veld, dus de blur-regel komt er dan niet aan te pas en zou het formulier na een geslaagde
    // berekening alsnog in de losse vorm blijven staan. Zelfde waarde, alleen in de standaardvorm.
    const m = (j.kaart.meta || {});
    if (m.datum) { datum.value = alsNederlands(m.datum); }
    if (m.tijd) { tijd.value = m.tijd; }
    // De meldregel zegt alleen wat er met de **invoer** aan de hand is. Het UT-moment en de zone
    // staan in het gegevensblok; blijft er niets te melden over, dan zegt de regel alleen dat het
    // gelukt is.
    const let_op = (j.waarschuwingen || []).slice();
    // Een lege tijdzone is door de kern opgezocht bij de coördinaten; het veld volgt dat, zodat je
    // ziet welke zone er gebruikt is en hem kunt bijstellen.
    if (!tz.value && j.kaart.meta && j.kaart.meta.tijdzone_id) {
      tz.value = j.kaart.meta.tijdzone_id;
    }
    // Staat er iets te melden, dan zegt de kop "Let op" het al en is "berekend" een overbodige
    // regel. Zonder opmerkingen blijft "berekend" staan als bevestiging.
    if (!stil) { zetMeld(let_op.length ? "let-op" : "", let_op.length ? let_op : ["berekend"]); }
    laatsteLetOp = let_op;
    vies = false;   // wat er in het formulier staat is nu precies deze kaart
    trActualiseer();   // de transits-tab hangt aan deze kaart
    zetSolaarMenu();   // en de solaar ook: die vraagt een berekende horoscoop
    return j;
  } catch (e) {
    zetMeld("fout", e.message);
    return null;
  }
}

// Wanneer een kaart "bewaard" is: het veld uit de index, met het id als terugval. Allebei zijn het
// milliseconden, dus een kaart van vóór de wijziging sorteert gewoon mee.
function bewaardOp(k) {
  return Number(k && (k.bewaard || k.id)) || 0;
}

function zetBewaarKnop() {
  const b = document.getElementById("bewaar");
  // Zonder gerekende kaart valt er niets te bewaren: dan is de knop uitgegrijsd in plaats van een
  // knop die bij een leeg formulier een foutmelding geeft (zelfde regel als in de menu's).
  b.disabled = !laatste;
  const open = (actiefId !== null && actiefId !== undefined);
  b.textContent = open ? "Aanpassen" : "Bewaren";
  // De knop zegt wat hij dóet, niet hoe hij het doet: "het bestand overschrijven" is onze zorg.
  // De titel van de open horoscoop is ook de enige plek waar "Aanpassen" wordt uitgelegd.
  b.title = open
    ? "Deze bewaarde horoscoop bijwerken"
    : "Deze horoscoop als nieuwe bewaren";
}

function toonKaarten() {
  const vak = document.getElementById("kaartenlijst");
  const meer = document.getElementById("kaartenmeer");
  if (!kaarten.length) {
    vak.innerHTML = "<div class='leeg'>nog geen bewaarde horoscopen</div>";
    if (meer) { meer.hidden = true; }
    return;
  }
  // De nieuwste bovenaan; bij gelijke tijd beslist de index, zodat de volgorde niet verspringt.
  const nieuwste = kaarten.map((k, i) => ({ k, i }))
    .sort((a, b) => (bewaardOp(b.k) - bewaardOp(a.k)) || (b.i - a.i))
    .slice(0, RECENT_MAX);
  vak.innerHTML = nieuwste.map(({ k, i }) => {
    // Eén regel: de naam, en daarachter het moment en de plaats: "1 rij, anders
    // wordt het te druk". Datum en tijd staan **vooraan** in de meta, zodat een ellips bij een lange
    // naam of plaats de plaats raakt en nooit het moment: dat is het enige wat je hier zoekt.
    // De meta in drie stukken, elk met een eigen krimpgewicht in de CSS: de plaats
    // verdwijnt eerst, dan de tijd, en de datum blijft staan. Eén string kan dat niet - dan krimpt
    // het geheel en verdwijnt het moment samen met de plaats.
    const meta = "<span class='m-datum'>" + esc(alsNederlands(k.datum)) + "</span>" +
      // Zonder seconden: die staan in de kaart en in het scherm, maar niet in een lijstje van één
      // regel. De kop van de afdruk doet hetzelfde (`trDrukKop`), dus dit is één maat voor beide.
      "<span class='m-tijd'>" + esc(String(k.tijd || "").slice(0, 5)) + "</span>" +
      // De plaatsnaam kan in deze smalle kolom afgekapt worden; de titel maakt hem dan leesbaar
      // zonder de rij breder te maken.
      (k.plaats ? "<span class='m-plaats' title='" + esc(k.plaats) + "'>· " + esc(k.plaats) + "</span>" : "") +
      (k.huizenstelsel && k.huizenstelsel !== "K"
        ? "<span class='m-plaats'>· " + esc(k.huizenstelsel_naam || k.huizenstelsel) + "</span>" : "");
    return "<div class='kaartrij'>" +
      "<button type='button' class='kaartnaam' data-i='" + i + "' title='Openen en opnieuw berekenen'>" +
      "<span class='kaartnaaml'>" + esc(k.naam || "zonder naam") + "</span>" +
      "<span class='kaartmeta'>" + meta + "</span></button>" +
      "<button type='button' class='kaartweg' data-i='" + i + "' title='Deze horoscoop verwijderen'>&times;</button>" +
      "</div>";
  }).join("");
  // Een plaats die na het inleveren alleen een "…" van een paar px overhoudt is ruis; dan liever
  // niets. De rest van de regel is niet kleiner te maken - datum en tijd staan op `flex: 0 0 auto` -
  // dus dit is puur het laatste restje van de plaats: "wat er meer bij kan is
  // prettig", en een losse ellips is geen "meer".
  vak.querySelectorAll(".m-plaats").forEach(p => {
    if (p.getBoundingClientRect().width < 26) { p.hidden = true; }
  });
  // De verwijzing staat er alleen als er ook echt meer is dan er past.
  if (meer) { meer.hidden = kaarten.length <= RECENT_MAX; }
  vak.querySelectorAll(".kaartnaam").forEach(b =>
    b.addEventListener("click", () => openKaart(Number(b.dataset.i))));
  vak.querySelectorAll(".kaartweg").forEach(b =>
    b.addEventListener("click", () => verwijderKaart(Number(b.dataset.i))));
}

async function laadKaarten() {
  try {
    const r = await fetch("/api/kaarten");
    kaarten = await r.json();
  } catch (e) {
    kaarten = [];
  }
  toonKaarten();
}

async function openKaart(i) {
  const k = kaarten[i];
  if (!k) { return; }
  zetMeld("", "openen: " + k.naam + "…");
  const r = await fetch("/api/lees", { method: "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ bestand: k.bestand }) });
  const j = await r.json();
  if (!r.ok) {
    zetMeld("fout", j.fout || "onbekend");
    return;
  }
  vulFormulier(j.meta || {});
  klokStop();             // een bewaarde horoscoop is geen "nu"
  // Vanaf hier is dit de open kaart: de knop wordt Aanpassen en werkt deze kaart bij.
  actiefId = (k.id !== undefined) ? k.id : null;
  zetBewaarKnop();
  zetTab("wiel");
  const antwoord = await reken();
  if (antwoord) {
    // "berekend" is hier overbodig (het openen zegt het al) maar de let-op-regels van de berekening
    // horen erbij; elke regel krijgt een eigen regel in het blok.
    //
    // Chiron volgt het jaarprofiel en het vinkje onder Beeld, niet het moment van bewaren; en omdat
    // de app altijd met Koch rekent (zie `huizenstelsel: "Koch"` in de vraag hierboven) is opnieuw
    // rekenen met het standaardstelsel genoeg voor een bestand van elders.
    zetMeld(laatsteLetOp.length ? "let-op" : "",
            ["geopend en opnieuw berekend: " + k.bestand].concat(laatsteLetOp));
  }
}

async function verwijderKaart(i) {
  const k = kaarten[i];
  if (!k) { return; }
  const door = await bericht({ titel: "Horoscoop verwijderen",
    tekst: "Horoscoop '" + (k.naam || "zonder naam") + "' (" + alsNederlands(k.datum) +
      ") verwijderen? Het bestand gaat weg en dat is niet terug te draaien.",
    ja: "Verwijderen", nee: "Annuleren" });
  if (!door) { return; }
  const r = await fetch("/api/verwijder", { method: "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ bestand: k.bestand }) });
  const j = await r.json();
  if (!r.ok) {
    zetMeld("fout", j.fout || "onbekend");
    return;
  }
  zetMeld("", "verwijderd: " + j.verwijderd);
  if (actiefId !== null && actiefId !== undefined && actiefId === k.id) {
    actiefId = null;          // de open kaart bestaat niet meer: terug naar Bewaren
    zetBewaarKnop();
  }
  await laadKaarten();
  // Staat het venster Horoscopen open, dan moet de tabel mee: dezelfde functie bedient het kruisje
  // in het paneel én de knop in de rij (één regel, twee deuren).
  if (!document.getElementById("dlg-openen").hidden) { tekenOpenen(); }
}

function toon(j) {
  const k = j.kaart;
  zetStatusKaart(k);
  // Een andere kaart betekent een ander bevroren moment: het bi-wheel hoort niet stiekem
  // op de datum van de vorige kaart te blijven staan.
  const stempel = [k.meta.naam, k.meta.datum, k.meta.tijd].join("|");
  if (stempel !== wmStempel) {
    wmStempel = stempel; wielMoment = null; wmBuffer = ""; drukBeeld = null;
  }
  zetWielBeeld(j.svg);
  const g = k.meta, h = [];
  const rij = (a, b) => h.push("<dt>" + a + "</dt><dd>" + esc(b) + "</dd>");
  // De herkomst van de tijdzone is debug-informatie en blijft in het gegevensblok; alleen het
  // Engelse "manual" (de tijd is zo ingevoerd, uit de keuze UT of LMT) wordt hier vertaald. De
  // sleutel in de kaart-JSON blijft ongemoeid — dit is de rand, niet het contract.
  const herkomst = s => (s === "manual" ? "zo ingevoerd" : s);
  rij("Naam", g.naam); rij("Datum", alsNederlands(g.datum)); rij("Tijd", g.tijd + " (" + g.offset_label + ", " + herkomst(g.offset_source) + ")");
  rij("UT", alsUtNederlands(g.utc)); rij("Plaats", g.plaats); rij("Coordinaten", dms(g.lat, "lat") + " / " + dms(g.lon, "lon"));
  // "Dierenriem" en niet "Zonneteken": dit is de methode waarop de dierenriem is
  // opgebouwd (Tropisch) met het rekencentrum erbij - niet het teken waarin de Zon staat.
  rij("Dierenriem", g.zodiactype + ", " + g.centrum); rij("Huizen", g.huizenstelsel_naam); rij("Knoop", g.knoop);
  rij("Jul. dag", g.julian_day_ut.toFixed(6));
  document.getElementById("gegevens").innerHTML = "<dl class='gegevens'>" + h.join("") + "</dl>";
  document.getElementById("lijstvak").innerHTML = lijstHTML(k);
  koppelSorteer();
  document.getElementById("toevoegingen").innerHTML = toevoegingenHTML(j);
  // Vier kolommen: vijftien punten (met Chiron) worden dan vier rijen hoog en passen onder het
  // wiel zonder dat de Wiel-tab hoeft te scrollen.
  document.getElementById("standen").innerHTML = standenHTML(k, 2);
  zetAfdruk(j);
  document.getElementById("afdruk").classList.add("vast");
  schaalAfdruk();
  // Alleen als er echt iets raakt: nul botsingen is de gewone stand en hoeft geen regel.
  document.getElementById("kruis").innerHTML = j.botsingen.aantal > 0
    ? "<span class='let-op'>let op: " + j.botsingen.aantal +
      (j.botsingen.aantal === 1 ? " label raakt" : " labels raken") + " een buur" +
      (j.botsingen.paren.length
        ? " (" + j.botsingen.paren.map(p => p.join("-")).join(", ") + ")" : "") + "</span>"
    : "";
  zetAspecten(document.getElementById("toon-aspecten").checked);
  // De schakelaar naar de bi-wheel-stand hoort bij dit vak. Eerst de stand bepalen en pas daarna
  // tekenen: bij de kaart van "Nu" valt er niets te transitieren, dus zet `zetWielSchakel()` de
  // schakelaar uit - anders bleef het wiel van de vorige kaart met transits staan.
  zetWielSchakel();
  if (wielStand !== "radix") {
    // Na een nieuwe kaart is het moment leeg: dan opnieuw bevriezen op nu, anders op de gekozen datum.
    if (wielStand === "transits" && !wielMoment) { wmNu(); return; }
    wielTeken();
  }
}

// Sorteren op **planeet** (de stand: de volgorde van de puntenlijst, waarin de paren gemaakt worden) of
// op **orb** (het nauwste aspect bovenaan). Alleen voor deze lijst; papier leest de kaart zelf.
let aspectSortering = "planeet";

// De aspectenlijst: de matrix is van het scherm af en staat alleen nog op de A4,
// als trap. Elk aspect staat één keer in de lijst, bij het eerste van de twee punten; de volgorde is
// die van `k.aspecten` en dat is al de volgorde van de puntenlijst (de kern loopt i < j). De opbouw
// is die van zijn eigen online programma: de twee
// punten, het aspect, de orb en de stand van beide punten.
// Dominante aspecten worden hier niet gemarkeerd: dat is stof voor jaar 2.
// De Noordknoop en de Dagpars doen niet mee, net als in de trap: "Die hebben we in
// de trap bewust weggelaten. Ik denk dat we dit hier ook moeten doen.". Eén regel voor allebei de
// tabellen, zodat scherm en papier niet uit elkaar kunnen lopen: een aspect waarin een van die twee
// voorkomt valt weg.
// `orbDelen` blijft staan: de trap op de A4 gebruikt hem voor de twee regels in een cel.
// Welke punten wegblijven staat **in de kaart** (`k.weg_punt`, besluit T42): de regel
// hoort bij de aspecten en niet bij de weergave, en zo gebruiken de lijst, de trap én de tekenaar
// dezelfde lijst. Hier blijft alleen de lezing over.
function wegPunt(k) { return new Set((k && k.weg_punt) || []); }

function lijstHTML(k) {
  // De stand in drie stukken met elk een eigen breedte. Als één string schuift het
  // zodiacteken de cijfers op: de glyphs zijn samen niet even breed (Tweeling 0,632 em, Kreeft 0,937 em),
  // en dat gaf tot 4,3 px verschil in dezelfde kolom. De cijfers zelf zijn al tabulair (0,513 em).
  const stand = {};
  for (const q of k.punten) {
    const b = q.positie;
    stand[q.naam] = "<span class='dg'>" + String(b.graad).padStart(2, "0") + "°</span>" +
      "<span class='sg'>" + b.glyf + "</span>" +
      "<span class='mn'>" + String(b.minuut).padStart(2, "0") + "'</span>";
  }
  // AC en MC zijn letters, geen glyph; die horen in de letter van de tabel (Selawik 400, 13 px) en niet
  // in Astro Sans, want dat is een 600-letter en dan staat er vet tussen regular.
  const g = (n) => {
    const teken = GLYF[n] || "?";
    return teken.length > 1 ? "<span class='naam'>" + teken + "</span>"
                            : "<span class='glyf'>" + teken + "</span>";
  };
  const weg = wegPunt(k);
  const rijen = k.aspecten.filter((a) => !weg.has(a.p1) && !weg.has(a.p2));
  // Op orb: het nauwste aspect eerst. Delen met dezelfde orb houden hun onderlinge volgorde (de
  // sortering is stabiel), dus de lijst blijft per orb deterministisch.
  if (aspectSortering === "orb") { rijen.sort((a, b) => a.orb - b.orb); }
  let t = "<h2 class='met-sorteer'>Aspecten (" + rijen.length + ")" + aspectSorteerKeuze() +
    "</h2><table class='lijst'><thead><tr>" +
    "<th>Planeet 1</th><th>Aspect</th><th>Planeet 2</th><th class='r'>Orb</th>" +
    "<th class='r'>Stand 1</th><th class='r'>Stand 2</th></tr></thead><tbody>";
  for (const a of rijen) {
    t += "<tr><td>" + g(a.p1) + "</td><td><span class='glyf'>" + a.glyf + "</span></td><td>" +
      // De orb-kolom bestaat uit vier vaste vakken: de twee markeringen, de orb en de A/S. Zonder
      // die vakken schuift de orb op: de rechterrand van de orb liep
      // uiteen, want een B of ◆ erachter duwt hem naar links en de A en de S zijn niet even breed
      // ("zo blijven de orbs netjes onder elkaar staan"). De markeringen staan nu vóór de orb,
      // in dezelfde orde als de noot ze noemt.
      // Een teken dat er niet is, laat ook geen lege plek achter: staat er geen B,
      // dan schuift het ◆ op naar de plek naast de orb. De orb zelf blijft staan waar hij stond, want
      // die is rechts uitgelijnd in zijn eigen vak en de cel is rechts uitgelijnd.
      g(a.p2) + "</td><td class='r orbcel'>" +
      (a.dominant && techniekAan("dominant")
        ? "<span class='mk dom' title='dominant: hard aspect naar de Ascendant of het MC " +
          "binnen 2°'>◆</span>"
        : "") +
      // Stap 2 van het stappenplan: het meest exacte harde aspect tussen twee
      // planeten, zonder een dominante planeet erbij. Een klein rood balletje, zoals hij het vroeg.
      (a.meest_exact && techniekAan("dominant")
        ? "<span class='mk exact' title='het meest exacte harde aspect: tussen twee planeten " +
          "onderling, zonder een dominante planeet erbij'>\u25cf</span>"
        : "") +
      (a.buiten_teken ? "<span class='mk buiten'>B</span>" : "") +
      "<span class='orb'>" + a.orb_afgekapt + "</span>" +
      "<span class='scheidend'>" + a.letter + "</span></td>" +
      "<td class='r pos'>" + (stand[a.p1] || "") + "</td><td class='r pos'>" + (stand[a.p2] || "") +
      "</td></tr>";
  }
  return t + "</tbody></table><p class='lijst-noot'>Elke regel: de twee punten, het aspect, de orb met " +
    "<b>A</b> (ingaand, <i>applying</i>) of <b>S</b> (uitgaand, <i>separating</i>) en de stand van " +
    "beide punten. <b>B</b> = buiten teken: zo'n aspect telt alleen mee bij een orb van hoogstens 2°." +
    (techniekAan("dominant")
      ? " <span class='dom'>◆</span> = dominant: een hard aspect naar de Ascendant of het MC " +
        "binnen 2° orb. <span class='exact'>\u25cf</span> = het meest exacte harde aspect tussen twee " +
        "planeten onderling, zonder een dominante planeet erbij."
      : "") + "</p>";
}

// De twee knoppen in de kop van de lijst. Ze zijn pas zinvol als de techniek aanstaat: zonder dominant
// is er ook geen stap 2, dus dan staat er geen schakelaar (dezelfde grendel als het merkteken).
function aspectSorteerKeuze() {
  if (!techniekAan("dominant")) { return ""; }
  const knop = (waarde, tekst) => "<button type='button' class='tr-startknop" +
    (aspectSortering === waarde ? " aan" : "") + "' data-sorteer='" + waarde + "'>" + tekst + "</button>";
  return "<span class='sorteer'><span class='sorteerlabel'>Sorteren op</span>" +
    knop("planeet", "planeet") + knop("orb", "orb") + "</span>";
}

// De knoppen horen bij de lijst die er net is neergezet, dus na elke tekening opnieuw koppelen. Een klik
// tekent de lijst opnieuw in de gekozen volgorde; de kaart zelf wordt niet opnieuw gerekend.
function koppelSorteer() {
  document.querySelectorAll("#lijstvak [data-sorteer]").forEach(b =>
    b.addEventListener("click", () => {
      const gekozen = b.getAttribute("data-sorteer");
      if (gekozen === aspectSortering) { return; }
      aspectSortering = gekozen;
      if (laatste && laatste.kaart) {
        document.getElementById("lijstvak").innerHTML = lijstHTML(laatste.kaart);
        koppelSorteer();
      }
    }));
}

function orbDelen(orb) {
  const m = String(orb).match(/^(\d+)°(\d+)'/);
  return m ? { deg: m[1], min: m[2] } : { deg: String(orb), min: "" };
}

// De element- en kruisverdeling: twee losse blokken onder één gezamenlijke kop, op het scherm
// naast elkaar en op papier onder elkaar: "het zijn twee verschillende staten,
// niet een aaneengesloten opsomming".
function groepenHTML(ek, op_schem) {
  const rij = (paar) => {
    const naam = KRUIS_NL[paar[0]] || paar[0], d = paar[1];
    return "<tr><th>" + naam + "</th><td>" + d.lichamen.map(glyfVan).join("") +
      (d.hoeken.length ? " <span class='hoeken'>" + d.hoeken.join(" ") + "</span>" : "") +
      "</td></tr>";
  };
  const tabel = (rijen) => "<table class='groepen'>" + rijen.map(rij).join("") + "</table>";
  return "<h2>Elementen en kruisen</h2><div class='tweekolom'>" +
    "<div class='groep'>" + tabel(ek.elementen) + "</div>" +
    "<div class='groep'>" + tabel(ek.kruisen) + "</div></div>";
}

// De heerschappen per huis. De cusp staat hier voluit in DMS met seconden (zoals de planeetstanden
// onder het wiel); het teken en de heerser staan er alleen als glyph, en bij "staat in" alleen het
// huisnummer — de positie van die planeet staat immers al in de standentabel.
function heerschappenHTML(h, k) {
  const lengtes = new Map(((k && k.huizen) || []).map(x => [x.nr, x.positie.lengte]));
  const rij = (r) => {
    const glyf = glyfTeken(r.teken);
    // Dezelfde notatie als overal: graad, tekenglyph, minuut, seconde.
    const cusp = lengtes.has(r.huis) ? standTekst(lengtes.get(r.huis), glyf)
                                     : glyf + " " + esc(r.cusp);
    return "<tr><th>huis " + r.huis + "</th><td class='pos'>" + cusp + "</td><td>" +
      glyfVan(r.heerser) + "</td><td>" +
      (r.heerser_huis ? "huis " + r.heerser_huis : "-") + "</td></tr>";
  };
  const kop = "<thead><tr><th></th><th>cusp</th><th>heerser</th><th>staat in</th></tr></thead>";
  const helft = (rijen) => "<table class='groepen heerschappen'>" + kop +
    "<tbody>" + rijen.map(rij).join("") + "</tbody></table>";
  const n = Math.ceil(h.per_huis.length / 2);
  return "<div class='blokken'>" + helft(h.per_huis.slice(0, n)) + helft(h.per_huis.slice(n)) + "</div>";
}

function toevoegingenHTML(j, op_papier) {
  let h = "";
  if (j.element_kruis) {
    h += "<div>" + groepenHTML(j.element_kruis, !op_papier) + "</div>";
  }
  if (j.heerschappen && !op_papier) {
    h += "<div><h2>Heerschappen (modern)</h2>" + heerschappenHTML(j.heerschappen, j.kaart) + "</div>";
  }
  // Onder elkaar, niet naast elkaar: de huizen en heerschappen staan onder de
  // element- en kruisverdeling. De heerschappen zelf houden hun twee helften wél naast elkaar —
  // dat is de aparte `.blokken` binnenin.
  return h ? "<div class='stapel'>" + h + "</div>" : "";
}

function zetAspecten(aan) {
  document.getElementById("wielvak").classList.toggle("geen-aspecten", !aan);
}

async function laadBron() {
  try {
    const r = await fetch("/api/plaatsen");
    const j = await r.json();
    if (j.zones && j.zones.length) {
      // De keuzelijst van het tijdzoneveld: de namen die de plaatsenlijst zelf gebruikt.
      document.getElementById("zones").innerHTML =
        j.zones.map((z) => "<option value='" + esc(z) + "'></option>").join("");
    }
    if (j.bron && j.bron.aantal) {
      // De regel staat in de Over-tab in plaats van onder het formulier, met de datum voluit in
      // plaats van het ruwe veld uit het databestand.
      document.getElementById("over-plaatsen").textContent = "De meegeleverde database bevat " +
        j.bron.aantal.toLocaleString("nl-NL") + " plaatsen en is samengesteld op " +
        langeDatum(j.bron.gebouwd) + ".";
    }
  } catch (e) { /* de regel blijft dan staan zoals hij is */ }
}
// --- Het venster: menubalk, werkbalk en sneltoetsen ------------------------------
//
// Eén regel per handeling: een menu-item of een werkbalkknop klikt het element aan dat de handeling
// al doet, of roept de functie aan die er al is. Zo kan er geen knop in het venster staan die nog
// moet komen, en is er geen tweede waarheid per handeling (dezelfde afspraak als bij de plaatszoeker).

function zetStatusKaart(k) {
  const cel = document.getElementById("status-kaart");
  if (!cel) { return; }
  if (!k || !k.meta) { cel.textContent = ""; return; }
  cel.textContent = k.meta.naam + " · " + alsNederlands(k.meta.datum) + " " + k.meta.tijd;
}

// Een leeg scherm horen bij een lege kaart: het wiel, de standen, de aspectenlijst, de toevoegingen,
// het A4-blad en de gegevens horen bij de kaart die er stond. Blijft de tekening van de vorige kaart
// staan, dan lijkt het of het lege formulier daar bij hoort.
function leegScherm(waarom) {
  laatste = null;
  wielStand = "radix";
  wielMoment = null;
  wlGekozen = false;
  wlLaatste = null;
  wmStempel = "";
  zetStatusKaart(null);
  zetWielBeeld("<p class='leegvlak'>Nog geen horoscoop berekend.<br>Vul de gegevens links in en " +
    "druk op Berekenen (F9).</p>");
  // Een leeg paneel met alleen een kader leest als een fout; één regel zegt wat er aan de hand is.
  document.getElementById("gegevens").innerHTML =
    "<p class='leegvlak' style='padding:6px 0'>nog geen horoscoop berekend</p>";
  document.getElementById("lijstvak").innerHTML = "";
  document.getElementById("toevoegingen").innerHTML = "";
  document.getElementById("standen").innerHTML = "";
  document.getElementById("kruis").innerHTML = "";
  const blad = document.getElementById("afdruk");
  blad.innerHTML = "";
  blad.classList.remove("vast");
  drukBi = false;
  drukBeeld = null;
  zetDrukSchakel();
  actiefId = null;
  zetBewaarKnop();
  zetMeld("", waarom || "");
}

// Nieuw: een lege kaart. De locatie blijft staan — dat is de plaats van het programma, en bij een
// reeks kaarten uit dezelfde plaats scheelt dat typen. Naam, datum en tijd zijn leeg, want dat is
// juist wat je per kaart invult.
async function nieuwKaart() {
  if (vies) {
    const door = await bericht({ titel: "Nieuwe horoscoop",
      tekst: "De ingevulde gegevens zijn nog niet bewaard. Een nieuwe horoscoop beginnen?",
      ja: "Nieuwe horoscoop", nee: "Annuleren" });
    if (!door) { return; }
  }
  // Ook de locatie leeg: met de standaardplaats er nog in kon iemand berekenen
  // met een plaats die hij niet zelf gekozen had, en dat is erger dan een keer extra typen. De
  // plaats van het programma blijft bestaan voor "Horoscoop van dit moment"; een nieuwe horoscoop
  // begint leeg, met ook het zoekveld en de suggestielijst schoon.
  ["naam", "datum", "tijd", "plaats", "lat", "lon", "tz"].forEach(id => {
    document.getElementById(id).value = "";
  });
  document.getElementById("plaatsen").innerHTML = "";
  document.getElementById("correctie").value = "";
  coordDms("lat", "lon", "dms");
  zetTab("wiel");
  leegScherm("nieuwe horoscoop: vul naam, datum, tijd en plaats in.");
  document.getElementById("naam").focus();
  vies = false;
  klokStop();             // een leeg formulier is geen "nu"
  trActualiseer();        // geen kaart: de transits-tab gaat uit en de lijst is weg
  zetSolaarMenu();        // en de solaar-regel ook uit
}

// De kaart van dit moment: dezelfde weg als het openen van het programma (tijd van de server,
// locatie uit de instellingen). Dit deed Nieuw hiervoor, en het is een eigen handeling.
async function nuKaart() {
  if (vies) {
    const door = await bericht({ titel: "Horoscoop van dit moment",
      tekst: "De ingevulde gegevens zijn nog niet bewaard. De horoscoop van dit moment openen?",
      ja: "Doorgaan", nee: "Annuleren" });
    if (!door) { return; }
  }
  const uit = await laadInstellingen();
  if (!uit || !uit.instellingen) { return; }
  vulNu(uit.instellingen, uit.nu);
  actiefId = null;
  zetBewaarKnop();
  zetTab("wiel");
  await reken();
  klokStart();            // terug bij "Nu": de klok loopt weer
}
