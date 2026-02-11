import { useState, useEffect, useCallback } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/useAuth";
import type { Database } from "@/integrations/supabase/types";

type AppRole = Database["public"]["Enums"]["app_role"];

export interface AdminUser {
  id: string;
  email: string;
  fullName: string | null;
  companyId: string | null;
  companyName: string | null;
  roles: AppRole[];
  createdAt: string;
  // Dados de quota/plano
  quotaPlanType: string | null;
  quotaPlanName: string | null;
  quotaStatus: string | null;
  quotaExpiresAt: string | null;
}

export interface Company {
  id: string;
  name: string;
  slug: string;
  createdAt: string;
  membersCount: number;
  subscription: {
    planId: string;
    status: string;
    demoUsed: boolean;
  } | null;
}

export function useAdmin() {
  // Pegamos user, session e isLoading (como authLoading)
  const { user, session, isLoading: authLoading } = useAuth() as any;
  
  const [isAdmin, setIsAdmin] = useState<boolean | null>(() => {
    // Tenta recuperar do sessionStorage para evitar flicker
    const cached = sessionStorage.getItem('isAdmin');
    return cached !== null ? cached === 'true' : null;
  });
  const [isLoading, setIsLoading] = useState(true);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);

  // Check if current user is admin
  const checkAdminStatus = useCallback(async () => {
    // Se a sessão é undefined ou o auth está carregando, mantém loading
    if (session === undefined || authLoading === true) {
      setIsLoading(true);
      return;
    }

    if (!user?.id) {
      setIsAdmin(false);
      setIsLoading(false);
      sessionStorage.setItem('isAdmin', 'false');
      return;
    }

    // Mantém loading enquanto faz a verificação
    setIsLoading(true);

    try {
      const { data, error } = await supabase.rpc("has_role", {
        _user_id: user.id,
        _role: "super_admin",
      });

      if (error) {
        console.error("Error checking admin status:", error);
        setIsAdmin(false);
        sessionStorage.setItem('isAdmin', 'false');
      } else {
        const adminStatus = data === true;
        setIsAdmin(adminStatus);
        sessionStorage.setItem('isAdmin', String(adminStatus));
      }
    } catch (error) {
      console.error("Error checking admin status:", error);
      setIsAdmin(false);
      sessionStorage.setItem('isAdmin', 'false');
    } finally {
      setIsLoading(false);
    }
  }, [user?.id, session, authLoading]);

  useEffect(() => {
    checkAdminStatus();
  }, [checkAdminStatus]);

  // Fetch all users (admin only)
  const fetchUsers = useCallback(async () => {
    if (!isAdmin) return;

    try {
      // Fetch profiles
      const { data: profiles, error: profilesError } = await supabase
        .from("profiles")
        .select(`
          id,
          email,
          full_name,
          company_id,
          created_at,
          companies:company_id (name)
        `);

      if (profilesError) {
        console.error("Error fetching profiles:", profilesError);
        return;
      }

      // Fetch user roles
      const { data: roles, error: rolesError } = await supabase
        .from("user_roles")
        .select("user_id, role");

      if (rolesError) {
        console.error("Error fetching roles:", rolesError);
        return;
      }

      // Fetch user quotas (handle case where subscription_status column might not exist)
      let quotas: any[] = [];
      try {
        const { data: quotasData, error: quotasError } = await supabase
          .from("user_quotas")
          .select("user_id, plan_type, plan_name, plan_expires_at");

        if (quotasError) {
          console.error("Error fetching quotas:", quotasError);
        } else if (quotasData) {
          quotas = quotasData;
        }
      } catch (e) {
        console.warn("Could not fetch quotas:", e);
      }

      // Map roles by user_id
      const rolesByUser: Record<string, AppRole[]> = {};
      roles?.forEach((r) => {
        if (!rolesByUser[r.user_id]) {
          rolesByUser[r.user_id] = [];
        }
        rolesByUser[r.user_id].push(r.role as AppRole);
      });

      // Map quotas by user_id
      const quotasByUser: Record<string, any> = {};
      quotas?.forEach((q) => {
        quotasByUser[q.user_id] = q;
      });

      const mappedUsers: AdminUser[] = (profiles || []).map((p: any) => ({
        id: p.id,
        email: p.email,
        fullName: p.full_name,
        companyId: p.company_id,
        companyName: p.companies?.name || null,
        roles: rolesByUser[p.id] || [],
        createdAt: p.created_at,
        quotaPlanType: quotasByUser[p.id]?.plan_type || null,
        quotaPlanName: quotasByUser[p.id]?.plan_name || null,
        quotaStatus: quotasByUser[p.id]?.plan_type === 'suspended' ? 'suspended' : 'active',
        quotaExpiresAt: quotasByUser[p.id]?.plan_expires_at || null,
      }));

      setUsers(mappedUsers);
    } catch (error) {
      console.error("Error fetching users:", error);
    }
  }, [isAdmin]);

  // Fetch all companies (admin only)
  const fetchCompanies = useCallback(async () => {
    if (!isAdmin) return;

    try {
      const { data: companiesData, error: companiesError } = await supabase
        .from("companies")
        .select(`
          id,
          name,
          slug,
          created_at,
          subscriptions (plan_id, status, demo_used)
        `);

      if (companiesError) {
        console.error("Error fetching companies:", companiesError);
        return;
      }

      // Count members per company
      const { data: profileCounts, error: countsError } = await supabase
        .from("profiles")
        .select("company_id");

      if (countsError) {
        console.error("Error fetching profile counts:", countsError);
        return;
      }

      const memberCounts: Record<string, number> = {};
      profileCounts?.forEach((p) => {
        if (p.company_id) {
          memberCounts[p.company_id] = (memberCounts[p.company_id] || 0) + 1;
        }
      });

      const mappedCompanies: Company[] = (companiesData || []).map((c: any) => {
        const sub = Array.isArray(c.subscriptions) ? c.subscriptions[0] : c.subscriptions;
        return {
          id: c.id,
          name: c.name,
          slug: c.slug,
          createdAt: c.created_at,
          membersCount: memberCounts[c.id] || 0,
          subscription: sub
            ? {
                planId: sub.plan_id,
                status: sub.status,
                demoUsed: sub.demo_used || false,
              }
            : null,
        };
      });

      setCompanies(mappedCompanies);
    } catch (error) {
      console.error("Error fetching companies:", error);
    }
  }, [isAdmin]);

  useEffect(() => {
    if (isAdmin) {
      fetchUsers();
      fetchCompanies();
    }
  }, [isAdmin, fetchUsers, fetchCompanies]);

  // Add admin role to a user
  const addAdminRole = async (userId: string): Promise<boolean> => {
    if (!isAdmin) return false;

    try {
      const { error } = await supabase.from("user_roles").insert({
        user_id: userId,
        role: "super_admin",
      });

      if (error) {
        console.error("Error adding admin role:", error);
        return false;
      }

      await fetchUsers();
      return true;
    } catch (error) {
      console.error("Error adding admin role:", error);
      return false;
    }
  };

  // Remove admin role from a user
  const removeAdminRole = async (userId: string): Promise<boolean> => {
    if (!isAdmin) return false;

    // Prevent removing own admin role
    if (userId === user?.id) return false;

    try {
      const { error } = await supabase
        .from("user_roles")
        .delete()
        .eq("user_id", userId)
        .eq("role", "super_admin");

      if (error) {
        console.error("Error removing admin role:", error);
        return false;
      }

      await fetchUsers();
      return true;
    } catch (error) {
      console.error("Error removing admin role:", error);
      return false;
    }
  };

  // Update subscription plan for a company
  const updateCompanyPlan = async (
    companyId: string,
    planId: string,
    resetDemo: boolean = false
  ): Promise<boolean> => {
    if (!isAdmin) return false;

    try {
      const updateData: Record<string, unknown> = {
        plan_id: planId,
        current_period_start: new Date().toISOString(),
        current_period_end: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
      };

      if (resetDemo) {
        updateData.demo_used = false;
      }

      const { error } = await supabase
        .from("subscriptions")
        .update(updateData)
        .eq("company_id", companyId);

      if (error) {
        console.error("Error updating company plan:", error);
        return false;
      }

      await fetchCompanies();
      return true;
    } catch (error) {
      console.error("Error updating company plan:", error);
      return false;
    }
  };

  // Reset demo usage for a company
  const resetDemoUsage = async (companyId: string): Promise<boolean> => {
    if (!isAdmin) return false;

    try {
      const { error } = await supabase
        .from("subscriptions")
        .update({ demo_used: false })
        .eq("company_id", companyId);

      if (error) {
        console.error("Error resetting demo:", error);
        return false;
      }

      await fetchCompanies();
      return true;
    } catch (error) {
      console.error("Error resetting demo:", error);
      return false;
    }
  };

  // Pause/Activate subscription for a company
  const toggleCompanyStatus = async (companyId: string, newStatus: "active" | "paused"): Promise<boolean> => {
    if (!isAdmin) return false;

    try {
      const { error } = await supabase
        .from("subscriptions")
        .update({ status: newStatus })
        .eq("company_id", companyId);

      if (error) {
        console.error("Error toggling company status:", error);
        return false;
      }

      await fetchCompanies();
      return true;
    } catch (error) {
      console.error("Error toggling company status:", error);
      return false;
    }
  };

  // Delete a company and all related data
  const deleteCompany = async (companyId: string): Promise<boolean> => {
    if (!isAdmin) return false;

    try {
      // Delete in order: leads, search_history, subscriptions, company_settings, profiles, user_roles (via profile cascade), then company
      await supabase.from("leads").delete().eq("company_id", companyId);
      await supabase.from("search_history").delete().eq("company_id", companyId);
      await supabase.from("subscriptions").delete().eq("company_id", companyId);
      await supabase.from("company_settings").delete().eq("company_id", companyId);
      
      // Get user IDs for this company to delete their roles
      const { data: companyProfiles } = await supabase
        .from("profiles")
        .select("id")
        .eq("company_id", companyId);
      
      if (companyProfiles && companyProfiles.length > 0) {
        const userIds = companyProfiles.map(p => p.id);
        await supabase.from("user_roles").delete().in("user_id", userIds);
        await supabase.from("profiles").delete().eq("company_id", companyId);
      }
      
      // Finally delete the company
      const { error: companyError } = await supabase
        .from("companies")
        .delete()
        .eq("id", companyId);

      if (companyError) {
        console.error("Error deleting company:", companyError);
        return false;
      }

      await fetchCompanies();
      await fetchUsers();
      return true;
    } catch (error) {
      console.error("Error deleting company:", error);
      return false;
    }
  };

  // Delete a single user
  const deleteUser = async (userId: string): Promise<boolean> => {
    if (!isAdmin) return false;

    // Prevent deleting yourself
    if (userId === user?.id) return false;

    try {
      // Usar endpoint do backend que deleta completamente
      const backendUrl = import.meta.env.VITE_BACKEND_URL || '';
      const token = session?.access_token;
      
      if (!token) {
        console.error("No access token available");
        return false;
      }
      
      const response = await fetch(`${backendUrl}/api/admin/users/${userId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        const error = await response.json();
        console.error("Error deleting user:", error);
        return false;
      }
      
      const result = await response.json();
      console.log("✅ Usuário deletado completamente:", result);

      await fetchUsers();
      await fetchCompanies();
      return true;
    } catch (error) {
      console.error("Error deleting user:", error);
      return false;
    }
  };

  // Change user role (member, admin, company_owner)
  const changeUserRole = async (userId: string, newRole: AppRole): Promise<boolean> => {
    if (!isAdmin) return false;

    // Cannot change super_admin role with this function
    if (newRole === "super_admin") return false;

    try {
      // First, remove existing non-super_admin roles
      const { data: existingRoles } = await supabase
        .from("user_roles")
        .select("id, role")
        .eq("user_id", userId);

      if (existingRoles) {
        for (const role of existingRoles) {
          if (role.role !== "super_admin") {
            await supabase.from("user_roles").delete().eq("id", role.id);
          }
        }
      }

      // Insert the new role
      const { error } = await supabase.from("user_roles").insert({
        user_id: userId,
        role: newRole,
      });

      if (error) {
        console.error("Error changing user role:", error);
        return false;
      }

      await fetchUsers();
      return true;
    } catch (error) {
      console.error("Error changing user role:", error);
      return false;
    }
  };

  // Transfer user to another company
  const transferUserToCompany = async (userId: string, newCompanyId: string): Promise<boolean> => {
    if (!isAdmin) return false;

    try {
      const { error } = await supabase
        .from("profiles")
        .update({ company_id: newCompanyId })
        .eq("id", userId);

      if (error) {
        console.error("Error transferring user:", error);
        return false;
      }

      await fetchUsers();
      await fetchCompanies();
      return true;
    } catch (error) {
      console.error("Error transferring user:", error);
      return false;
    }
  };

  return {
    isAdmin,
    isLoading,
    users,
    companies,
    addAdminRole,
    removeAdminRole,
    updateCompanyPlan,
    resetDemoUsage,
    toggleCompanyStatus,
    deleteCompany,
    deleteUser,
    changeUserRole,
    transferUserToCompany,
    refreshData: () => {
      fetchUsers();
      fetchCompanies();
    },
  };
}