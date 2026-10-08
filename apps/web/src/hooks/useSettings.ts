"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import type { StaffDirectoryItem, StaffDirectoryResponse } from "@aifya/shared";

// ── Facility profile ──────────────────────────────────────────────────────

/** Facility profile as returned by GET /facility. */
export interface FacilityProfile {
  id: string;
  name: string;
  code: string;
  facility_type: string;
  keph_level: string | null;
  mfl_code: string | null;
  county: string | null;
  sub_county: string | null;
  ward: string | null;
  physical_address: string | null;
  latitude: number | null;
  longitude: number | null;
  phone: string | null;
  email: string | null;
  website: string | null;
  logo_url: string | null;
  timezone: string;
  currency: string;
  dhis2_org_unit_id: string | null;
  onboarding_status: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Editable subset of the facility profile. */
export type FacilityUpdatePayload = Partial<
  Pick<
    FacilityProfile,
    | "name"
    | "facility_type"
    | "keph_level"
    | "mfl_code"
    | "county"
    | "sub_county"
    | "ward"
    | "physical_address"
    | "latitude"
    | "longitude"
    | "phone"
    | "email"
    | "website"
    | "logo_url"
    | "timezone"
    | "currency"
    | "dhis2_org_unit_id"
  >
>;

/**
 * Read the signed-in user's facility profile.
 *
 * @returns Query result with the facility profile
 */
export function useFacilityProfile() {
  return useOfflineQuery<FacilityProfile>({
    queryKey: ["settings", "facility"],
    queryFn: () => apiClient.get<FacilityProfile>("/facility"),
  });
}

/**
 * Update the facility profile.
 *
 * @returns Mutation for saving facility changes
 */
export function useUpdateFacility() {
  const queryClient = useQueryClient();
  return useMutation<FacilityProfile, Error, FacilityUpdatePayload>({
    mutationFn: (data) => apiClient.patch<FacilityProfile>("/facility", data),
    onSuccess: (updated) => {
      queryClient.setQueryData(["settings", "facility"], updated);
    },
  });
}

// ── Roles & permissions ───────────────────────────────────────────────────

/** One role and the permissions it holds at this facility. */
export interface RolePermissions {
  role: string;
  permissions: string[];
}

/** Response shape of GET /auth/roles. */
export interface RolesMatrix {
  roles: RolePermissions[];
  all_permissions: string[];
  total_permissions: number;
}

/**
 * Read the role-to-permission matrix in force at this facility.
 *
 * @returns Query result with the roles matrix
 */
export function useRolesMatrix() {
  return useOfflineQuery<RolesMatrix>({
    queryKey: ["settings", "roles"],
    queryFn: () => apiClient.get<RolesMatrix>("/auth/roles"),
  });
}

// ── Team & users ──────────────────────────────────────────────────────────

/**
 * Read the staff directory, including deactivated staff so an administrator
 * can reactivate them.
 *
 * @returns Query result with the staff directory
 */
export function useStaffDirectory() {
  return useOfflineQuery<StaffDirectoryResponse>({
    queryKey: ["settings", "staff", "all"],
    queryFn: () =>
      apiClient.get<StaffDirectoryResponse>("/hr/staff?include_inactive=true"),
    refetchInterval: 60_000,
  });
}

/**
 * Activate or deactivate a staff member.
 *
 * @returns Mutation for changing a staff member's active state
 */
export function useSetStaffActive() {
  const queryClient = useQueryClient();
  return useMutation<
    StaffDirectoryItem,
    Error,
    { staffId: string; isActive: boolean }
  >({
    mutationFn: ({ staffId, isActive }) =>
      apiClient.patch<StaffDirectoryItem>(`/hr/staff/${staffId}/active`, {
        is_active: isActive,
      }),
    onSuccess: () => {
      // The HR directory lists the same people under its own key, so refresh
      // both or the other screen keeps showing the old state.
      queryClient.invalidateQueries({ queryKey: ["settings", "staff"] });
      queryClient.invalidateQueries({ queryKey: ["hr", "staff"] });
    },
  });
}
