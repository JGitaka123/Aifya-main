/**
 * The signed-in staff member, as the web app keeps them in its auth context.
 *
 * `permissions` is the effective list the API resolved for this person from
 * their role, their facility's `role_permissions` overrides and any per-person
 * grant on the staff record. The web app uses it to hide navigation and
 * actions it knows are forbidden; the API enforces the same list again on
 * every request, so a stale copy here can mislead the menu but cannot open a
 * door on its own.
 */
export interface AuthUser {
  /** Staff UUID. */
  id: string;
  email: string;
  name: string;
  /** Roles carried by the access token. */
  roles: string[];
  facilityId: string;
  /**
   * The hospital or clinic this session belongs to.
   *
   * Shown in the workspace header so anyone signed in at a facility can see
   * which one they are working in. Absent on sessions issued before the API
   * reported it, so treat it as "unknown" and fall back rather than blank.
   */
  facilityName?: string | null;
  /** Unit the staff member is rostered to, when they have one. */
  departmentId?: string | null;
  departmentName?: string | null;
  /**
   * Effective permission strings, e.g. "clinical.view".
   *
   * Absent when the session predates permission reporting. Treat absent as
   * "unknown" rather than "none" - an older session must not hide the whole
   * app from someone who can still use it.
   */
  permissions?: string[];
}
