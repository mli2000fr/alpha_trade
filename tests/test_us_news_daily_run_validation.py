from copy import deepcopy

import pytest

from scripts.research.us_news_daily_run_validation import assess


def fixture():
    progress=dict(requested=3,received=7,persisted=5,empty=1,failed=0,
        details=dict(status='COMPLETED',completed_symbols=2,skipped_completed=1,pending_symbols=0,
            archive={'map_versions':6}))
    pit=dict(status='COMPLETED',**{key+'_count':progress[key] for key in
        ('requested','received','persisted','empty','failed')})
    archive=dict(map_versions=6,unsealed_mapping_receipts=0,missing_raw_versions=0,wrong_provider=0)
    return progress,pit,3,archive


def test_success_is_collection_only_not_direction():
    result=assess(*fixture())
    assert result['status']=='VALIDATED_COLLECTION_ONLY' and not result['direction_signal_validated']


def test_running_can_have_concurrent_checkpoints_ahead_without_final_approval():
    progress,pit,count,archive=fixture()
    pit['status']='RUNNING'
    progress['details'].update(completed_symbols=1,skipped_completed=0,pending_symbols=2,status='RUNNING')
    result=assess(progress,pit,count,archive)
    assert result['status']=='RUNNING_NOT_YET_VALIDATED' and not result['final']


@pytest.mark.parametrize('field',['requested','received','persisted','empty','failed'])
def test_final_pit_counters_must_match_local_report(field):
    progress,pit,count,archive=fixture()
    pit[field+'_count']+=1
    assert 'PIT_COUNTER_MISMATCH_'+field.upper() in assess(progress,pit,count,archive)['errors']


@pytest.mark.parametrize('field',['unsealed_mapping_receipts','missing_raw_versions','wrong_provider'])
def test_invalid_archive_never_certified(field):
    progress,pit,count,archive=fixture(); archive[field]=1
    assert 'ARCHIVE_INTEGRITY_UNQUALIFIED' in assess(progress,pit,count,archive)['errors']


def test_failed_partial_run_is_not_empty_news_success():
    progress,pit,count,archive=fixture()
    progress['details'].update(status='FAILED',completed_symbols=1,pending_symbols=1)
    pit['status']='FAILED'
    result=assess(progress,pit,1,archive)
    assert result['status']=='FAILED_OR_INCOMPLETE_VALIDATION'
    assert 'COLLECTION_NOT_FULLY_SUCCESSFUL' in result['errors']


def test_missing_checkpoint_or_mapping_count_blocks_complete_status():
    progress,pit,count,archive=fixture(); archive['map_versions']=5
    result=assess(progress,pit,2,archive)
    assert 'SUCCESSFUL_CYCLE_CHECKPOINTS_INCOMPLETE' in result['errors']
    assert 'RUN_MAPPING_VERSION_COUNT_MISMATCH' in result['errors']
