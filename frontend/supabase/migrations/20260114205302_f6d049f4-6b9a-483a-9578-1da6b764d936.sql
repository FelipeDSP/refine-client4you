-- Add policies for super_admin to have full access to all tables

-- Profiles: super_admin can view all profiles
CREATE POLICY "Super admins can view all profiles"
ON public.profiles
FOR SELECT
TO authenticated
USING (has_role(auth.uid(), 'super_admin'::app_role));

-- Companies: super_admin can view all companies
CREATE POLICY "Super admins can view all companies"
ON public.companies
FOR SELECT
TO authenticated
USING (has_role(auth.uid(), 'super_admin'::app_role));

-- User roles: super_admin can view all roles
CREATE POLICY "Super admins can view all roles"
ON public.user_roles
FOR SELECT
TO authenticated
USING (has_role(auth.uid(), 'super_admin'::app_role));

-- User roles: super_admin can insert roles
CREATE POLICY "Super admins can insert roles"
ON public.user_roles
FOR INSERT
TO authenticated
WITH CHECK (has_role(auth.uid(), 'super_admin'::app_role));

-- User roles: super_admin can delete roles
CREATE POLICY "Super admins can delete roles"
ON public.user_roles
FOR DELETE
TO authenticated
USING (has_role(auth.uid(), 'super_admin'::app_role));

-- Subscriptions: super_admin can view all subscriptions
CREATE POLICY "Super admins can view all subscriptions"
ON public.subscriptions
FOR SELECT
TO authenticated
USING (has_role(auth.uid(), 'super_admin'::app_role));

-- Subscriptions: super_admin can update all subscriptions
CREATE POLICY "Super admins can update all subscriptions"
ON public.subscriptions
FOR UPDATE
TO authenticated
USING (has_role(auth.uid(), 'super_admin'::app_role));