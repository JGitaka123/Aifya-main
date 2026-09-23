"use client";

import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  HRSummary,
  StaffDirectoryResponse,
  StaffProfileResponse,
  StaffProfileCreate,
  ShiftResponse,
  ShiftCreate,
  ShiftAssignmentListResponse,
  ShiftAssignmentCreate,
  ShiftAssignmentResponse,
  LeaveRequestListResponse,
  LeaveRequestCreate,
  LeaveRequestResponse,
  LeaveApprovalRequest,
  AttendanceListResponse,
  AttendanceResponse,
  AttendanceClockIn,
  AttendanceClockOut,
} from "@aifya/shared";

// ── Summary ────────────────────────────────────────────────────────────────

/**
 * Hook for fetching HR dashboard summary.
 *
 * @returns Query result with HR summary stats
 */
export function useHRSummary() {
  return useOfflineQuery<HRSummary>({
    queryKey: ["hr", "summary"],
    queryFn: () => apiClient.get<HRSummary>("/hr/summary"),
    refetchInterval: 30_000,
  });
}

// ── Staff Directory ────────────────────────────────────────────────────────

/**
 * Hook for fetching staff directory.
 *
 * @param role - Optional role filter
 * @param departmentId - Optional department filter
 * @param search - Optional search query
 * @returns Query result with staff directory
 */
export function useStaffDirectory(
  role?: string,
  departmentId?: string,
  search?: string
) {
  const params = new URLSearchParams();
  if (role) params.set("role", role);
  if (departmentId) params.set("department_id", departmentId);
  if (search) params.set("search", search);
  const qs = params.toString();

  return useOfflineQuery<StaffDirectoryResponse>({
    queryKey: ["hr", "staff", role, departmentId, search],
    queryFn: () =>
      apiClient.get<StaffDirectoryResponse>(
        `/hr/staff${qs ? `?${qs}` : ""}`
      ),
    refetchInterval: 30_000,
  });
}

// ── Staff Profile ──────────────────────────────────────────────────────────

/**
 * Hook for fetching a staff profile.
 *
 * @param staffId - Staff UUID
 * @returns Query result with staff profile
 */
export function useStaffProfile(staffId?: string) {
  return useOfflineQuery<StaffProfileResponse>({
    queryKey: ["hr", "profile", staffId],
    queryFn: () =>
      apiClient.get<StaffProfileResponse>(`/hr/staff/${staffId}/profile`),
    enabled: !!staffId,
  });
}

/**
 * Hook for creating/updating a staff profile.
 *
 * @param staffId - Staff UUID
 * @returns Mutation for upserting profile
 */
export function useUpsertProfile(staffId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<StaffProfileResponse, StaffProfileCreate>(
    {
      mutationFn: (data) =>
        apiClient.put<StaffProfileResponse>(
          `/hr/staff/${staffId}/profile`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["hr", "profile", staffId] });
      },
    },
    { url: `/api/v1/hr/staff/${staffId}/profile`, method: "PUT" },
  );
}

// ── Shifts ─────────────────────────────────────────────────────────────────

/**
 * Hook for fetching shift definitions.
 *
 * @returns Query result with shifts
 */
export function useShifts() {
  return useOfflineQuery<ShiftResponse[]>({
    queryKey: ["hr", "shifts"],
    queryFn: () => apiClient.get<ShiftResponse[]>("/hr/shifts"),
  });
}

/**
 * Hook for creating a shift.
 *
 * @returns Mutation for creating a shift
 */
export function useCreateShift() {
  const qc = useQueryClient();
  return useOfflineMutation<ShiftResponse, ShiftCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<ShiftResponse>("/hr/shifts", data, generateId()),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["hr", "shifts"] });
      },
    },
    { url: "/api/v1/hr/shifts", method: "POST" },
  );
}

// ── Shift Assignments ──────────────────────────────────────────────────────

/**
 * Hook for fetching shift assignments.
 *
 * @param date - Optional date filter
 * @param staffId - Optional staff filter
 * @returns Query result with shift assignments
 */
export function useShiftAssignments(date?: string, staffId?: string) {
  const params = new URLSearchParams();
  if (date) params.set("date", date);
  if (staffId) params.set("staff_id", staffId);
  const qs = params.toString();

  return useOfflineQuery<ShiftAssignmentListResponse>({
    queryKey: ["hr", "shift-assignments", date, staffId],
    queryFn: () =>
      apiClient.get<ShiftAssignmentListResponse>(
        `/hr/shift-assignments${qs ? `?${qs}` : ""}`
      ),
    refetchInterval: 15_000,
  });
}

