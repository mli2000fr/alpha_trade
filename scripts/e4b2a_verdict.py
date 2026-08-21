"""E4-B2A — Ajoute la section Verdict au rapport de diagnostic short volume.

Fondée sur les tableaux de e4b2a_diag.py (UP/DOWN + BOTTOM/TOP + permutation)
et e4b2a_robustesse.py (quintiles, biais liquidité, contrôle par taille).
"""
from __future__ import annotations

from pathlib import Path

OUT = Path("artifacts/models/oracle/e4b2a_short_volume_diag.md")

VERDICT = """
## Verdict E4-B2A — NO-GO (direction), signature de classe documentée

### Constat central
- **Direction UP/DOWN (question centrale) : AUCUNE séparation exploitable.**
  Toutes features short-volume, toutes périodes : AUC 0.45-0.53 (bruit).
  Meilleur cas 2026H1 = ret5_x_short_ratio 0.530 / rel_short_pressure_sector
  0.524 — isolé, non persistant. Permutation null : p_perm > 0.2 pour la
  quasi-totalité des features. Quintiles du ratio_20d non monotones (Q5-Q1
  oscille entre -6.8pp et +5.7pp selon l'annee) : aucune relation dose.
- **Controle "biais liquidite" : short_share est un ARTEFACT DE TAILLE**
  (Spearman +0.89 avec finra_total_volume). Son "signal" inverse
  (d~-0.44 BOTTOM vs TOP) n'est pas une pression short : les TOP captures
  sont des titres plus gros/mieux couverts. A ecarter.
- **Critique BOTTOM rates vs TOP captures 2025-26 : signature RELLE mais de
  CLASSE, pas de timing.** short_volume_ratio_20d : AUC ALL 0.557, 2025 0.563,
  2026H1 0.619 (d +0.195 ALL, +0.374 2026H1) ; rel_short_pressure_sector
  ALL 0.545. Survit au controle par taille (AUC 0.52-0.57 dans chaque
  quintile). Interpretation : les BOTTOM reels 2025-26 portaient une
  pression short RELATIVE plus elevee que les TOP captures — c'est une
  propriete de CLASSE des BOTTOM (titres structurellement sous pression),
  coherente avec E4-A (volatilite/drawdown permanents), PAS un signal qui
  se declenche a l'approche du mouvement. Elle ne separe pas UP de DOWN
  dans le pool Extreme (les DOWN y ont le meme ~0.51 de ratio).

### Verdict : NO-GO
Le short volume quotidien FINRA (TRF/ADF/ORF) n'apporte AUCUNE information
directionnelle UP/DOWN conditionnelle au pool Oracle Extreme, sur aucun
horizon, aucune annee, aucune feature (ratio, zscore, changement, tendance,
part de marche, interaction prix, relatif sectoriel). Conforme a la cascade :
E4-A (OHLCV) -> E4-B1 (earnings) -> E4-B2A (short) : trois sources
orthogonales, trois NO-GO directionnels.

Documente (non exploitable comme trigger) : les BOTTOM reels ont une
pression short relative plus elevee que les TOP captures, croissante
2022->2026H1 (AUC 0.53 -> 0.62). A ne PAS convertir en feature de selection :
dans le pool Extreme elle ne distingue pas UP de DOWN.

### Implications
- Fermer la piste short volume pour la direction H20 conditionnelle.
- La "signature BOTTOM" (ratio_20d eleve) est un attribut permanent des
  titres en decadence, pas un signal pre-mouvement : ne pas chercher a en
  faire un filtre directionnel.
- Prochaines pistes E4-B : options (put/call positioning) -> positioning
  institutionnel -> order flow. Verifier d'abord la disponibilite PIT et la
  couverture 400 avant diagnostic.

_(Fichier : artifacts/models/oracle/e4b2a_short_volume_diag.md.
Population pool Extreme 400 : N=65,373 (UP 32,915 / DOWN 32,458).
BOTTOM_rate 25,393 / TOP_capture 7,479 / ALL.)_
"""


def main() -> None:
    txt = OUT.read_text(encoding="utf-8")
    if "## Verdict E4-B2A" in txt:
        print("verdict deja present, rien a faire")
        return
    OUT.write_text(txt.rstrip() + "\n" + VERDICT.lstrip("\n"), encoding="utf-8")
    print("verdict ajoute:", OUT)


if __name__ == "__main__":
    main()
