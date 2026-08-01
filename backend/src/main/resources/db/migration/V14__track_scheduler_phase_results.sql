ALTER TABLE scheduler_runs
    ADD COLUMN phase_results_json TEXT NULL AFTER observation_count;
