# Trin 2b: hvad fandt nævnet tilstrækkeligt? (stadfæstede sager)

Du får en liste af sags-id'er, hvor nævnet **stadfæstede** (klager fik ikke medhold). For hvert id læser du
nævnets vurdering i `analyser/miljoevurdering/v2/sager/<id>.txt` med Read (lange filer: læs i bidder med
offset/limit; nævnets vurdering står under overskrifter som "## ... Planklagenævnets vurdering",
"## ... bemærkninger og afgørelse", "## Miljø- og Fødevareklagenævnets vurdering"). Læs sagsfremstillingen
kun så meget, at du forstår, hvad myndigheden gjorde.

Formålet er at lære et værktøj forskellen på en vurdering, der er **tynd, men lovlig**, og en, der er
**mangelfuld**. Find derfor hvert klagepunkt, nævnet afviste, og hvorfor nævnet fandt myndighedens vurdering
tilstrækkelig.

Skriv én JSON-linje pr. sag til den outputfil, du får oplyst (append, ingen anden tekst):

```json
{"id": "...",
 "dokumenttype": "screening_projekt|screening_plan|miljoerapport_plan|projekttilladelse|andet",
 "projekttype": "bolig_byudvikling|vand_natur_klima|fritid_turisme|vindmoeller|solceller|energi_oevrig|erhverv_industri|vej_infrastruktur|raastof|husdyr_landbrug|andet",
 "holdt": [
   {"tjekpunkt": "<id fra listen nedenfor>",
    "klagepunkt": "hvad klager påstod var mangelfuldt (1 sætning)",
    "myndigheden_gjorde": "hvad myndigheden konkret havde vurderet/oplyst (1-2 sætninger, så konkret som muligt: fx 'oplyste afstand 2,5 km til Natura 2000 og at projektet ikke udleder kvælstof')",
    "hvorfor_tilstraekkeligt": "nævnets begrundelse for, at det var nok (1-2 sætninger)",
    "citat_naevn": "ordret fra NÆVNETS VURDERING (1-3 sætninger)"}
 ],
 "resume": "1-2 sætninger: sagen og hvorfor den holdt"}
```

Tjekpunkter (brug id'et):
A1 korrekt placering i lovens bilag og projektbegreb · A2 hele projektet vurderet (ingen opsplitning) ·
A3 plan: miljøvurdering eller screening (§ 8) · A4 screening efter påbegyndt projekt (lovliggørelse) ·
B1 tilstrækkeligt oplysningsgrundlag · B2 høring af berørte myndigheder · B3 rigtigt udgangspunkt (referencetilstand) ·
C1 bilag 6-kriterier (projekter) · C2 bilag 3-kriterier (planer) · C3 kumulation · C4 støj, lys, lugt, støv, trafik ·
C5 landskab, kulturarv, visuel påvirkning · C6 vand (grundvand, vandløb, søer, kyst, miljømål) ·
D1 Natura 2000 · D2 bilag IV-arter · D3 § 3-natur, fredninger, beskyttelseslinjer ·
E1 afværgeforanstaltninger · E2 konklusionen er begrundet · E3 afgørelse, offentliggørelse, klagevejledning ·
F1 miljørapportens indhold (alternativer, 0-alternativ, kumulation, overvågning) · G1 vilkår ·
X andet (fx planlov, forhold uden for nævnets kompetence)

Regler:
- Tag alle afviste klagepunkter med, der handler om miljøvurderingen (højst 8 pr. sag). Klagepunkter, nævnet
  afviste at behandle (uden for kompetence), markeres X.
- `citat_naevn` skal stå ordret i filen (tegn for tegn; kun forkortet med "[…]"). Kontrollér det. Hellere null.
- Skriv kun det, nævnet faktisk siger. Ingen personnavne, adresser eller matrikelnumre.
