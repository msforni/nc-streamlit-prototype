-- migrations/001_initial.sql
-- NC-SPRINT-002 T106: Initial Supabase schema for the Investment Scoping Calculator
--
-- Apply via Supabase SQL editor (one-time) OR via the migration helper in
-- engine/migrations.py with a postgres_url in secrets.
-- Idempotent — safe to re-run.

-- Migration tracking
CREATE TABLE IF NOT EXISTS migrations_applied (
    id TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    applied_by TEXT
);

-- Users (lightweight; Google OAuth provides identity)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    google_sub TEXT UNIQUE,
    is_active BOOLEAN DEFAULT true,
    role TEXT DEFAULT 'analyst',  -- 'analyst', 'admin'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

-- Segment registers (uploaded CSVs)
CREATE TABLE IF NOT EXISTS segment_registers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    estate TEXT NOT NULL,
    description TEXT,
    segment_count INTEGER,
    total_envelope_kwp NUMERIC(12, 2),
    csv_content TEXT NOT NULL,
    uploaded_by_email TEXT,
    is_canonical BOOLEAN DEFAULT false,
    source_reference TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_segment_registers_estate ON segment_registers(estate);
CREATE INDEX IF NOT EXISTS idx_segment_registers_canonical
    ON segment_registers(is_canonical) WHERE is_canonical = true;

-- Parameter overrides (named sets)
CREATE TABLE IF NOT EXISTS parameter_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    overrides JSONB NOT NULL,
    created_by_email TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Runs (every scoping execution)
CREATE TABLE IF NOT EXISTS runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_label TEXT,
    estate TEXT NOT NULL,
    segment_register_id UUID REFERENCES segment_registers(id) ON DELETE SET NULL,
    parameter_override_id UUID REFERENCES parameter_overrides(id) ON DELETE SET NULL,
    inputs_snapshot JSONB NOT NULL,
    results_snapshot JSONB NOT NULL,
    cashflow_data JSONB,
    validation_report JSONB,
    intake_warnings JSONB,
    intake_errors JSONB,
    engine_version TEXT NOT NULL,
    param_version TEXT NOT NULL,
    ran_by_email TEXT,
    ran_at TIMESTAMPTZ DEFAULT NOW(),
    duration_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_runs_estate ON runs(estate);
CREATE INDEX IF NOT EXISTS idx_runs_ran_at ON runs(ran_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_ran_by ON runs(ran_by_email);

-- PDF outputs (post-T111)
CREATE TABLE IF NOT EXISTS pdf_outputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES runs(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    template_version TEXT NOT NULL,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    generated_by_email TEXT
);

CREATE INDEX IF NOT EXISTS idx_pdf_outputs_run ON pdf_outputs(run_id);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    user_email TEXT,
    event_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_email);

-- RLS: service role full access; anon implicitly denied (no policy)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE segment_registers ENABLE ROW LEVEL SECURITY;
ALTER TABLE parameter_overrides ENABLE ROW LEVEL SECURITY;
ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE pdf_outputs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "service_role_all" ON users;
DROP POLICY IF EXISTS "service_role_all" ON segment_registers;
DROP POLICY IF EXISTS "service_role_all" ON parameter_overrides;
DROP POLICY IF EXISTS "service_role_all" ON runs;
DROP POLICY IF EXISTS "service_role_all" ON pdf_outputs;
DROP POLICY IF EXISTS "service_role_all" ON audit_log;

CREATE POLICY "service_role_all" ON users FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON segment_registers FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON parameter_overrides FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON runs FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON pdf_outputs FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON audit_log FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Record migration
INSERT INTO migrations_applied (id, applied_by) VALUES ('001_initial', 'manual_or_runner')
ON CONFLICT (id) DO NOTHING;
