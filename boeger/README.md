# Bøger / Bibliotek

Denne mappe indeholder bøgerne der vises i **Bibliotek**-fanen i Harald-appen.

## Sådan tilføjer du en bog

Du kan tilføje bøger på tre måder:

### 1. En mappe med billedsider (manga / scannede sider)
Opret en undermappe og læg billedfilerne i den. Filnavnene afgør rækkefølgen
(naturlig sortering, så `side2.jpg` kommer før `side10.jpg`).

```
boeger/
└── Min Manga Kapitel 1/
    ├── 001.jpg
    ├── 002.jpg
    └── 003.jpg
```

Understøttede billedformater: `.jpg .jpeg .png .webp .gif .svg .avif .bmp`

### 2. Et CBZ- eller ZIP-arkiv
Læg en `.cbz`- eller `.zip`-fil direkte i mappen. Den pakkes automatisk ud,
og billederne sorteres efter navn.

```
boeger/
└── Min Tegneserie.cbz
```

### 3. En PDF
Læg en `.pdf`-fil direkte i mappen. Den renderes side for side i læseren.

```
boeger/
└── Min Bog.pdf
```

## Upload i appen
Du kan også uploade en fil (billede, CBZ/ZIP eller PDF) direkte i biblioteket.
Uploadede bøger gælder kun for den aktuelle browser-session og gemmes ikke i
projektet — vil du beholde en bog permanent, så læg den i denne mappe og commit.

## Læser-funktioner
- Bladr med pile-tasterne (← →), mellemrum, klik i siderne eller swipe på mobil
- Zoom: tilpas bredde/højde, +/− eller dobbeltklik · pinch på touch
- Læseretning kan skiftes mellem venstre→højre og højre→venstre (manga)
- Fuldskærm (F)
- Appen husker automatisk hvor du kom til i hver bog (gemt i browseren)
