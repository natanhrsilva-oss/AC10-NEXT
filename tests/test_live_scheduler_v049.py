from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "20-live.yml").read_text(encoding="utf-8")
SQL = (ROOT / "scripts" / "setup_supabase_live_scheduler_v049.sql").read_text(encoding="utf-8")


def test_supabase_dispatch_does_not_force_live():
    assert "ac10-next live --scheduled" in WORKFLOW
    assert 'inputs.force }}" = "true"' in WORKFLOW
    assert 'source:' in WORKFLOW


def test_github_schedule_remains_as_backup():
    assert "schedule:" in WORKFLOW
    assert "BACKUP" in WORKFLOW
    assert 'timezone: "America/Sao_Paulo"' in WORKFLOW


def test_supabase_cron_checks_success_before_dispatch():
    assert "ac10_dispatch_live_if_due" in SQL
    assert "status = 'SUCCESS'" in SQL
    assert "interval '15 minutes'" in SQL
    assert "status = 'RUNNING'" in SQL


def test_supabase_dispatch_uses_safe_workflow_inputs():
    assert "'force', false" in SQL
    assert "'source', 'supabase'" in SQL
    assert "github_actions_token" in SQL
    assert "vault.decrypted_secrets" in SQL


def test_cron_runs_every_five_minutes():
    assert "'*/5 * * * *'" in SQL
    assert "ac10-live-primary-heartbeat" in SQL
