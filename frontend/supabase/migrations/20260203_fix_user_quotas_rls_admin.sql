-- Migration: Permitir super_admin ver todas as user_quotas
-- Data: 2025-02-03

-- Adicionar policy para super_admin poder ver todas as quotas
CREATE POLICY "Super admin can view all quotas"
  ON user_quotas FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM user_roles
      WHERE user_roles.user_id = auth.uid()
      AND user_roles.role = 'super_admin'
    )
  );

-- Adicionar policy para super_admin poder atualizar qualquer quota
CREATE POLICY "Super admin can update all quotas"
  ON user_quotas FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM user_roles
      WHERE user_roles.user_id = auth.uid()
      AND user_roles.role = 'super_admin'
    )
  );

COMMENT ON POLICY "Super admin can view all quotas" ON user_quotas 
IS 'Permite super_admin visualizar quotas de todos os usuários no painel admin';

COMMENT ON POLICY "Super admin can update all quotas" ON user_quotas 
IS 'Permite super_admin atualizar quotas de qualquer usuário no painel admin';
