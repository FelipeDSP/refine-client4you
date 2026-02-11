-- Add super_admin role for the user dsefs123@gmail.com
INSERT INTO public.user_roles (user_id, role, company_id)
VALUES ('335cd113-95c1-411b-936c-068bb5075e13', 'super_admin', '2f9bc96b-ebd0-46fa-9aa8-297af4dd82bc')
ON CONFLICT DO NOTHING;

-- Also add company_owner role so they can manage their own company settings
INSERT INTO public.user_roles (user_id, role, company_id)
VALUES ('335cd113-95c1-411b-936c-068bb5075e13', 'company_owner', '2f9bc96b-ebd0-46fa-9aa8-297af4dd82bc')
ON CONFLICT DO NOTHING;