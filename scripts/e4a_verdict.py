"""E4-A — Ajoute la section Verdict au rapport de signature pré-crash.

La synthèse est fondée sur les tableaux générés par e4a_precrash_signature.py
(sections 1-6). Aucun calcul supplémentaire : figé le diagnostic.
"""
from __future__ import annotations

from pathlib import Path

OUT = Path("artifacts/models/oracle/e4a_precrash_signature.md")

VERDICT = """
## Verdict E4-A — A (dominant)

### Constat central
- **Familles directionnelles (momentum, RSI, return, volume, gap, range) :
  AUCUNE séparation, à aucun lag, y compris D-1 et D.**
  AUC 0.48-0.52 partout (bruit). Les futurs BOTTOM10 ratés ne deviennent
  jamais distinguables des futurs TOP10 capturés, même la veille du
  mouvement H20. Aucune signature pré-crash.
- **Volatilité / ATR / drawdown : séparation forte (AUC 0.81-0.93) MAIS
  PERMANENTE** — déjà complète à D-60 (rolling_volatility_60 :
  D-60=0.854 -> D=0.926 ; atr20_pct : 0.834 -> 0.885 ; drawdown_20 :
  ~0.39 constant). C'est une propriété de CLASSE des BOTTOM (titres
  structurellement volatils/en drawdown), pas un signal de TIMING.
- **Trajectoire normalisée (delta vs D-60, section 5) :** AUC(delta) max
  0.59 à D pour vol_60, ~0.53 pour ATR, ~0.50 pour tout le reste. Émergence
  tardive (D-5/D), faible, monotone, sans saut net à D-10/D-5. Rien
  n'atteint un niveau exploitable (seuil indicatif >0.60) avant D.
- **Contrôle "pourquoi Oracle rate l'extrême" (sections 4/6) :** aucune
  signature avant D. Oracle capture structurellement les BOTTOM les plus
  volatils (permanent, déjà dans le modèle), mais rien ne signale à
  l'avance quels BOTTOM il va rater.

### Verdict : A
Aucune séparation exploitable, même à D-1/D, sur l'ensemble des familles
OHLCV/techniques. Les BOTTOM réels 2025-26 ne deviennent jamais
distinguables des TOP sur les features existantes, à aucun horizon avant le
mouvement.

La volatilité "sépare" mais de façon permanente (caractéristique de classe) :
un modèle entraîné dessus prédirait "c'est un BOTTOM" en permanence, sans
déclencher à l'approche du mouvement. Inutilisable comme discriminateur
directionnel H3/H5 conditionnel (verdict B non retenu : aucune séparation
D-1/D-3 sur les familles de direction).

### Implications
- Conforme au cadre utilisateur : **A -> fermer OHLCV/technique pour la
  direction** (Oracle Extreme reste le prédicteur d'extrêmes ; aucune
  information directionnelle exploitable à exploiter en pré-crash).
- **Prochaine étape : E4-B = nouvelles données orthogonales**
  (earnings / révisions -> options -> positioning).
- Ne PAS tenter de discriminateur directionnel H3/H5 sur les features
  existantes.

_(Fichier : artifacts/models/oracle/e4a_precrash_signature.md.
Population 2025 + 2026H1 : TOP_capture=3,029, BOTTOM_rate=11,307,
BOTTOM_capture=2,472. Lags D-60..D, strictement PIT.)_
"""


def main() -> None:
    txt = OUT.read_text(encoding="utf-8")
    if "## Verdict E4-A" in txt:
        print("verdict deja present, rien a faire")
        return
    OUT.write_text(txt.rstrip() + "\n" + VERDICT.lstrip("\n"), encoding="utf-8")
    print("verdict ajoute:", OUT)


if __name__ == "__main__":
    main()
