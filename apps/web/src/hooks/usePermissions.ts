"use client";

import { useCallback, useMemo } from "react";
import { useAuth } from "@/components/providers/AuthProvider";
import { PERMISSIONS, type PermissionString } from "@/lib/auth/permissions";

/** What the signed-in user's permissions let the interface do. */
export interface PermissionsApi {
  /** Effective permissions from the API, or undefined when not reported. */
  permissions: readonly string[] | undefined;
  /**
   * Whether the user holds a permission.
   *
   * Returns true when the API has not told us the permission list yet, or when
   * no permission is required. That is deliberate: the server is the authority
   * and refuses anything it should not allow, so the interface should not hide
   * a page from a user whose access it simply has not learned yet. A session
   * that predates permission reporting keeps working exactly as before.
   *
   * @param permission - Permission string to test, e.g. "clinical.view"
   * @returns True when the user may use the permission, or it is unknown
   */
  hasPermission: (permission?: PermissionString | string) => boolean;
  /**
   * Whether the user holds at least one of several permissions.
   *
   * @param required - Permission strings, any one of which is enough
   * @returns True when one is held, or the list is unknown
   */
  hasAnyPermission: (required: readonly string[]) => boolean;
  /** Whether the user may open the clinical workspace at all. */
  canSeeClinical: boolean;
}

/**
 * Read the signed-in user's effective permissions.
 *
 * The API answers "may this person open this part of Aifya?" from role,
 * facility overrides and per-person grants, and returns the answer with
 * /auth/me. This hook exposes it to the interface so a cashier never sees the
 * clinical workspace in the first place.
 *
 * @returns Permission helpers for the current user
 */
export function usePermissions(): PermissionsApi {
  const { user } = useAuth();
  const permissions = user?.permissions;

  const granted = useMemo(
    () => (permissions ? new Set(permissions) : null),
    [permissions],
  );

  const hasPermission = useCallback(
    (permission?: PermissionString | string) => {
      if (!permission) return true;
      // Unknown, not denied - see the note on PermissionsApi.
      if (!granted) return true;
      return granted.has(permission);
    },
    [granted],
  );

  const hasAnyPermission = useCallback(
    (required: readonly string[]) => {
      if (required.length === 0) return true;
      if (!granted) return true;
      return required.some((permission) => granted.has(permission));
    },
    [granted],
  );

  return {
    permissions,
    hasPermission,
    hasAnyPermission,
    canSeeClinical: hasPermission(PERMISSIONS.CLINICAL_VIEW),
  };
}
