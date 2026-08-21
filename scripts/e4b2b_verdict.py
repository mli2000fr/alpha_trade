"""E4-B2B — Ajoute la section Verdict au rapport de diagnostic short interest.

Fondée sur e4b2b_diag.py (UP/DOWN + BOTTOM/TOP + permutation) et
e4b2b_robustesse.py (quintiles, biais taille, contrôle par taille).
"""
from __future__ import annotations

from pathlib import Path

OUT = Path("artifacts/models/oracle/e4b2b_short_interest_diag.md")

VERDICT = """
## Verdict E4-B2B — NO-GO (direction), signature de classe documentée

### Constat central
- **Direction UP/DOWN (question centrale) : AUCUNE séparation exploitable.**
  Toutes features short interest (stock, variation de cycle, % change,
  days-to-cover, accélération, ratio/float, ratio/advol), toutes périodes :
  AUC 0.45-0.54 (bruit). Meilleur cas = dtc/ratio_advol 0.508 ALL (2023 0.536,
  2026H1 0.527) — non persistant, signe qui s'inverse (2024 0.485). Permutation
  null : p_perm > 0.2 sauf short_interest_raw (0.005, mais AUC 0.477 = effet
  TAILLE, voir §2). Quintiles dtc et ratio_float non monotones (Q5-Q1 oscille
  -4.9pp a +6.3pp selon l'annee) : aucune relation dose.
- **Biais taille : short_interest_raw et ratio_float sont des artefacts de
  TAILLE** (Spearman SI_raw vs ratio_float = +0.66 ; les BOTTOM ont un SI absolu
  PLUS FAIBLE que les TOP parce que les TOP sont des titres plus gros).
  Leur "signal" AUC 0.38 (BOTTOM vs TOP) est l'inverse de la direction
  attendue -> a ecarter comme feature directionnelle.
- **Critique BOTTOM rates vs TOP captures : signature de CLASSE faible mais
  reelle, survive au controle de taille.** days_to_cover / ratio_advol :
  AUC(BOTTOM=1) ALL 0.532 (d +0.07), par quintile de taille 0.54-0.62 dans
  Q1-Q4 (seul Q0 inverse). Interpretation : les BOTTOM reels portent une
  pression short plus difficile a couvrir (plus de jours), coherent avec le
  ratio_20d de E4-B2A — mais c'est un attribut PERMANENT de classe, pas un
  signal qui se declenche a l'approche du mouvement, et il ne separe pas
  UP de DOWN dans le pool Extreme.

### Verdict : NO-GO
Le short interest FINRA (stock de positions, bimensuel, PIT strict via
publication_date = settlement + 7 jours ouvrés) n'apporte AUCUNE information
directionnelle UP/DOWN conditionnelle au pool Oracle Extreme, sur aucune
feature ni annee. Conforme a la cascade : E4-A (OHLCV) -> E4-B1 (earnings) ->
E4-B2A (short volume quotidien) -> E4-B2B (short interest stock) : quatre
sources, quatre NO-GO directionnels.

Documente (non exploitable comme trigger) : les BOTTOM reels ont un
days-to-cover plus eleve que les TOP captures (signature de classe, survive
au controle de taille). Meme famille que le ratio_20d en E4-B2A.

### Implications
- Fermer la piste short interest pour la direction H20 conditionnelle.
- La signature "days-to-cover eleve" des BOTTOM est un attribut permanent
  (titres structurellement sous pression), pas un signal pre-mouvement.
- Une fois 3-4 sources independantes (news eventuelles, options, revisions),
  on pourra envisager un modele multivarie encadre (WF causal + permutation),
  mais AUCUN univarie ne justifie seul un trigger directionnel.

_(Fichier : artifacts/models/oracle/e4b2b_short_interest_diag.md.
Population pool Extreme 400 : N=65,373 (UP 32,915 / DOWN 32,458).
BOTTOM_rate 25,393 / TOP_capture 7,479 / ALL. PIT strict publication_date.)_
"""


def main() -> None:
    txt = OUT.read_text(encoding="utf-8")
    if "## Verdict E4-B2B" in txt:
        print("verdict deja present, rien a faire")
        return
    OUT.write_text(txt.rstrip() + "\n" + VERDICT.lstrip("\n"), encoding="utf-8")
    print("verdict ajoute:", OUT)


if __name__ == "__main__":
    main()
