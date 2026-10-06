-- Une exécution possède sa propre preuve brute, même si le fournisseur renvoie
-- exactement le même contenu qu'au passage précédent. Les lignes métier du
-- staging restent dédupliquées par endpoint + entity_key + payload_hash.
ALTER TABLE tushare_raw_payloads DROP INDEX uq_tushare_raw_page;
ALTER TABLE tushare_raw_payloads
  ADD UNIQUE KEY uq_tushare_raw_run_page (run_id,endpoint,request_hash,page_key);
