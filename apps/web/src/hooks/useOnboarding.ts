"use client";

import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export interface FacilitySignupRequest {
  facility_name: string;
  facility_type: string;
  county?: string | null;
  mfl_code?: string | null;
  facility_phone?: string | null;
  admin_first_name: string;
  admin_last_name: string;
  admin_email: string;
  admin_password?: string;
}

export interface FacilitySignupResponse {
  facility_id: string;
  onboarding_status: string;
  message: string;
}

export interface StaffInviteRequest {
  email: string;
  first_name: string;
  last_name: string;
  role: string;
}

export interface StaffInviteResponse {
  staff_id: string;
  keycloak_user_id: string;
  email: string;
  role: string;
  message: string;
}

/** Public gated facility sign-up. */
export function useFacilitySignup() {
  return useMutation<FacilitySignupResponse, Error, FacilitySignupRequest>({
    mutationFn: (data) =>
      apiClient.post<FacilitySignupResponse>("/onboarding/facility-signup", data),
  });
}

/** Facility-admin invite for a new staff member. */
export function useStaffInvite() {
  return useMutation<StaffInviteResponse, Error, StaffInviteRequest>({
    mutationFn: (data) =>
      apiClient.post<StaffInviteResponse>("/onboarding/staff-invite", data),
  });
}
