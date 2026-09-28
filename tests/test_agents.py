from agents.authenticity_agent import assess_authenticity
from agents.lifecycle_agent import determine_lifecycle_phase

def base_signal():
    return {"evidence_status": "MEASURED",
            "source_scores": {"google_trends": .8, "wikipedia": .4, "youtube": .5, "news": .3, "autocomplete": .2},
            "details": {"google_trends": {"available": True, "velocity": 10, "recent_avg": 40,
                                         "historical_avg": 20, "previous_avg": 25,
                                         "acceleration": 3, "observations": 30, "rising": True}}}

def test_lifecycle_and_authenticity_rules():
    signal = base_signal()
    assert determine_lifecycle_phase(signal)[0] == "GROWTH"
    assert assess_authenticity(signal)[0] in {"GENUINE", "LIKELY_GENUINE"}
