"""Guardrails for synthesising Ankenævnet practice from retrieved decisions.

Decision grounding ensures that the model sees what each decision was actually decided
on. This module adds the next distinction: a decision that is useful as an analogy must
not silently enter counts or generalisations as if it were direct practice on the user's
question.

The policy changes answer generation only. It does not label decisions automatically,
change retrieval or decide concrete insurance claims.
"""
from __future__ import annotations

from typing import Any


_POLICY_MARKER = "PRAKSISSYNTESE (OBLIGATORISK)"
_PRACTICE_POLICY = (
    "\n\nPRAKSISSYNTESE (OBLIGATORISK):\n"
    "Disse regler har forrang for tidligere generelle instrukser om at identificere "
    "mønstre, praksislinjer eller fordelinger.\n"
    "13. Før du beskriver en praksislinje, tendens, et mønster eller en fordeling, skal "
    "du for hver anvendt kendelse kontrollere afgørelseskernen og skelne mellem DIREKTE "
    "PRAKSIS og INDIREKTE STØTTE. En kendelse er kun direkte praksis, når nævnets egen "
    "bærende begrundelse faktisk tager stilling til det juridiske spørgsmål, du bruger "
    "kendelsen til.\n"
    "14. Kendelser, der reelt blev afgjort på et andet grundlag, må gerne bruges som "
    "analogi eller indirekte støtte, men de må IKKE tælles med i udsagn som '3 af 5', "
    "'flertallet af kendelserne', 'nævnet lægger typisk vægt på' eller 'praksis viser'. "
    "Angiv dem særskilt som indirekte støtte og forklar det andet afgørelsesgrund.\n"
    "15. Brug aldrig udfaldet (medhold/ikke medhold) alene til at udlede en praksisregel. "
    "En fordeling må kun beregnes blandt direkte sammenlignelige kendelser, hvor samme "
    "juridiske spørgsmål indgår i nævnets bærende begrundelse. Hvis du angiver en "
    "fordeling, skriv tydeligt hvad nævneren består af, fx '2 af 3 direkte relevante "
    "kendelser'.\n"
    "16. Én direkte kendelse er et eksempel, ikke en praksislinje. To direkte kendelser "
    "kan beskrives som to kendelser, der peger i samme eller forskellig retning, men er "
    "ikke i sig selv 'fast praksis'. Brug kun formuleringer som 'klar/fast praksis', når "
    "flere direkte sammenlignelige kendelser har konsistent bærende begrundelse, og de "
    "fremlagte kilder ikke viser væsentlige modgående direkte afgørelser.\n"
    "17. Hvis du ikke sikkert kan afgøre, om en kilde er direkte praksis eller indirekte "
    "støtte ud fra afgørelseskernen, så medregn den ikke i en generalisering. Beskriv "
    "usikkerheden i stedet.\n"
    "18. Når brugerens spørgsmål efterspørger praksis, tendens, afgørende momenter eller "
    "hvornår nævnet når et bestemt resultat, skal kildegrundlaget være synligt i svaret: "
    "Brug overskriften 'Direkte praksis' for kendelser, hvor nævnets bærende begrundelse "
    "tager stilling til spørgsmålet. Hvis du også anvender kendelser, der blev afgjort på "
    "et andet grundlag, placér dem særskilt under 'Indirekte støtte' og angiv kort dette "
    "andet afgørelsesgrund, fx tilstandsrapport, bevis ved overtagelsen eller frist. "
    "Opret ikke tomme kategorier. Hvis der ikke er tilstrækkelig direkte praksis til en "
    "generalisering, sig det tydeligt i stedet for at få indirekte kilder til at ligne "
    "direkte praksis."
)


def inject_practice_synthesis_policy(prompt: Any) -> Any:
    """Inject conservative synthesis rules into Ejnar's legal answer prompt.

    Input is copied rather than mutated. Non-Ejnar/string prompts pass through unchanged.
    The function is idempotent so nested Streamlit/runtime installation is safe.
    """
    if not isinstance(prompt, list):
        return prompt

    copied: list[Any] = []
    changed = False
    for block in prompt:
        if not isinstance(block, dict):
            copied.append(block)
            continue
        new_block = dict(block)
        text = new_block.get("text")
        if (
            not changed
            and isinstance(text, str)
            and "REGLER:" in text
            and "Du er en juridisk assistent" in text
        ):
            if _POLICY_MARKER not in text:
                new_block["text"] = text + _PRACTICE_POLICY
            changed = True
        copied.append(new_block)
    return copied
