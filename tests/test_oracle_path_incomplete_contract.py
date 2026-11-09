import json

import pytest

from modelFactory.oracle_path.predict import load_contract


def test_missing_report_describes_unpublished_training_without_loading_weights(tmp_path):
    root=tmp_path/'batch'/'oracle_path';root.mkdir(parents=True)
    for name in ('protocol.json','feature_profile.json'):
        (root/name).write_text('{}',encoding='utf-8')
    (root/'progress.json').write_text(json.dumps(dict(status='RUNNING',phase='directional',
        completed=1539,total=1790)),encoding='utf-8')
    with pytest.raises(ValueError,match=r'non prêt.*report.json.*RUNNING.*directional.*1539/1790'):
        load_contract(tmp_path,'batch')
    assert not (root/'report.json').exists()


def test_unknown_batch_and_broken_progress_remain_unservable(tmp_path):
    with pytest.raises(ValueError,match='non prêt.*protocol.json.*feature_profile.json.*report.json'):
        load_contract(tmp_path,'missing')
    root=tmp_path/'broken'/'oracle_path';root.mkdir(parents=True)
    (root/'progress.json').write_text('{',encoding='utf-8')
    with pytest.raises(ValueError,match='Dernier état enregistré : inconnu'):
        load_contract(tmp_path,'broken')
