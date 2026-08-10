# Blind grounding-audit på virkelige kendelser

Det adversarielle grounding-benchmark tester kendte fejlstrukturer deterministisk. Dette
værktøj har et andet formål: at finde **virkelige query/kendelse-par i Ejnars korpus**, som
er værd at læse manuelt for den samme fejltype.

For hvert relevant retrieval-resultat sammenstilles:

1. det paragraph, som matcher brugerens spørgsmål bedst;
2. nævnets udtrukne afgørelseskerne.

Et par prioriteres til audit, når afgørelseskernen indeholder et muligt dispositivt grundlag,
som ikke findes i det query-relevante uddrag, fx tilstandsrapport, manglende OT-bevis,
frist, undtagelse, beløbsgrænse, vedligeholdelse eller efterfølgende årsag.

Heuristikken er **ikke en juridisk label**. Den bruges kun til at reducere en stor
resultatliste til en menneskeligt gennemgåelig stikprøve.

## To adskilte artifacts

Workflowet `Ejnar grounding audit pool` producerer:

- `ejnar-grounding-audit-adjudication`: blind pool til juristen. Den indeholder spørgsmål,
  kendelse, query-uddrag, afgørelseskerne og tomme reviewfelter — men ikke retrieval-rank,
  heuristisk score eller automatisk prioritet.
- `ejnar-grounding-audit-diagnostics`: retrieval-resultater, contrast score, ground-tags,
  prioritet og summary. Denne fil må først sammenholdes med reviewet efter labels er frosset.

Foreslåede menneskelige labels er:

- `direct_practice`: kendelsen tager faktisk stilling til det juridiske spørgsmål;
- `indirect_support`: kendelsen belyser spørgsmålet, men udfaldet hviler helt eller delvist
  på et andet grundlag;
- `not_useful`: uddraget bør ikke bruges som støtte for spørgsmålet;
- `uncertain`: kræver nærmere gennemgang.

Formålet er at bygge et senere menneskevalideret grounding-facit. Først dér kan vi måle,
hvor ofte Ejnar skelner korrekt mellem direkte praksis og analogier på virkelige kendelser.
