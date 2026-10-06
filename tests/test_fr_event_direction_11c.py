from pathlib import Path

import pandas as pd
import pytest
import yaml

from service.fr.event_direction_11c import amf_events, available_day, dila_events, event_features


def position(day, ratio, position_day=None):
    return {"isin": "FR0000054470", "holder": "fund", "publication_date": day,
            "position_date": position_day or day, "ratio_percent": ratio}


def test_availability_is_delayed_and_lag_frozen():
    assert available_day("2024-01-05", 1) == "2024-01-06"
    assert available_day("2024-01-05", 2) == "2024-01-07"
    with pytest.raises(ValueError):
        available_day("2024-01-05", 0)


def test_ambiguous_update_breaks_previous_state():
    records = [position("2024-01-01", 0.5), position("2024-01-02", 0.6),
               position("2024-01-02", 0.7), position("2024-01-03", 0.8)]
    events, audit = amf_events(records)
    assert len(events) == 2
    assert audit["ambiguous_holder_isin_day_groups_excluded"] == 1
    assert events[-1]["increase"] == 0


def test_below_threshold_exit_not_continuous_total_interest():
    events, _ = amf_events([position("2024-01-01", 0.6), position("2024-01-02", 0.4),
                          position("2024-01-03", 0.7)])
    assert events[1]["threshold_exit"] == 1
    assert events[1]["decrease"] == 0
    assert events[2]["increase"] == 0


def test_dila_duplicate_and_conflicting_day():
    row = {"identificationsociete_iso_cd_isi": "FR0000054470", "uin_idt_uin": "one",
           "uin_dat_amf": "2024-01-01T12:00:00Z"}
    events, _ = dila_events([row, row])
    assert len(events) == 1
    events, report = dila_events([row, {**row, "uin_dat_amf": "2024-01-02T12:00:00Z"}])
    assert not events and report["rejected_groups"]


def test_no_same_day_or_future_publication_feature():
    pool = pd.DataFrame([{"research_uid": "uid", "decision_session_date": "2024-01-02"}])
    events, _ = amf_events([position("2024-01-01", 0.6), position("2024-01-02", 0.7), position("2024-01-03", 0.8)])
    features = event_features(pool, {"uid": "FR0000054470"}, events, [], set(), 1)
    assert features.iloc[0]["amf_publications_7"] == pytest.approx(0.6931471805599453)
    assert features.iloc[0]["dila_archive_collected"] == 0
    assert event_features(pool, {"uid": "FR0000054470"}, events, [], set(), 2).iloc[0]["amf_publications_7"] == 0


def test_visual_orange_footnote_and_vallourec_type_preserved():
    review = yaml.safe_load(Path("config/research_fr/guidance_review_11c_v1.yaml").read_text(encoding="utf-8"))
    records = {r["issuer"]: r for r in review["records"]}
    assert records["Orange"]["old_value"] == 3.5
    assert records["Vallourec"]["type"] == "PROVISIONAL_RESULTS_VS_PREVIOUS_GUIDANCE"
    assert records["Vallourec"]["excluded_from_forward_guidance"]
