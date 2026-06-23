# 🏖️ Vores ferie · Korfu — live-synkroniseret feriekalender

En hyggelig **fælles feriekalender** til dig og din kæreste, som I kan have som en app på telefonen. Planlæg ting **sammen og hver for sig**, og se ændringer opdatere sig **live hos jer begge**.

- 📱 Kan installeres på hjemmeskærmen (PWA) — føles som en rigtig app
- 🔄 Live-synkronisering mellem jeres to telefoner
- 🎨 Farvekodet pr. person + "Sammen", filtre, nedtælling og Korfu-idéer
- 💾 Virker også helt uden internet/opsætning (kun lokalt)

---

## 1) Læg den online (så I kan åbne den fra telefonen)

Filerne er en helt almindelig statisk hjemmeside. Den nemmeste gratis vej er **GitHub Pages**:

1. Gå til repoet på GitHub → **Settings** → **Pages**.
2. Under *Build and deployment*: vælg **Deploy from a branch**, branch `main` (eller denne branch), mappe `/ (root)`. Gem.
3. Efter et par minutter er appen på:
   **`https://simo224i-eng.github.io/pkn-vidensbase/ferie-kalender/`**
4. Åbn linket på begge telefoner.

> Alternativt kan I trække mappen `ferie-kalender/` ind på [netlify.com/drop](https://app.netlify.com/drop) og få et link med det samme.

### Føj til hjemmeskærmen
- **iPhone (Safari):** Del-knappen → *Føj til hjemmeskærm*.
- **Android (Chrome):** menuen ⋮ → *Installér app* / *Føj til startskærm*.

---

## 2) Slå live-synkronisering til (én gang, ~5 min — gratis)

Synkroniseringen kører på **Firebase Firestore** (Googles gratis database). Kun **én** af jer skal sætte det op:

1. Gå til <https://console.firebase.google.com> → **Tilføj projekt** (giv det et navn, slå Analytics fra — ligegyldigt).
2. I projektet: **Build → Firestore Database → Create database** → vælg en *region* (fx `europe-west`) → start i **production mode**.
3. Gå til **Firestore → Rules**, indsæt denne regel og tryk **Publish**:
   ```
   rules_version = '2';
   service cloud.firestore {
     match /databases/{database}/documents {
       match /trips/{tripId} {
         allow read, write: if true;
       }
     }
   }
   ```
   *(Jeres "ferie-kode" fungerer som den hemmelige nøgle til kalenderen — vælg derfor en lang, svær kode. Det er en simpel feriekalender, så risikoen er lille.)*
4. Tryk på tandhjulet ⚙️ → **Project settings** → rul ned til **Your apps** → klik web-ikonet **`</>`** → giv den et kælenavn → **Register app**.
5. Kopiér `firebaseConfig`-objektet (det med `apiKey`, `projectId` osv.).

### Forbind appen
1. Åbn feriekalenderen → tryk **⚙️** → rul ned til **🔄 Live-synkronisering**.
2. Skriv en **ferie-kode** (samme tekst som I begge vil bruge, fx `korfu-os-to-2026`).
3. Indsæt `firebaseConfig`-JSON'en i feltet.
4. Tryk **🔌 Forbind & synk**. Pillen øverst skifter til **🟢 Live**.

### Inviter din kæreste (ét klik)
Tryk **📩 Kopiér invitationslink** (eller **🔗 Del** på forsiden) og send linket. Når din kæreste åbner det på sin telefon, bliver de **automatisk forbundet** til samme kalender — de skal ikke selv røre Firebase. ✨

Herefter ses alle ændringer live hos jer begge.

---

## Funktioner i appen

- **Sammen og hver for sig** — hver aktivitet markeres som *Sammen*, *dig* eller *kæreste*, med hver sin farve. Filtrér med chip'erne foroven.
- **Dagsplan + liste** — to visninger af ferien.
- **Idéer til Korfu** — strande, bådture, paladser, tavernaer m.m. Klik for at lægge i planen.
- **Nedtælling** til afrejse.
- **⚙️ Opsætning** — navne, farver, datoer og synkronisering.
- **Eksportér / Importér** plan som JSON (god backup).

## Godt at vide
- Uden Firebase-opsætning virker appen 100 % lokalt; "Del" laver så et øjebliksbillede-link i stedet.
- Synkronisering bruger *sidste-ændring-vinder* pr. plan — perfekt til to personer. Redigér gerne samtidig; ændringer samles løbende.
- Alt er gratis inden for Firebase' gratis-niveau (en lille feriekalender bruger nærmest ingenting).
