"""Predeclared future-outcome rules. Keep these fixed before experiments."""
def direction(current, future, tolerance=0.05):
    delta = future - current
    if delta > tolerance: return "UP"
    if delta < -tolerance: return "DOWN"
    return "STABLE"

def outcome(search_change, mention_change, cross_source_count):
    available = [x for x in (search_change, mention_change) if x is not None]
    if not available or cross_source_count < 2:
        return "UNCERTAIN"
    positive = sum(x > 0.05 for x in available)
    negative = sum(x < -0.05 for x in available)
    if positive >= 2 or (positive == 1 and cross_source_count >= 3): return "STRENGTHENED"
    if negative >= 2 or (negative == 1 and cross_source_count >= 3): return "WEAKENED"
    return "UNCHANGED"
