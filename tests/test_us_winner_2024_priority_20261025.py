from scripts.research.us_winner_2024_priority_20261025 import choose_job


def job(name,qualified=True,blocked=False,resolved=False):
    return dict(name=name,qualified=qualified,blocked=blocked,resolved=resolved)


def test_two_slots_include_adopted_worker():
    jobs=[job('1x-2022'),job('1x-2024')]
    assert choose_job(jobs,{'2x-2024':{}},adopted_alive=True) is None
    assert choose_job(jobs,{},adopted_alive=True)==('1x-2024','resume')


def test_2024_priority_then_qualification_before_its_resume():
    jobs=[job('1x-2023'),job('2x-2024',False),job('1x-2024')]
    assert choose_job(jobs,{},adopted_alive=True)==('1x-2024','resume')
    assert choose_job([job('1x-2024',resolved=True),*jobs[:2]],{},adopted_alive=True)==('2x-2024','qualify')
    assert choose_job([job('1x-2024',resolved=True),job('2x-2024')],{},adopted_alive=True)==('2x-2024','resume')


def test_do_not_duplicate_active_or_failed_or_resolved_work():
    jobs=[job('1x-2024',blocked=True),job('2x-2024',resolved=True),job('1x-2023')]
    assert choose_job(jobs,{'1x-2023':{}},adopted_alive=False) is None
