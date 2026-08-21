"""E4-B1 — ajoute la section Verdict au rapport de diagnostic earnings."""
from __future__ import annotations

from pathlib import Path

OUT = Path("artifacts/models/oracle/e4b1b_earnings_diag.md")

VERDICT = """
## Verdict E4-B1

### 1. Direction UP/DOWN dans le pool Extreme : **NO-GO**
- Aucune feature earnings ne discrimine la direction H20, sur AUCUN horizon ni période :
  - `eps_yoy_growth` : AUC 0.479-0.519 selon année, médianes UP/DOWN quasi identiques, signe instable.
  - `revenue_yoy_growth` : AUC 0.465-0.544, signe changeant par année.
  - `days_since_earnings` / `days_to_next_earnings` : AUC ~0.49-0.52, médianes identiques (54j/54j ; 42j/42j).
  - `post_earnings_1d` / `post_earnings_3d` : AUC ~0.45-0.53, sans stabilité.
- **Permutation null (200 répliques, ALL)** : AUC observés 0.485-0.509 = tous dans la plage null
  (p50 null ~0.50, p95 null ~0.51-0.52). Aucun AUC ne dépasse le bruit. p_perm > 0.02 pour tous sauf
  revenue_yoy (0.025, mais AUC 0.485 = inversé et non stable par année).
- Le gate "signal stable et orienté sur plusieurs années" **n'est PAS franchi** : rien n'est orienté
  de façon cohérente 2022->2026.

### 2. Diagnostic secondaire BOTTOM ratés vs TOP capturés : signal FAIBLE mais STABLE (piste)
- `revenue_yoy_growth` : AUC(BOTTOM=1) < 0.5 cohérent sur 4 périodes (2023: 0.365, 2024: 0.460,
  2025: 0.415, 2026H1: 0.375 ; ALL 0.423). **Les BOTTOM "invisibles" ont une croissance revenue
  plus faible** (median 0.078 vs 0.153). Effet modeste (d ~ -0.09 a -0.15) mais signe stable.
- `days_to_next_earnings` : AUC(BOTTOM=1) ~0.36-0.43 cohérent 2022->2025 (2022: 0.356, 2023: 0.425,
  2024: 0.424, 2025: 0.428 ; ALL 0.413). **Les BOTTOM ratés ont un prochain earnings plus proche**
  (median 39j vs 50j). Cohérent avec E4-A : risque/event proximity.
- `post_earnings_3d` : fort en 2022 (0.562) et 2023 (0.607) mais retombe a ~0.50 en 2024-25 ->
  NON stable, ecarter.
- `eps_yoy_growth` : signe instable (0.586 en 2022 -> 0.463 en 2026H1) -> non fiable.

### Conclusion
- **E4-B1 earnings : NO-GO pour la direction** (UP/DOWN). La croissance YoY, l'âge et la reaction
  post-earnings n'apportent aucune information directionnelle dans le pool Extreme, meme en
  restreignant a l'univers de trade reel (400 symboles).
- **Piste secondaire confirmee (non exploitable seule)** : les BOTTOM invisibles 2025-26 se
  caracterisent par une croissance revenue plus faible et un earnings plus proche. Aucun AUC
  directionnel > 0.55 stable : inutilisable pour un Direction Model, mais utile pour comprendre
  *pourquoi* Oracle rate l'extreme (contexte, pas signal).
- **Gate : E4-B1 NO-GO -> passer a E4-B2 (fundamentals de niveau, stock_fundamentals_daily)**
  comme planifie. Le consensus Finnhub (2026 seul) reste une hypothese a part, N trop faible.
"""


def main() -> None:
    txt = OUT.read_text(encoding="utf-8")
    if "## Verdict E4-B1" in txt:
        print("verdict deja present")
        return
    OUT.write_text(txt.rstrip() + "\n" + VERDICT.lstrip("\n"), encoding="utf-8")
    print("verdict ajoute:", OUT)


if __name__ == "__main__":
    main()
