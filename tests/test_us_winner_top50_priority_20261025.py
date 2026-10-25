from scripts.research.us_winner_top50_priority_20261025 import choose


def j(name,qualified=False,blocked=False,resolved=False):
    return dict(name=name,qualified=qualified,blocked=blocked,resolved=resolved)


def test_adopted_workers_consume_real_slots_not_duplicated():
    jobs=[j('1x-2022',True),j('1x-2024',True),j('top50-2017'),j('2x-2024')]
    adopted={'1x-2022':{},'1x-2024':{}}
    assert choose(jobs,{},adopted)==('top50-2017','qualify')
    assert choose(jobs,{'top50-2017':{}},adopted) is None


def test_qualified_top50_resumes_before_new_lower_priority_work():
    assert choose([j('top50-2017',True),j('2x-2024')],{}, {})==('top50-2017','resume')
    assert choose([j('top50-2017',True,resolved=True),j('2x-2024')],{}, {})==('2x-2024','qualify')


def test_no_retry_of_blocked_job():
    assert choose([j('top50-2017',blocked=True)],{}, {}) is None
