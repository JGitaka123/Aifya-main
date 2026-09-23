"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { useToast } from "@/components/Toast";

export default function ProfilePage() {
  const { user } = useAuth();
  const { toast } = useToast();

  // Profile form
  const [fullName, setFullName] = useState("");
  const [licenseNo, setLicenseNo] = useState("");
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);

  // Password form
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [showPasswords, setShowPasswords] = useState(false);

  const loadProfile = useCallback(async () => {
    try {
      const profile = await api.auth.profile();
      setFullName(profile.full_name || "");
      setLicenseNo(profile.license_no || "");
    } catch {
      // Fall back to local user data
      if (user) {
        setFullName(user.full_name || "");
      }
    }
  }, [user]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim()) {
      toast("Full name is required", "error");
      return;
    }
    setProfileLoading(true);
    try {
      await api.auth.updateProfile({
        full_name: fullName.trim(),
        license_no: licenseNo.trim() || undefined,
      });
      toast("Profile updated successfully", "success");
      setProfileSaved(true);
      setTimeout(() => setProfileSaved(false), 3000);
    } catch (err: any) {
      toast(err.message || "Failed to update profile", "error");
    } finally {
      setProfileLoading(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword.length < 8) {
      toast("Password must be at least 8 characters", "error");
      return;
    }
    if (newPassword !== confirmPassword) {
      toast("Passwords do not match", "error");
      return;
    }
    if (currentPassword === newPassword) {
      toast("New password must be different from current password", "error");
      return;
    }
    setPasswordLoading(true);
    try {
      await api.auth.changePassword(currentPassword, newPassword);
      toast("Password changed successfully", "success");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: any) {
      toast(err.message || "Failed to change password", "error");
    } finally {
      setPasswordLoading(false);
    }
  };

  const passwordStrength = (pw: string) => {
    if (!pw) return { label: "", color: "", width: "0%" };
    let score = 0;
    if (pw.length >= 8) score++;
    if (pw.length >= 12) score++;
    if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
    if (/\d/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;
    if (score <= 1) return { label: "Weak", color: "bg-red-500", width: "20%" };
    if (score === 2) return { label: "Fair", color: "bg-orange-500", width: "40%" };
    if (score === 3) return { label: "Good", color: "bg-yellow-500", width: "60%" };
    if (score === 4) return { label: "Strong", color: "bg-green-500", width: "80%" };
    return { label: "Very Strong", color: "bg-green-600", width: "100%" };
  };

  const strength = passwordStrength(newPassword);

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Profile &amp; Settings</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">Manage your account details and security</p>
      </div>

      {/* Account Info Card */}
      <div className="card p-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="h-16 w-16 bg-medical-blue/10 rounded-full flex items-center justify-center">
            <span className="text-2xl font-bold text-medical-blue">
              {user?.full_name?.charAt(0)?.toUpperCase() || "?"}
            </span>
          </div>
          <div>
            <p className="text-lg font-semibold text-slate-900 dark:text-white">{user?.full_name}</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">{user?.email}</p>
            <span className="inline-block mt-1 px-2 py-0.5 rounded text-xs font-medium bg-medical-blue/10 text-medical-blue capitalize">
              {user?.role?.replace("_", " ")}
            </span>
          </div>
        </div>

        <form onSubmit={handleSaveProfile} className="space-y-4">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
            Personal Information
          </h3>

          <div>
            <label htmlFor="fullName" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Full Name
            </label>
            <input
              id="fullName"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="input w-full"
              required
            />
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={user?.email || ""}
              className="input w-full bg-slate-50 dark:bg-slate-700 cursor-not-allowed"
              disabled
            />
            <p className="text-xs text-slate-400 mt-1">Email cannot be changed</p>
          </div>

          <div>
            <label htmlFor="licenseNo" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              License Number
            </label>
            <input
              id="licenseNo"
              type="text"
              value={licenseNo}
              onChange={(e) => setLicenseNo(e.target.value)}
              placeholder="e.g. KMPDB-12345"
              className="input w-full"
            />
          </div>

          <div className="flex items-center gap-3 pt-2">
            <button
              type="submit"
              disabled={profileLoading}
              className="btn-primary flex items-center gap-2"
            >
              {profileLoading ? (
                <>
                  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
                  Saving...
                </>
              ) : profileSaved ? (
                <>
                  <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                  Saved!
                </>
              ) : (
                "Save Changes"
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Change Password Card */}
      <div className="card p-6">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-4">
          Change Password
        </h3>

        <form onSubmit={handleChangePassword} className="space-y-4">
          <div>
            <label htmlFor="currentPassword" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Current Password
            </label>
            <input
              id="currentPassword"
              type={showPasswords ? "text" : "password"}
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="input w-full"
              required
              autoComplete="current-password"
            />
          </div>

          <div>
            <label htmlFor="newPassword" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              New Password
            </label>
            <input
              id="newPassword"
              type={showPasswords ? "text" : "password"}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="input w-full"
              required
              minLength={8}
              autoComplete="new-password"
            />
            {newPassword && (
              <div className="mt-2">
                <div className="h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${strength.color} transition-all duration-300 rounded-full`}
                    style={{ width: strength.width }}
                  />
                </div>
                <p className={`text-xs mt-1 ${
                  strength.label === "Weak" ? "text-red-500" :
                  strength.label === "Fair" ? "text-orange-500" :
                  strength.label === "Good" ? "text-yellow-600" :
                  "text-green-600"
                }`}>
                  {strength.label}
                </p>
              </div>
            )}
          </div>

          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Confirm New Password
            </label>
            <input
              id="confirmPassword"
              type={showPasswords ? "text" : "password"}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="input w-full"
              required
              minLength={8}
              autoComplete="new-password"
            />
            {confirmPassword && newPassword !== confirmPassword && (
              <p className="text-xs text-red-500 mt-1">Passwords do not match</p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="showPasswords"
              checked={showPasswords}
              onChange={(e) => setShowPasswords(e.target.checked)}
              className="rounded border-slate-300"
            />
            <label htmlFor="showPasswords" className="text-sm text-slate-600 dark:text-slate-400">
              Show passwords
            </label>
          </div>

          <button
            type="submit"
            disabled={passwordLoading || !currentPassword || !newPassword || newPassword !== confirmPassword}
            className="btn-primary flex items-center gap-2"
          >
            {passwordLoading ? (
              <>
                <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
                Changing...
              </>
            ) : (
              "Change Password"
            )}
          </button>
        </form>
      </div>

      {/* Session Info */}
      <div className="card p-6">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-4">
          Session Information
        </h3>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-500 dark:text-slate-400">Account Status</span>
            <span className={`font-medium ${user?.is_active ? "text-green-600" : "text-red-600"}`}>
              {user?.is_active ? "Active" : "Disabled"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500 dark:text-slate-400">Role</span>
            <span className="text-slate-800 dark:text-slate-200 capitalize font-medium">{user?.role?.replace("_", " ")}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500 dark:text-slate-400">Keyboard Shortcuts</span>
            <span className="text-slate-600 dark:text-slate-300 font-mono text-xs">Ctrl+/ to view</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500 dark:text-slate-400">Command Palette</span>
            <span className="text-slate-600 dark:text-slate-300 font-mono text-xs">Ctrl+K to open</span>
          </div>
        </div>
      </div>
    </div>
  );
}
