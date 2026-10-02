from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pre_workflow_has_supabase_source_and_safe_if_missing():
    text = (ROOT / ".github/workflows/10-pre.yml").read_text(encoding="utf-8")
    assert 'source:' in text
    assert '"supabase"' in text
    assert 'ac10-next pre --if-missing' in text
    assert '15 6 * * *' in text
    assert '30 6 * * *' in text


def test_supabase_pre_scheduler_is_resilient_and_daily_deduped():
    text = (ROOT / "scripts/setup_supabase_pre_scheduler_v0411.sql").read_text(encoding="utf-8")
    assert "ac10_dispatch_pre_if_missing" in text
    assert "ac10-pre-primary-heartbeat" in text
    assert "0,5,10,15,20,25,30 6 * * *" in text
    assert "parameters->>'date' = v_target_date::text" in text
    assert "status = 'SUCCESS'" in text
    assert "status = 'RUNNING'" in text
    assert "10-pre.yml/dispatches" in text
