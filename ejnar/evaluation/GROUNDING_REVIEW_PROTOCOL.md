# Ejnar grounding review protocol

Formålet er at bedømme, **hvordan en fundet kendelse må bruges som praksisstøtte til det konkrete spørgsmål**. Reviewet tager ikke stilling til, om en konkret forsikringssag er dækket.

## Labeldefinitioner

### `direct_practice`

Brug denne label, når nævnets egen begrundelse direkte tager stilling til det juridiske spørgsmål, og det spørgsmålsrelevante uddrag kan bruges som direkte praksisstøtte.

Eksempel: Spørgsmålet handler om, hvornår nedsat bæreevne udgør en skade, og nævnet tager faktisk stilling til skadesbegrebet/bæreevnen som led i den bærende begrundelse.

### `indirect_support`

Brug denne label, når kendelsen indeholder et relevant udsagn eller faktum, men udfaldet eller den bærende begrundelse hviler på et andet grundlag.

Eksempel: Kendelsen omtaler væsentligt nedsat bæreevne, men klageren får ikke medhold, fordi forholdet allerede var anmærket i tilstandsrapporten. Udsagnet kan være et støttepunkt eller en analogi, men kendelsen er ikke direkte praksis for skadebegrebet.

### `not_useful`

Brug denne label, når kendelsen eller uddraget ikke giver pålidelig støtte til spørgsmålet. Det kan fx være et partsudsagn, et teknisk faktum uden forbindelse til nævnets begrundelse eller et resultat, der er hentet på et andet emne.

### `uncertain`

Brug denne label, når det viste uddrag og afgørelseskernen ikke er nok til en sikker bedømmelse. Åbn originalkendelsen via linket, kontrollér den, og skriv i `review_notes`, hvorfor sagen fortsat er usikker, hvis den ikke kan afklares.

## Reviewrækkefølge

1. Læs brugerens spørgsmål.
2. Læs `query_excerpt` og identificér, hvorfor teksten umiddelbart virker relevant.
3. Læs `decision_core` og fastslå, hvad nævnet faktisk lagde til grund for udfaldet.
4. Sammenhold de to.
5. Vælg én label.
6. Angiv reviewer. Ved `indirect_support` bør `review_notes` kort angive det andet afgørelsesgrund. Ved `uncertain` er note obligatorisk.

## Vigtige guardrails

- Bedøm ikke ud fra udfald alene (`medhold`/`ikke medhold`).
- Et udsagn fra klager, selskab eller sagkyndig er ikke automatisk nævnets praksis.
- Et korrekt citat kan stadig være juridisk misvisende, hvis kendelsen blev afgjort på et andet grundlag.
- Tilstandsrapport, kendt forhold, bevis ved overtagelsen, frister, undtagelser og beløbsgrænser er typiske alternative afgørelsesgrunde, der skal kontrolleres.
- `indirect_support` er ikke en dårlig kendelse. Den må bare ikke præsenteres som direkte praksis for et spørgsmål, som nævnet ikke behøvede at afgøre.

## Blinding

Reviewarket indeholder bevidst ikke retrieval-rank, contrast score, priority eller automatiske juridiske labels. De oplysninger ligger i et separat diagnostik-artifact og bør først ses efter labels er frosset.
