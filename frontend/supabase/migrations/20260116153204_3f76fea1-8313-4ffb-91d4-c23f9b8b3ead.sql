-- Fix 1: Add UPDATE policy for leads table (error level issue)
CREATE POLICY "Users can update their company leads"
ON public.leads
FOR UPDATE
TO authenticated
USING (company_id = public.get_user_company_id(auth.uid()))
WITH CHECK (company_id = public.get_user_company_id(auth.uid()));

-- Fix 2: Restrict company_settings access to company_owner and super_admin only (warn level - important security improvement)
-- Drop existing permissive policies
DROP POLICY IF EXISTS "Users can view their company settings" ON public.company_settings;
DROP POLICY IF EXISTS "Users can insert their company settings" ON public.company_settings;
DROP POLICY IF EXISTS "Users can update their company settings" ON public.company_settings;

-- Create restrictive policies for company_owner and super_admin only
CREATE POLICY "Company owners can view settings"
ON public.company_settings
FOR SELECT
TO authenticated
USING (
  company_id = public.get_user_company_id(auth.uid())
  AND (
    public.has_role(auth.uid(), 'company_owner'::app_role)
    OR public.has_role(auth.uid(), 'super_admin'::app_role)
  )
);

CREATE POLICY "Company owners can insert settings"
ON public.company_settings
FOR INSERT
TO authenticated
WITH CHECK (
  company_id = public.get_user_company_id(auth.uid())
  AND (
    public.has_role(auth.uid(), 'company_owner'::app_role)
    OR public.has_role(auth.uid(), 'super_admin'::app_role)
  )
);

CREATE POLICY "Company owners can update settings"
ON public.company_settings
FOR UPDATE
TO authenticated
USING (
  company_id = public.get_user_company_id(auth.uid())
  AND (
    public.has_role(auth.uid(), 'company_owner'::app_role)
    OR public.has_role(auth.uid(), 'super_admin'::app_role)
  )
)
WITH CHECK (
  company_id = public.get_user_company_id(auth.uid())
  AND (
    public.has_role(auth.uid(), 'company_owner'::app_role)
    OR public.has_role(auth.uid(), 'super_admin'::app_role)
  )
);