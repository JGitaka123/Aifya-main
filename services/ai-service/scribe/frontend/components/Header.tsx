"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { usePathname } from "next/navigation";
import ThemeToggle from "@/components/ThemeToggle";

export function Header() {
  const { user, isAuthenticated, logout } = useAuth();
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  // Close on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMobileMenuOpen(false);
      }
    }
    if (mobileMenuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [mobileMenuOpen]);

  // Close on Escape key
  useEffect(() => {
    function handleEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setMobileMenuOpen(false);
    }
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, []);

  const navLinks = [
    { href: "/", label: "Home" },
    { href: "/clinician", label: "Clinician", roles: ["clinician", "superadmin"] },
    { href: "/billing", label: "Billing", roles: ["billing_admin", "facility_admin", "superadmin"] },
    { href: "/analytics", label: "Analytics", roles: ["billing_admin", "facility_admin", "superadmin"] },
    { href: "/admin", label: "Admin", roles: ["facility_admin", "superadmin"] },
  ];

  const visibleLinks = navLinks.filter(
    (link) => !link.roles || (user && link.roles.includes(user.role))
  );

  return (
    <header className="bg-medical-blue text-white shadow-md relative z-50" ref={menuRef}>
      <div className="max-w-7xl mx-auto px-4 md:px-6 lg:px-8 flex justify-between items-center h-16">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-2xl font-black tracking-tighter">AIFYA</span>
            <span className="text-sm font-normal opacity-80 border-l border-white/20 pl-2 hidden sm:inline">
              Mary Help Hospital
            </span>
          </Link>

          {/* Desktop Nav */}
          {isAuthenticated && (
            <nav className="hidden md:flex items-center gap-1" aria-label="Main navigation">
              {visibleLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    pathname === link.href
                      ? "bg-white/20 text-white"
                      : "text-white/70 hover:text-white hover:bg-white/10"
                  }`}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          )}
        </div>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          {isAuthenticated && user ? (
            <>
              <Link
                href="/profile"
                className="text-right hidden sm:block hover:opacity-80 transition-opacity"
                title="View profile settings"
              >
                <p className="text-sm font-medium">{user.full_name}</p>
                <p className="text-xs opacity-70 capitalize">{user.role.replace("_", " ")}</p>
              </Link>
              <button
                onClick={logout}
                className="px-3 py-1.5 text-sm bg-white/10 hover:bg-white/20 rounded-md transition-colors hidden md:block"
              >
                Sign Out
              </button>
              {/* Mobile hamburger */}
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="md:hidden p-2 rounded-md hover:bg-white/10 transition-colors"
                aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
                aria-expanded={mobileMenuOpen}
              >
                {mobileMenuOpen ? (
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                ) : (
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                )}
              </button>
            </>
          ) : (
            <Link
              href="/login"
              className="px-4 py-1.5 text-sm bg-white text-medical-blue font-medium rounded-md hover:bg-white/90 transition-colors"
            >
              Sign In
            </Link>
          )}
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && isAuthenticated && (
        <div className="md:hidden bg-medical-blue border-t border-white/10 shadow-lg">
          <nav className="px-4 py-3 space-y-1" aria-label="Mobile navigation">
            {visibleLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`block px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                  pathname === link.href
                    ? "bg-white/20 text-white"
                    : "text-white/70 hover:text-white hover:bg-white/10"
                }`}
              >
                {link.label}
              </Link>
            ))}
          </nav>
          <div className="px-4 py-3 border-t border-white/10">
            <div className="flex items-center justify-between">
              <Link href="/profile" className="hover:opacity-80 transition-opacity">
                <p className="text-sm font-medium">{user?.full_name}</p>
                <p className="text-xs opacity-70 capitalize">{user?.role.replace("_", " ")}</p>
              </Link>
              <button
                onClick={logout}
                className="px-3 py-1.5 text-sm bg-white/10 hover:bg-white/20 rounded-md transition-colors"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
