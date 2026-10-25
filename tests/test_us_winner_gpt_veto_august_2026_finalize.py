from pathlib import Path

from scripts.research import us_winner_gpt_veto_august_2026_finalize as final


def test_operational_lock_is_never_hashed(tmp_path,monkeypatch):
    for name in ('run.lock','failure.json','progress.json','report.json','comparison.csv'):
        (tmp_path/name).write_text('fixture',encoding='utf-8')
    original=final.study.base.digest
    def digest(path):
        assert Path(path).name not in ('run.lock','failure.json','progress.json','report.json')
        return original(path)
    monkeypatch.setattr(final.study.base,'digest',digest)
    assert set(final.report_files(tmp_path))=={'comparison.csv'}
