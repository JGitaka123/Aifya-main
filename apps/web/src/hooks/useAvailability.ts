"use client";

import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  WeeklyScheduleResponse,
  WeeklyScheduleUpdate,
} from "@aifya/shared";

/**
 * Hook for the signed-in clinician's own weekly working hours.
 *
 * The staff row is resolved from the token server-side, so no id is passed.
 *
 * @returns Query result with the caller's week and effective status
 */
export function useMySchedule() {
  return useOfflineQuery<WeeklyScheduleResponse>({
    queryKey: ["availability", "me"],
    queryFn: () => apiClient.get<WeeklyScheduleResponse>("/hr/me/schedule"),
  });
}

/**
 * Hook for replacing the signed-in clinician's own weekly working hours.
 *
 * @returns Mutation for saving the caller's week
 */
export function useUpdateMySchedule() {
  const qc = useQueryClient();
  return useOfflineMutation<WeeklyScheduleResponse, WeeklyScheduleUpdate>(
    {
      mutationFn: (data) =>
        apiClient.put<WeeklyScheduleResponse>(
          "/hr/me/schedule",
          data,
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["availability"] });
      },
    },
    { url: "/api/v1/hr/me/schedule", method: "PUT" },
  );
}

/**
 * Hook for HR reading any employee's weekly working hours.
 *
 * @param staffId - Staff UUID whose week is wanted
 * @returns Query result with that employee's week and effective status
 */
export function useStaffSchedule(staffId?: string) {
  return useOfflineQuery<WeeklyScheduleResponse>({
    queryKey: ["availability", "staff", staffId],
    queryFn: () =>
      apiClient.get<WeeklyScheduleResponse>(
        `/hr/staff/${staffId}/schedule`,
      ),
    enabled: Boolean(staffId),
  });
}

/**
 * Hook for HR replacing any employee's weekly working hours.
 *
 * @param staffId - Staff UUID whose week is being rewritten
 * @returns Mutation for saving that employee's week
 */
export function useUpdateStaffSchedule(staffId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<WeeklyScheduleResponse, WeeklyScheduleUpdate>(
    {
      mutationFn: (data) =>
        apiClient.put<WeeklyScheduleResponse>(
          `/hr/staff/${staffId}/schedule`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["availability"] });
      },
    },
    { url: `/api/v1/hr/staff/${staffId}/schedule`, method: "PUT" },
  );
}