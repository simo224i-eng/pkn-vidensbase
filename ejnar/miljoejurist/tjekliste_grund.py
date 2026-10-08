"""Tjeklistens grundpunkter: krav fra loven og vejledningen.

Hvert punkt har:
- id, titel og spørgsmål (det sagsbehandleren skal kunne svare ja til),
- gælder: dokumenttyper (screening_projekt, screening_plan, miljoerapport_plan, projekttilladelse),
- fejlkategorier: kategorier fra trin 2 (analyser/miljoevurdering/v2), som punktet skal forebygge,
- lov: [(kode, nr, uddrag)] – uddrag skal stå ordret i lovteksten (kontrolleres i test),
- vejl_søg: søgeord til at finde vejledningens afsnit (lovkilder.søg),
- dækket: regex, der viser, at dokumentet behandler emnet,
- svagt: regex for typiske svage formuleringer (vurdering uden grundlag),
- kræver: regex, hvoraf mindst ét skal findes, når emnet er behandlet (fx en begrundelse),
- relevant_hvis: regex på dokumentet, der gør punktet relevant (tom = altid relevant),
- søg: forespørgsel til lignende afgørelser.

Regex er skrevet til dansk sagsbehandlersprog. De er bevidst brede: værktøjet peger på steder,
som en fagperson skal se på; det afgør ikke, om noget er lovligt.

Byg den færdige tjekliste med `python -m miljoejurist.byg_tjekliste` (kobler hyppigheder og
eksempler fra nævnspraksis på).
"""

ALLE_SCREENINGER = ["screening_projekt", "screening_plan"]
ALLE = ["screening_projekt", "screening_plan", "miljoerapport_plan", "projekttilladelse"]

# Ord, der viser en begrundelse (årsag, grundlag, målestok)
BEGRUNDELSE = (r"\b(fordi|idet|da (der|det|projektet|planen|området|arealet)|på baggrund af|på grund af|"
               r"baseret på|ud fra|jf\.|beregn\w*|målt|målinger|undersøgelse\w*|kortlæg\w*|besigtig\w*|"
               r"registrer\w*|afstand\w*|\d+\s?(m|meter|km|ha|m2|m²|dB|%)\b|kilde|rapport|notat)")

