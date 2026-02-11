-- Create company_settings table for storing API keys and configurations per company
CREATE TABLE public.company_settings (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  serpapi_key TEXT,
  waha_api_url TEXT,
  waha_api_key TEXT,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  CONSTRAINT unique_company_settings UNIQUE (company_id)
);

-- Enable RLS
ALTER TABLE public.company_settings ENABLE ROW LEVEL SECURITY;

-- Create policies - only company members can view/manage their company settings
CREATE POLICY "Users can view their company settings"
ON public.company_settings
FOR SELECT
USING (
  company_id = get_user_company_id(auth.uid())
);

CREATE POLICY "Users can insert their company settings"
ON public.company_settings
FOR INSERT
WITH CHECK (
  company_id = get_user_company_id(auth.uid())
);

CREATE POLICY "Users can update their company settings"
ON public.company_settings
FOR UPDATE
USING (
  company_id = get_user_company_id(auth.uid())
);

-- Create trigger for automatic timestamp updates
CREATE TRIGGER update_company_settings_updated_at
BEFORE UPDATE ON public.company_settings
FOR EACH ROW
EXECUTE FUNCTION public.handle_updated_at();