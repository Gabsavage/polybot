"""Quarter-Kelly sizing for C1 alerts."""

from polybot.config import Settings


def compute_size(
    bankroll: float,
    tier_a_confidence: float,
    settings: Settings,
) -> float | None:
    """Compute quarter-Kelly suggested size.

    Returns suggested USD size, or None if below minimum alert threshold.
    """
    if tier_a_confidence >= 0.90:  # A1
        edge = settings.C1_EDGE_DEFAULT_A1
        confidence = settings.C1_CONFIDENCE_MULTIPLIER_A1
    else:  # A2
        edge = settings.C1_EDGE_DEFAULT_A2
        confidence = settings.C1_CONFIDENCE_MULTIPLIER_A2

    size = bankroll * settings.C1_KELLY_FRACTION * edge * confidence

    # Cap at max % of bankroll
    size = min(size, bankroll * settings.C1_SIZE_MAX_PCT_BANKROLL)

    if size < settings.C1_SIZE_MIN_ALERT:
        return None

    return round(size, 2)
