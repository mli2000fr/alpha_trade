"""E4-B2C — Ajoute la section Verdict au rapport de diagnostic news structurelles.

Fondée sur e4b2c_diag.py (UP/DOWN + BOTTOM/TOP + permutation).
"""
from __future__ import annotations

from pathlib import Path

OUT = Path("artifacts/models/oracle/e4b2c_news_diag.md")

VERDICT = """
## Verdict E4-B2C — NO-GO (direction), asymétrie news documentée

### Constat central
- **Direction UP/DOWN (question centrale) : AUCUNE séparation exploitable.**
  Toutes features news structurelles (burst counts, major-event, diversité
  sources, pre/post-market, relevance, accélération), toutes périodes :
  AUC 0.44-0.51. Les p-values sont toutes ultra-significatives (N=65 373)
  mais l'EFFET est minuscule : écart à 0.5 <= 0.06, Cohen d <= 0.20.
  Permutation null : pour counts/major/diversité p_perm=0.000 mais AUC observé
  ~0.47-0.48 (hors du bruit, dans le mauvais sens pour un trigger UP).
- **Asymétrie COHÉRENTE mais faible : les DOWN ont PLUS de news que les UP.**
  news_count_1d/5d/20d AUC 0.476/0.474/0.471 ALL, d -0.07/-0.08/-0.09 ;
  s'amplifie en 2026H1 (count_20d AUC 0.435, d -0.20). Interpretation : la
  couverture médiatique est un marqueur de RISQUE (titres sous pression
  couverts), pas un déclencheur directionnel. Direction contraire à un
  signal "news -> up". Non exploitable tel quel (trop loin de 0.5 et du
  seuil utile 0.55), mais orthogonale et stable -> candidat multivarié.
- **Critique BOTTOM rates vs TOP captures : signature de CLASSE (couverture
  médiatique).** Les BOTTOM ratés ont BEAUCOUP MOINS de news que les TOP
  capturés (news_count_1d/5d/20d AUC(BOTTOM=1) 0.483/0.478/0.479 ALL,
  d -0.246/-0.275/-0.263 ; after_close d -0.215). Interpretation : les TOP
  capturés sont des titres très couverts (grosses caps, forte visibilité) ;
  les BOTTOM ratés sont des titres moins couverts. C'est un attribut de
  CLASSE/taille, cohérent avec le biais taille vu en E4-B2A/B2B, PAS un
  signal de timing.

### Verdict : NO-GO
Les news structurelles déjà en base (burst, major-event, diversité, pré/post,
relevance) n'apportent AUCUNE information directionnelle UP/DOWN exploitable
conditionnelle au pool Oracle Extreme. Le sentiment net avait déjà été condamné
en D1 ; la partie structurelle l'est aussi pour la direction.

Documenté (piste multivariée, pas un trigger) : (a) asymétrie "les DOWN ont
plus de news" stable et croissante vers 2026H1 ; (b) les BOTTOM ratés sont des
titres structurellement moins couverts médiatiquement que les TOP capturés.

### Implications
- Fermer la piste news structurelle pour la direction H20 conditionnelle.
- Avec E4-B2A/B2B, on a maintenant 3 sources orthogonales (short volume, short
  interest, news) qui montrent TOUTES un signal de CLASSE (titres sous pression
  / moins couverts) mais AUCUN signal de timing directionnel. Ce n'est qu'à ce
  stade (3+ sources indépendantes) qu'un modèle multivarié encadré (WF causal +
  permutation) devient pertinent — PAS avant.
- Prochaine source : options (E4-B3, skew/put-call) si disponible PIT, puis
  analyst revisions (E4-B4).

_(Fichier : artifacts/models/oracle/e4b2c_news_diag.md.
Population pool Extreme 400 : N=65,373 (UP 32,915 / DOWN 32,458).
BOTTOM_rate 25,393 / TOP_capture 7,479 / ALL. PIT : effective_trade_date.)_
"""


def main() -> None:
    txt = OUT.read_text(encoding="utf-8")
    if "## Verdict E4-B2C" in txt:
        print("verdict deja present, rien a faire")
        return
    OUT.write_text(txt.rstrip() + "\n" + VERDICT.lstrip("\n"), encoding="utf-8")
    print("verdict ajoute:", OUT)


if __name__ == "__main__":
    main()
