-- Migration: add is_pinned column to threads table
-- Safe to run multiple times (uses IF NOT EXISTS equivalent via DO block)

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'threads' AND column_name = 'is_pinned'
    ) THEN
        ALTER TABLE threads ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
END$$;