PUNKTER = [
    # ---------- A. Er planen/projektet omfattet, og er det afgrænset rigtigt ----------
    {
        "id": "A1", "gruppe": "Omfattet og afgrænsning",
        "titel": "Korrekt placering i lovens bilag og projektbegreb",
        "spørgsmål": "Er det begrundet, hvilket punkt i bilag 1 eller 2 projektet hører under (eller hvorfor "
                     "det ikke er omfattet), herunder om der er tale om en ændring eller udvidelse (bilag 2, pkt. 13)?",
        "gælder": ["screening_projekt", "projekttilladelse"],
        "fejlkategorier": ["omfattet_bilag_projektbegreb"],
        "lov": [("mvl", "§ 16", "Et projekt omfattet af bilag 2 må ikke påbegyndes"),
                ("mvl", "§ 21", "afgørelse om, hvorvidt et projekt omfattet af bilag 2")],
        "vejl_søg": "projektbegrebet bilag 2 punkt ændringer udvidelser",
        "dækket": r"bilag (1|2)\b|bilag (I|II)\b|punkt \d+\s?,?\s?litra|pkt\. \d+",
        "svagt": r"ikke omfattet af (miljøvurderingsloven|loven|reglerne)|ikke er omfattet af (miljøvurderingsloven|loven|reglerne)|falder uden for",
        "kræver": r"bilag 2,? (pkt|punkt)\.? ?\d+|bilag 1,? (pkt|punkt)\.? ?\d+",
        "relevant_hvis": "",
        "søg": "projektet er omfattet af bilag 2 punkt projektbegreb ændring udvidelse",
    },
    {
        "id": "A2", "gruppe": "Omfattet og afgrænsning",
        "titel": "Hele projektet er vurderet (ingen opsplitning)",
        "spørgsmål": "Omfatter screeningen hele projektet, inkl. tilhørende anlæg, veje, ledninger, anlægsfase, "
                     "drift og senere etaper, så projektet ikke er opsplittet?",
        "gælder": ["screening_projekt", "projekttilladelse", "screening_plan"],
        "fejlkategorier": ["afgraensning_opsplitning"],
        "lov": [("mvl", "bilag 6", "hele projektets dimensioner og udformning")],
        "vejl_søg": "opsplitning af projekter salamimetoden hele projektet",
        "dækket": r"anlægsfase|anlægsperiode|driftsfase|etape|tilhørende|adgangsvej|tilkørsel|ledning|kabel|samlet projekt|hele projektet",
        "svagt": r"(indgår|behandles|vurderes) ikke i (denne|nærværende) (screening|ansøgning)|separat (ansøgning|sag|screening)|særskilt (ansøgning|sag|screening)|senere etape",
        "kræver": r"anlægsfase|anlægsperiode|drift",
        "relevant_hvis": "",
        "kun_svagt": True,
        "søg": "projektet opsplittet hele projektet tilhørende anlæg vurderet samlet",
    },
    {
        "id": "A3", "gruppe": "Omfattet og afgrænsning",
        "titel": "Planen: miljøvurdering eller screening (§ 8)",
        "spørgsmål": "Er det vurderet, om planen fastlægger rammer for projekter i bilag 1 eller 2, og om den kun "
                     "fastlægger anvendelsen af mindre områder på lokalt plan (§ 8, stk. 2, nr. 1)?",
        "gælder": ["screening_plan"],
        "fejlkategorier": ["omfattet_bilag_projektbegreb"],
        "lov": [("mvl", "§ 8", "fastlægger rammerne for fremtidige anlægstilladelser"),
                ("mvl", "§ 8", "kun fastlægger anvendelsen af mindre områder på lokalt plan")],
        "vejl_søg": "mindre områder på lokalt plan mindre ændringer screening af planer",
        "dækket": r"§ ?8|mindre områder? på lokalt plan|mindre ændring|rammer for (fremtidige )?anlægstilladelser|bilag (1|2)",
        "svagt": "",
        "kræver": r"mindre områder? på lokalt plan|mindre ændring|§ ?8,? stk\. ?2",
        "relevant_hvis": "",
        "søg": "lokalplan mindre område på lokalt plan rammer for anlægstilladelser bilag 1 og 2",
    },
    # ---------- B. Oplysningsgrundlag og høring ----------
    {
        "id": "B1", "gruppe": "Oplysningsgrundlag",
        "titel": "Tilstrækkeligt oplysningsgrundlag",
        "spørgsmål": "Bygger vurderingerne på konkrete oplysninger (ansøgningens bilag 5-oplysninger, kort, "
                     "beregninger, registreringer), og fremgår det, hvor oplysningerne kommer fra?",
        "gælder": ALLE,
        "fejlkategorier": ["sagsoplysning_dokumentation"],
        "lov": [("mvl", "§ 19", "indgive en skriftlig ansøgning"),
                ("mvl", "bilag 5", "Oplysninger fra bygherren")],
        "vejl_søg": "oplysningsgrundlag officialprincippet tilstrækkelige oplysninger screening",
        "dækket": BEGRUNDELSE,
        "svagt": r"(forventes|vurderes|antages|skønnes) (ikke )?at|ikke (kendskab|oplysninger) om|ikke (registreret|kendt)|ingen (viden|oplysninger)",
        "kræver": BEGRUNDELSE,
        "relevant_hvis": "",
        "søg": "kommunen havde ikke tilstrækkeligt grundlag oplysninger undersøgt officialprincippet",
    },
    {
        "id": "B2", "gruppe": "Oplysningsgrundlag",
        "titel": "Høring af berørte myndigheder",
        "spørgsmål": "Er berørte myndigheder hørt før afgørelsen, og er deres bemærkninger inddraget "
                     "(§ 32 for planer, § 35 for projekter)?",
        "gælder": ["screening_plan", "miljoerapport_plan"],
        "fejlkategorier": ["hoering_inddragelse"],
        "lov": [("mvl", "§ 32", "skal sikre, at følgende informeres tidligt i beslutningsprocessen"),
                ("mvl", "§ 10", "resultaterne af høringerne efter § 32")],
        "vejl_søg": "høring af berørte myndigheder screeningsafgørelse",
        "dækket": r"høring|hørt|berørte myndigheder|Miljøstyrelsen|Vejdirektoratet|Kystdirektoratet|Slots- og Kulturstyrelsen|museum",
        "svagt": "",
        "kræver": r"berørte myndigheder|myndigheds?høring|(er|blev) hørt",
        "relevant_hvis": "",
        "søg": "høring af berørte myndigheder inden screeningsafgørelse",
    },
    # ---------- C. Screeningskriterierne (bilag 6 / bilag 3) ----------
    {
        "id": "C1", "gruppe": "Screeningskriterier",
        "titel": "Alle relevante kriterier i bilag 6 (projekter) er vurderet",
        "spørgsmål": "Er hvert relevant kriterium i bilag 6 (projektets karakteristika, placering og "
                     "påvirkningens art) vurderet konkret, og er afgørelsen begrundet med henvisning til dem?",
        "gælder": ["screening_projekt"],
        "fejlkategorier": ["screeningskriterier_ikke_vurderet", "begrundelse"],
        "lov": [("mvl", "§ 21", "Ved vurderingen skal myndigheden tage hensyn til kriterierne i bilag 6"),
                ("mvl", "§ 21", "henvisning til de i bilag 6 opførte relevante kriterier")],
        "vejl_søg": "screeningskriterierne i bilag 6",
        "dækket": r"bilag 6|kriteri",
        "svagt": "",
        "kræver": r"bilag 6",
        "relevant_hvis": "",
        "søg": "screeningskriterier bilag 6 ikke vurderet begrundelse henvisning til kriterierne",
    },
    {
        "id": "C2", "gruppe": "Screeningskriterier",
        "titel": "Alle relevante kriterier i bilag 3 (planer) er vurderet",
        "spørgsmål": "Er de relevante kriterier i bilag 3 vurderet konkret, og fremgår begrundelsen af den "
                     "offentliggjorte afgørelse (§ 10 og § 33)?",
        "gælder": ["screening_plan"],
        "fejlkategorier": ["screeningskriterier_ikke_vurderet", "begrundelse"],
        "lov": [("mvl", "§ 10", "inddrage de relevante kriterier i bilag 3"),
                ("mvl", "§ 33", "skal offentliggøres med begrundelse")],
        "vejl_søg": "screening af planer kriterierne i bilag 3 begrundelse",
        "dækket": r"bilag 3|kriteri",
        "svagt": "",
        "kræver": r"bilag 3",
        "relevant_hvis": "",
        "søg": "screening af lokalplan kriterierne i bilag 3 begrundelse",
    },
    {
        "id": "C3", "gruppe": "Screeningskriterier",
        "titel": "Kumulation med andre projekter og planer",
        "spørgsmål": "Er det konkret vurderet, hvilke eksisterende og godkendte projekter/planer i området "
                     "påvirkningen kan lægge sig oven i, og hvad den samlede påvirkning bliver?",
        "gælder": ALLE,
        "fejlkategorier": ["kumulation"],
        "lov": [("mvl", "bilag 6", "kumulation med andre eksisterende og/eller godkendte projekter"),
                ("mvl", "bilag 3", "indvirkningens kumulative karakter")],
        "vejl_søg": "kumulation med andre eksisterende og godkendte projekter",
        "dækket": r"kumul|samlede? påvirkning|sammen med (andre|øvrige)|i forbindelse med andre (planer|projekter)|i kombination med",
        "svagt": r"(ingen|ikke) (kendskab til|kendte) (andre )?(projekter|planer)|ikke relevant|ingen kumul",
        "kræver": r"(projekt|plan|anlæg|vindmølle|solcelle|lokalplan|tilladelse)\w*",
        "relevant_hvis": "",
        "søg": "kumulation med andre projekter ikke vurderet samlede påvirkning",
    },
    {
        "id": "C4", "gruppe": "Screeningskriterier",
        "titel": "Forurening og gener: støj, lys, lugt, støv, trafik",
        "spørgsmål": "Er gener for omgivelserne (støj, vibrationer, lys, lugt, støv, trafik) vurderet med "
                     "konkrete tal eller vejledende grænseværdier og afstande til nærmeste naboer?",
        "gælder": ALLE,
        "fejlkategorier": ["screeningskriterier_ikke_vurderet", "materiel_vaesentlighed"],
        "lov": [("mvl", "bilag 6", "forurening og gener")],
        "vejl_søg": "forurening og gener støj screening",
        "dækket": r"støj|lys(gener|forurening|påvirkning)?|lugt|støv|vibration|trafik",
        "svagt": r"(støj|gener|trafik)\w*[^.]{0,80}(forventes|vurderes|antages) (ikke|at være begrænset|ubetydelig)",
        "kræver": r"dB|grænseværdi|vejledende|beregn|afstand|meter|\d+\s?m\b|biler|køretøjer|ÅDT|døgn",
        "relevant_hvis": "",
        "emne": r"støj|lys|lugt|støv|trafik|gener|vibration",
        "søg": "støj gener naboer ikke vurderet grænseværdier screening",
    },
    {
        "id": "C5", "gruppe": "Screeningskriterier",
        "titel": "Landskab, kulturarv og visuel påvirkning",
        "spørgsmål": "Er påvirkningen af landskab, kystlandskab, kulturmiljø, fortidsminder og kirker vurderet "
                     "konkret (fx med visualiseringer og afstande)?",
        "gælder": ALLE,
        "fejlkategorier": ["screeningskriterier_ikke_vurderet", "materiel_vaesentlighed"],
        "lov": [("mvl", "bilag 6", "landskaber og lokaliteter af historisk, kulturel eller arkæologisk betydning")],
        "vejl_søg": "landskab kulturarv visuel påvirkning kirker",
        "dækket": r"landskab|kulturarv|kulturmiljø|fortidsminde|kirke|visualiser|udsigt|kystnær",
        "svagt": r"(landskab|visuel)\w*[^.]{0,80}(forventes|vurderes) (ikke|at være begrænset)",
        "kræver": r"visualiser|afstand|meter|højde|\d+\s?m\b|synlig",
        "relevant_hvis": r"landskab|kyst|kirke|fredning|vindmølle|solcelle|højde|byggeri|bygning",
        "emne": r"landskab|visuel|kulturarv|kulturmiljø|kirke|fortidsminde|kystnær",
        "søg": "landskabelig påvirkning visualiseringer kystnærhedszonen kirker ikke vurderet",
    },
    {
        "id": "C6", "gruppe": "Screeningskriterier",
        "titel": "Vand: grundvand, vandløb, søer, kyst og miljømål",
        "spørgsmål": "Er påvirkningen af grundvand (drikkevandsinteresser), overfladevand og målopfyldelsen i "
                     "vandområdeplanerne vurderet?",
        "gælder": ALLE,
        "fejlkategorier": ["screeningskriterier_ikke_vurderet", "sagsoplysning_dokumentation"],
        "lov": [("mvl", "bilag 6", "miljøkvalitetsnormer")],
        "vejl_søg": "vandområdeplaner miljømål grundvand screening",
        "dækket": r"grundvand|drikkevand|vandløb|vandområdeplan|miljømål|målopfyldelse|recipient|udledning|nedsivning|regnvand|søer?\b",
        "svagt": "",
        "kræver": r"vandområdeplan|miljømål|målsætning|OSD|drikkevandsinteresser|indvindingsopland|recipient",
        "relevant_hvis": r"grundvand|drikkevand|vandløb|udledning|spildevand|regnvand|dræn|indvinding|\bsø\b|søer|\bå\b|fjord|vådområde|boring|nedsivning",
        "emne": r"vand|grundvand|vandløb|miljømål|udledning|recipient|drikkevand",
        "søg": "påvirkning af vandområde miljømål vandområdeplan grundvand ikke vurderet",
    },
    # ---------- D. Natur ----------
    {
        "id": "D1", "gruppe": "Natur",
        "titel": "Natura 2000: væsentlighedsvurdering",
        "spørgsmål": "Er det vurderet, om planen/projektet alene eller sammen med andre kan påvirke et Natura "
                     "2000-område væsentligt, ud fra områdets udpegningsgrundlag, afstand og påvirkningsveje "
                     "(fx hydrologi, kvælstof, forstyrrelse) – og uden at lægge afværgeforanstaltninger til grund?",
        "gælder": ALLE,
        "fejlkategorier": ["natura2000_vaesentlighed"],
        "lov": [("habitatbek", "§ 6", "kan påvirke et Natura 2000-område væsentligt"),
                ("planlov_habitat_bek", "§ 3", "kan påvirke et Natura 2000-område væsentligt")],
        "vejl_søg": "væsentlighedsvurdering Natura 2000 udpegningsgrundlag",
        "dækket": r"Natura ?2000|habitatområde|fuglebeskyttelsesområde|internationalt naturbeskyttelsesområde|N\d{1,3}\b",
        "svagt": r"(ligger|beliggende) (ca\.? )?\d+[\d.,]*\s?(m|km|meter)[^.]{0,80}(derfor|hvorfor|ikke)|på grund af afstanden",
        "kræver": r"udpegningsgrundlag|bevaringsmålsætning|naturtype|arter på udpegningsgrundlaget|kvælstof|deposition|hydrolog|forstyrr",
        "relevant_hvis": "",
        "søg": "væsentlighedsvurdering Natura 2000 udpegningsgrundlag ikke vurderet afstand",
    },
    {
        "id": "D2", "gruppe": "Natur",
        "titel": "Bilag IV-arter: yngle- og rasteområder",
        "spørgsmål": "Er det undersøgt, hvilke bilag IV-arter der kan forekomme i området (kendt viden og om "
                     "nødvendigt besigtigelse), og vurderet, om yngle- eller rasteområder kan beskadiges eller "
                     "ødelægges, så den økologiske funktionalitet påvirkes?",
        "gælder": ALLE,
        "fejlkategorier": ["bilagIV_arter"],
        "lov": [("habitatbek", "§ 10", "beskadige eller ødelægge yngle- eller rasteområder"),
                ("habitatbek", "§ 10", "Vurderingen skal fremgå af de afgørelser"),
                ("planlov_habitat_bek", "§ 7", "beskadige eller ødelægge yngle- eller rasteområder")],
        "vejl_søg": "bilag IV-arter yngle- og rasteområder økologisk funktionalitet",
        "dækket": r"bilag IV|bilag 4-art|yngle- og raste|raste- og yngle|økologisk funktionalitet|flagermus|markfirben|stor vandsalamander|odder|spidssnudet frø|løgfrø|birkemus|strandtudse",
        "svagt": r"ikke (kendskab|kendte?|registreret|registrerede)[^.]{0,60}(bilag IV|arter|forekomst)|ingen (kendte|registrerede) (forekomster|bilag IV)|ikke (kendskab til|viden om) (forekomst|bilag)",
        "kræver": r"yngle|raste|økologisk funktionalitet|besigtig|undersøg|kortlæg|udbredelse|Arter\.dk|DCE|NOVANA",
        "relevant_hvis": "",
        "søg": "bilag IV-arter yngle- og rasteområder ikke undersøgt økologisk funktionalitet",
    },
    {
        "id": "D3", "gruppe": "Natur",
        "titel": "§ 3-natur, fredninger, beskyttelseslinjer og anden natur",
        "spørgsmål": "Er påvirkningen af § 3-beskyttet natur, fredede arealer, skov, beskyttelseslinjer og "
                     "biodiversitet i øvrigt vurderet, herunder indirekte påvirkning (fx dræning, kvælstof)?",
        "gælder": ALLE,
        "fejlkategorier": ["natur_paragraf3"],
        "lov": [("mvl", "bilag 6", "områder, der er registreret eller fredet ved national lovgivning")],
        "vejl_søg": "§ 3-beskyttet natur screening påvirkning",
        "dækket": r"§ ?3|beskyttet natur|beskyttede naturtyper|fredning|fredet|skovbyggelinje|åbeskyttelseslinje|sø- og å|strandbeskyttelse|biodiversitet|eng|mose|overdrev",
        "svagt": r"(natur)\w*[^.]{0,60}(forventes|vurderes) ikke",
        "kræver": r"afstand|meter|\d+\s?m\b|besigtig|registrer|kortlæg|indirekte|kvælstof|dræn|hydrolog",
        "relevant_hvis": r"§ ?3|beskyttet|fredning|fredet|skov|mose|\beng\b|overdrev|hede|strandeng|biodiversitet|vandløb|\bsø\b",
        "emne": r"§ ?3|beskyttet natur|naturtype|fredning|skov|biodiversitet|natur",
        "søg": "§ 3-beskyttet natur påvirkning ikke vurderet screening",
    },
    # ---------- E. Afværgeforanstaltninger, begrundelse og afgørelse ----------
    {
        "id": "E1", "gruppe": "Begrundelse og afgørelse",
        "titel": "Afværgeforanstaltninger er konkrete og sikrede",
        "spørgsmål": "Hvis konklusionen bygger på afværgeforanstaltninger: er de beskrevet af bygherren, "
                     "konkrete og sikret (vilkår, lokalplanbestemmelse), og er de ikke brugt i Natura 2000-"
                     "væsentlighedsvurderingen?",
        "gælder": ALLE,
        "fejlkategorier": ["afvaergeforanstaltninger"],
        "lov": [("mvl", "§ 21", "hvilke foranstaltninger der påtænkes truffet for at undgå eller forebygge")],
        "vejl_søg": "afværgeforanstaltninger screeningsafgørelse vilkår",
        "dækket": r"afværge|afbødende|foranstaltning|tiltag|vilkår|forudsætning",
        "svagt": r"(bør|kan|forventes at|vil blive|anbefales)[^.]{0,60}(afværge|tiltag|foranstaltning|hensyn)|forudsættes",
        "kræver": r"vilkår|bindende|lokalplanens? (§|bestemmelse)|skal|fastsættes",
        "relevant_hvis": r"afværge|afbødende|foranstaltning|tiltag|forudsæt",
        "søg": "afværgeforanstaltninger ikke sikret vilkår screening ikke miljøvurderingspligt",
    },
    {
        "id": "E2", "gruppe": "Begrundelse og afgørelse",
        "titel": "Konklusionen er begrundet",
        "spørgsmål": "Står der for hver vurdering, hvorfor påvirkningen ikke er væsentlig (fakta, målestok, "
                     "afstand), og ikke kun en konklusion?",
        "gælder": ALLE,
        "fejlkategorier": ["begrundelse", "materiel_vaesentlighed"],
        "lov": [("mvl", "§ 21", "Afgørelsen skal begrundes med hovedårsagerne til afgørelsen")],
        "vejl_søg": "begrundelse screeningsafgørelse hovedårsagerne",
        "dækket": r"vurderes|vurdering|konklusion|samlet",
        "svagt": r"(vurderes|forventes|antages|skønnes) (ikke )?at (have|få|medføre|give|påvirke)[^.]{0,80}(væsentlig|nævneværdig|betydelig)",
        "kræver": BEGRUNDELSE,
        "relevant_hvis": "",
        "søg": "screeningsafgørelsen ikke tilstrækkeligt begrundet konklusion uden begrundelse",
    },
    {
        "id": "E3", "gruppe": "Begrundelse og afgørelse",
        "titel": "Klar afgørelse, offentliggørelse og klagevejledning",
        "spørgsmål": "Fremgår det klart, at der er truffet en afgørelse efter § 21 (projekter) eller § 10 "
                     "(planer), hvad den omfatter, og at den offentliggøres med klagevejledning?",
        "gælder": ALLE_SCREENINGER,
        "fejlkategorier": ["kompetence_procedure"],
        "lov": [("mvl", "§ 36", "Myndigheden skal offentliggøre en afgørelse efter § 21"),
                ("mvl", "§ 33", "skal offentliggøres med begrundelse")],
        "vejl_søg": "screeningsafgørelse offentliggørelse klagevejledning",
        "dækket": r"afgørelse|klagevejledning|klagefrist|offentliggør",
        "svagt": "",
        "kræver": r"klage(vejledning|frist|adgang)|kan påklages",
        "relevant_hvis": "",
        "søg": "indirekte afgørelse ikke miljøvurderingspligt manglende screeningsafgørelse",
    },
    # ---------- F. Miljørapport (planer) og G. tilladelse ----------
    {
        "id": "F1", "gruppe": "Miljørapport",
        "titel": "Miljørapportens indhold: alternativer, 0-alternativ og kumulation",
        "spørgsmål": "Indeholder miljørapporten rimelige alternativer, 0-alternativet, kumulative virkninger, "
                     "afværgeforanstaltninger og overvågning (bilag 4)?",
        "gælder": ["miljoerapport_plan"],
        "fejlkategorier": ["miljoerapport_mangelfuld"],
        "lov": [("mvl", "§ 12", "rimelige alternativer"),
                ("mvl", "bilag 4", "Oplysninger omhandlet i § 12")],
        "vejl_søg": "miljørapportens indhold rimelige alternativer 0-alternativ overvågning",
        "dækket": r"alternativ|0-alternativ|nulalternativ|overvågning",
        "svagt": "",
        "kræver": r"alternativ",
        "relevant_hvis": "",
        "søg": "miljørapport mangler alternativer 0-alternativ kumulative virkninger",
    },
    {
        "id": "G1", "gruppe": "Tilladelse",
        "titel": "Vilkår er klare, håndhævelige og dækker de væsentlige påvirkninger",
        "spørgsmål": "Er vilkårene i tilladelsen præcise, målbare og håndhævelige, og dækker de de "
                     "påvirkninger og foranstaltninger, miljøkonsekvensrapporten forudsætter (§ 27)?",
        "gælder": ["projekttilladelse"],
        "fejlkategorier": ["vilkaar"],
        "lov": [("mvl", "§ 27", "indeholde alle de miljømæssige betingelser, der er knyttet til afgørelsen")],
        "vejl_søg": "vilkår i § 25-tilladelse",
        "dækket": r"vilkår",
        "svagt": r"så vidt muligt|bør|tilstræbes|i videst muligt omfang",
        "kræver": r"vilkår",
        "relevant_hvis": "",
        "søg": "vilkår i VVM-tilladelse uklare utilstrækkelige ophævet",
    },
]

# Hvad værktøjet ikke vurderer (vises altid i rapporten)
IKKE_VURDERET = [
    "Om faktum i dokumentet er rigtigt (afstande, arealer, beregninger, artsfund). Værktøjet læser kun teksten.",
    "Kort, tegninger, bilag og billeder, som ikke er en del af den uploadede tekst.",
    "Om konklusionen om væsentlighed er rigtig. Værktøjet peger kun på steder, hvor grundlaget kan være svagt.",
    "Andre lovkrav end dem på tjeklisten, fx planlovens indholdskrav, byggeloven og lokale planbestemmelser.",
    "Nyere praksis eller lovændringer efter datagrundlagets dato (se 'Datagrundlag').",
    "Forhold, som kun fremgår af sagens øvrige akter (ansøgning, høringssvar, notater).",
]
