-- Add waha_session column to company_settings
ALTER TABLE public.company_settings
ADD COLUMN waha_session TEXT DEFAULT 'default';