/**
 * Hook for creating a shift assignment.
 *
 * @returns Mutation for assigning a shift
 */
export function useCreateShiftAssignment() {
  const qc = useQueryClient();
  return useOfflineMutation<ShiftAssignmentResponse, ShiftAssignmentCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<ShiftAssignmentResponse>(
          "/hr/shift-assignments",
          data,
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["hr", "shift-assignments"] });
      },
    },
    { url: "/api/v1/hr/shift-assignments", method: "POST" },
  );
}

// ── Leave Requests ─────────────────────────────────────────────────────────

/**
 * Hook for fetching leave requests.
 *
 * @param staffId - Optional staff filter
 * @param status - Optional status filter
 * @returns Query result with leave requests
 */
export function useLeaveRequests(staffId?: string, status?: string) {
  const params = new URLSearchParams();
  if (staffId) params.set("staff_id", staffId);
  if (status) params.set("status", status);
  const qs = params.toString();

  return useOfflineQuery<LeaveRequestListResponse>({
    queryKey: ["hr", "leave", staffId, status],
    queryFn: () =>
      apiClient.get<LeaveRequestListResponse>(
        `/hr/leave${qs ? `?${qs}` : ""}`
      ),
    refetchInterval: 15_000,
  });
}

/**
 * Hook for creating a leave request.
 *
 * @returns Mutation for creating leave request
 */
export function useCreateLeaveRequest() {
  const qc = useQueryClient();
  return useOfflineMutation<LeaveRequestResponse, LeaveRequestCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<LeaveRequestResponse>("/hr/leave", data, generateId()),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["hr", "leave"] });
      },
    },
    { url: "/api/v1/hr/leave", method: "POST" },
  );
}

/**
 * Hook for processing (approve/reject) a leave request.
 *
 * @param leaveId - Leave request UUID
 * @returns Mutation for processing leave
 */
export function useProcessLeave(leaveId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<LeaveRequestResponse, LeaveApprovalRequest>(
    {
      mutationFn: (data) =>
        apiClient.post<LeaveRequestResponse>(
          `/hr/leave/${leaveId}/process`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["hr", "leave"] });
      },
    },
    { url: `/api/v1/hr/leave/${leaveId}/process`, method: "POST" },
  );
}

// ── Attendance ─────────────────────────────────────────────────────────────

/**
 * Hook for fetching attendance records.
 *
 * @param date - Optional date filter
 * @param staffId - Optional staff filter
 * @returns Query result with attendance records
 */
export function useAttendance(date?: string, staffId?: string) {
  const params = new URLSearchParams();
  if (date) params.set("date", date);
  if (staffId) params.set("staff_id", staffId);
  const qs = params.toString();

  return useOfflineQuery<AttendanceListResponse>({
    queryKey: ["hr", "attendance", date, staffId],
    queryFn: () =>
      apiClient.get<AttendanceListResponse>(
        `/hr/attendance${qs ? `?${qs}` : ""}`
      ),
    refetchInterval: 15_000,
  });
}

/**
 * Hook for clocking in.
 *
 * @returns Mutation for clock-in
 */
export function useClockIn() {
  const qc = useQueryClient();
  return useOfflineMutation<AttendanceResponse, AttendanceClockIn>(
    {
      mutationFn: (data) =>
        apiClient.post<AttendanceResponse>(
          "/hr/attendance/clock-in",
          data,
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["hr", "attendance"] });
      },
    },
    { url: "/api/v1/hr/attendance/clock-in", method: "POST" },
  );
}

/**
 * Hook for clocking out.
 *
 * @param attendanceId - Attendance UUID
 * @returns Mutation for clock-out
 */
export function useClockOut(attendanceId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<AttendanceResponse, AttendanceClockOut>(
    {
      mutationFn: (data) =>
        apiClient.post<AttendanceResponse>(
          `/hr/attendance/${attendanceId}/clock-out`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["hr", "attendance"] });
      },
    },
    {
      url: `/api/v1/hr/attendance/${attendanceId}/clock-out`,
      method: "POST",
    },
  );
}
