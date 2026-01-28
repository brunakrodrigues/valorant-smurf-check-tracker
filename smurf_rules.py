from typing import Optional, Tuple

# Heurística simples (ajuste livre).
# Tracker tende a retornar tiers numéricos; o mapeamento exato pode variar,
# mas pra "gap grande" funciona bem.

TIER_LABELS = [
    (0, "Unranked"),
    (3, "Iron"),
    (6, "Bronze"),
    (9, "Silver"),
    (12, "Gold"),
    (15, "Platinum"),
    (18, "Diamond"),
    (21, "Ascendant"),
    (24, "Immortal"),
    (27, "Radiant"),
]


def tier_to_label(tier: Optional[int]) -> str:
    if tier is None:
        return "Unknown"
    label = "Unranked"
    for threshold, name in TIER_LABELS:
        if tier >= threshold:
            label = name
    return label


def is_suspicious_smurf(
    last3_peak_tier: Optional[int],
    current_tier: Optional[int],
    min_peak_tier: int = 18,     # >= Diamond
    max_current_tier: int = 12,  # <= Gold
    min_gap: int = 6,
) -> Tuple[bool, str]:
    if last3_peak_tier is None:
        return False, "Sem dados suficientes para calcular peak nos últimos 3 atos."
    if current_tier is None:
        return False, "Sem dados suficientes para estimar elo atual."

    gap = last3_peak_tier - current_tier
    if last3_peak_tier >= min_peak_tier and current_tier <= max_current_tier and gap >= min_gap:
        return True, f"Peak alto (tier {last3_peak_tier}) e atual baixo (tier {current_tier}), gap {gap}."
    return False, f"Sem evidência forte: peak {last3_peak_tier}, atual {current_tier}, gap {gap}."
