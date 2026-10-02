from types import SimpleNamespace

from ac10next.pipelines.audit import _finished_with_pending_recommendations


def test_audit_ignores_finished_provider_matches_without_pending_ac10_recommendation():
    recommended=SimpleNamespace(match_id="100")
    unrelated=SimpleNamespace(match_id="200")

    finished=[
        (recommended, {"id":"100"}),
        (unrelated, {"id":"200"}),
    ]
    by_match={
        "100":[{"id":"rec-1","match_id":"100","market":"BACK CASA"}],
    }

    relevant=_finished_with_pending_recommendations(finished,by_match)

    assert len(relevant)==1
    assert relevant[0][0].match_id=="100"


def test_audit_accepts_string_or_numeric_like_match_ids_consistently():
    match=SimpleNamespace(match_id=1398099323)
    by_match={
        "1398099323":[{"id":"rec-1","match_id":"1398099323","market":"OVER +1 GOL"}],
    }

    relevant=_finished_with_pending_recommendations([(match,{})],by_match)

    assert len(relevant)==1
