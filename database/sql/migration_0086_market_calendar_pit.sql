-- Sprint 4 CN — calendrier multi-marchés segmenté et contrat PIT.
ALTER TABLE market_sessions
    ADD COLUMN session_segments_json JSON NULL AFTER close_at_utc;