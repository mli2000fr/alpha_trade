-- Migration 0093: recherche prospective US; réponses append-only, aucun secret.
USE alpha_trade;

CREATE TABLE llm_directional_runs (
	run_id VARCHAR(80) NOT NULL, 
	trade_date DATE NOT NULL, 
	batch_id VARCHAR(255) NOT NULL, 
	account_id VARCHAR(40) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	started_at DATETIME NOT NULL, 
	completed_at DATETIME, 
	config_json LONGTEXT NOT NULL, 
	input_json LONGTEXT NOT NULL, 
	input_sha256 VARCHAR(64) NOT NULL, 
	protocol_version VARCHAR(40) NOT NULL, 
	selected_json LONGTEXT, 
	error_message TEXT, 
	risk_started_at DATETIME, 
	risk_run_id VARCHAR(100), 
	execution_started_at DATETIME, 
	PRIMARY KEY (run_id)
)ENGINE=InnoDB CHARSET=utf8mb4

;


CREATE TABLE llm_directional_assessments (
	run_id VARCHAR(80) NOT NULL, 
	symbol VARCHAR(20) NOT NULL, 
	oracle_rank INTEGER NOT NULL, 
	oracle_score FLOAT NOT NULL, 
	observed_at DATETIME NOT NULL, 
	request_json LONGTEXT NOT NULL, 
	response_json LONGTEXT, 
	response_sha256 VARCHAR(64), 
	assessment_json LONGTEXT, 
	sources_json LONGTEXT, 
	status VARCHAR(24) NOT NULL, 
	selected BOOL NOT NULL, 
	error_message TEXT, 
	PRIMARY KEY (run_id, symbol), 
	FOREIGN KEY(run_id) REFERENCES llm_directional_runs (run_id)
)ENGINE=InnoDB CHARSET=utf8mb4

;


CREATE TABLE llm_directional_evaluations (
	run_id VARCHAR(80) NOT NULL, 
	symbol VARCHAR(20) NOT NULL, 
	horizon INTEGER NOT NULL, 
	evaluated_at DATETIME NOT NULL, 
	entry_date DATE NOT NULL, 
	exit_date DATE NOT NULL, 
	return_pct FLOAT NOT NULL, 
	signal_return_pct FLOAT NOT NULL, 
	selected BOOL NOT NULL, 
	oracle_decile INTEGER, 
	lineage_json LONGTEXT NOT NULL, 
	PRIMARY KEY (run_id, symbol, horizon), 
	FOREIGN KEY(run_id) REFERENCES llm_directional_runs (run_id)
)ENGINE=InnoDB CHARSET=utf8mb4

;
