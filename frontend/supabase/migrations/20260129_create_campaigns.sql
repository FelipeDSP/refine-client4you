-- Create campaigns table for WhatsApp Dispatcher
CREATE TABLE IF NOT EXISTS public.campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    message_type TEXT NOT NULL DEFAULT 'text',
    message_text TEXT,
    media_url TEXT,
    media_filename TEXT,
    interval_min INTEGER DEFAULT 30,
    interval_max INTEGER DEFAULT 60,
    start_time TEXT,
    end_time TEXT,
    daily_limit INTEGER,
    working_days INTEGER[] DEFAULT ARRAY[0, 1, 2, 3, 4],
    total_contacts INTEGER DEFAULT 0,
    sent_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    pending_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Create campaign_contacts table
CREATE TABLE IF NOT EXISTS public.campaign_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES public.campaigns(id) ON DELETE CASCADE,
    name TEXT,
    phone TEXT NOT NULL,
    email TEXT,
    custom_data JSONB,
    status TEXT NOT NULL DEFAULT 'pending',
    sent_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create message_logs table
CREATE TABLE IF NOT EXISTS public.message_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES public.campaigns(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES public.campaign_contacts(id) ON DELETE SET NULL,
    phone TEXT NOT NULL,
    message_text TEXT,
    status TEXT NOT NULL,
    error_message TEXT,
    sent_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Enable RLS
ALTER TABLE public.campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaign_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.message_logs ENABLE ROW LEVEL SECURITY;

-- RLS Policies for campaigns
CREATE POLICY "Users can view campaigns of their company"
    ON public.campaigns FOR SELECT
    USING (company_id = get_user_company_id(auth.uid()));

CREATE POLICY "Users can insert campaigns in their company"
    ON public.campaigns FOR INSERT
    WITH CHECK (company_id = get_user_company_id(auth.uid()));

CREATE POLICY "Users can update campaigns in their company"
    ON public.campaigns FOR UPDATE
    USING (company_id = get_user_company_id(auth.uid()));

CREATE POLICY "Users can delete campaigns in their company"
    ON public.campaigns FOR DELETE
    USING (company_id = get_user_company_id(auth.uid()));

-- RLS Policies for campaign_contacts
CREATE POLICY "Users can view contacts of their company campaigns"
    ON public.campaign_contacts FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.campaigns
            WHERE campaigns.id = campaign_contacts.campaign_id
            AND campaigns.company_id = get_user_company_id(auth.uid())
        )
    );

CREATE POLICY "Users can insert contacts in their company campaigns"
    ON public.campaign_contacts FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.campaigns
            WHERE campaigns.id = campaign_contacts.campaign_id
            AND campaigns.company_id = get_user_company_id(auth.uid())
        )
    );

CREATE POLICY "Users can update contacts in their company campaigns"
    ON public.campaign_contacts FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM public.campaigns
            WHERE campaigns.id = campaign_contacts.campaign_id
            AND campaigns.company_id = get_user_company_id(auth.uid())
        )
    );

CREATE POLICY "Users can delete contacts in their company campaigns"
    ON public.campaign_contacts FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM public.campaigns
            WHERE campaigns.id = campaign_contacts.campaign_id
            AND campaigns.company_id = get_user_company_id(auth.uid())
        )
    );

-- RLS Policies for message_logs
CREATE POLICY "Users can view message logs of their company campaigns"
    ON public.message_logs FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.campaigns
            WHERE campaigns.id = message_logs.campaign_id
            AND campaigns.company_id = get_user_company_id(auth.uid())
        )
    );

CREATE POLICY "Users can insert message logs in their company campaigns"
    ON public.message_logs FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.campaigns
            WHERE campaigns.id = message_logs.campaign_id
            AND campaigns.company_id = get_user_company_id(auth.uid())
        )
    );

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_campaigns_company_id ON public.campaigns(company_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON public.campaigns(status);
CREATE INDEX IF NOT EXISTS idx_campaigns_created_at ON public.campaigns(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_campaign_contacts_campaign_id ON public.campaign_contacts(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_contacts_status ON public.campaign_contacts(status);

CREATE INDEX IF NOT EXISTS idx_message_logs_campaign_id ON public.message_logs(campaign_id);
CREATE INDEX IF NOT EXISTS idx_message_logs_sent_at ON public.message_logs(sent_at DESC);

-- Trigger for updated_at
CREATE TRIGGER update_campaigns_updated_at
    BEFORE UPDATE ON public.campaigns
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
