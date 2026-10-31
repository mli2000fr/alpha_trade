-- Primary collection storage without market or checkpoint file dependency.
CREATE TABLE fr_collection_objects (
 content_sha256 CHAR(64) NOT NULL PRIMARY KEY,
 byte_length BIGINT NOT NULL,
 stored_at DATETIME(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE fr_collection_object_parts (
 content_sha256 CHAR(64) NOT NULL,
 part_no INT NOT NULL,
 body MEDIUMBLOB NOT NULL,
 PRIMARY KEY(content_sha256,part_no),
 FOREIGN KEY(content_sha256) REFERENCES fr_collection_objects(content_sha256)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE fr_collection_versions (
 batch_name VARCHAR(96) NOT NULL,
 resource_sha256 CHAR(64) NOT NULL,
 content_sha256 CHAR(64) NOT NULL,
 resource_key TEXT NOT NULL,
 stored_at DATETIME(6) NOT NULL,
 available_at DATETIME(6) NULL,
 PRIMARY KEY(batch_name,resource_sha256,content_sha256),
 FOREIGN KEY(content_sha256) REFERENCES fr_collection_objects(content_sha256)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE fr_collection_heads (
 batch_name VARCHAR(96) NOT NULL,
 resource_sha256 CHAR(64) NOT NULL,
 content_sha256 CHAR(64) NOT NULL,
 resource_key TEXT NOT NULL,
 updated_at DATETIME(6) NOT NULL,
 PRIMARY KEY(batch_name,resource_sha256),
 FOREIGN KEY(batch_name,resource_sha256,content_sha256)
 REFERENCES fr_collection_versions(batch_name,resource_sha256,content_sha256)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE fr_collection_runs (
 operational_run_id VARCHAR(96) NOT NULL PRIMARY KEY,
 batch_name VARCHAR(96) NOT NULL,
 status VARCHAR(48) NOT NULL,
 started_at DATETIME(6) NOT NULL,
 finished_at DATETIME(6) NULL,
 summary_json JSON NOT NULL,
 KEY ix_fr_collection_runs_batch(batch_name,started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
