import type { ReactNode } from "react";

/**
 * Layout wrapper for patient pages.
 * @param props.children - Patient page content
 * @returns Layout with children
 */
export default function PatientsLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
