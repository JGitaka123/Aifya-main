"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  MessageSquare,
  Send,
  Phone,
  Mail,
  Filter,
  Plus,
  CheckCircle2,
  Clock,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { StatCardSkeleton, Skeleton } from "@/components/ui/Skeleton";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { PatientLookup } from "@/components/patients/PatientLookup";
import { useMessages, useMessageTemplates, useSendMessage } from "@/hooks/useCommunications";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type {
  MessageChannel,
  MessageStatus,
  MessageCategory,
  MessageTemplate,
  Patient,
} from "@aifya/shared";

/** Channel display config. */
const CHANNEL_DISPLAY: Record<MessageChannel, { label: string; color: string }> = {
  sms: { label: "SMS", color: "text-blue-600 dark:text-blue-400" },
  whatsapp: { label: "WhatsApp", color: "text-green-600 dark:text-green-400" },
  email: { label: "Email", color: "text-purple-600 dark:text-purple-400" },
};

/** Status display config. */
const STATUS_MAP: Record<MessageStatus, { variant: "success" | "warning" | "danger" | "info" | "neutral"; label: string }> = {
  queued: { variant: "neutral", label: "Queued" },
  sent: { variant: "info", label: "Sent" },
  delivered: { variant: "success", label: "Delivered" },
  read: { variant: "success", label: "Read" },
  failed: { variant: "danger", label: "Failed" },
};

/**
 * Patient Communication Hub page.
 * Manages SMS/WhatsApp messaging, templates, and delivery tracking.
 *
 * @returns Communications page component
 */
export default function CommunicationsPage() {
  const t = useTranslations("communications");
  const tc = useTranslations("common");

  const [page, setPage] = useState(1);
  const [channelFilter, setChannelFilter] = useState<string | undefined>();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [showSendDialog, setShowSendDialog] = useState(false);

  const messagesQuery = useMessages(page, 20, channelFilter, statusFilter);
  const templatesQuery = useMessageTemplates();

  const messages = messagesQuery.data;
  const templates = templatesQuery.data;

  // Stats from current page
  const totalMessages = messages?.total ?? 0;
  const deliveredCount = messages?.items.filter((m) => m.status === "delivered" || m.status === "read").length ?? 0;
  const failedCount = messages?.items.filter((m) => m.status === "failed").length ?? 0;
  const queuedCount = messages?.items.filter((m) => m.status === "queued" || m.status === "sent").length ?? 0;

  return (
    <div className="flex flex-col gap-6 p-6">
      <PageHeader
        title={t("title")}
        subtitle={t("subtitle")}
        icon={MessageSquare}
        actions={
          <button
            onClick={() => setShowSendDialog(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
          >
            <Send className="h-4 w-4" />
            {t("sendMessage")}
          </button>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {messagesQuery.isLoading ? (
          Array.from({ length: 4 }).map((_, i) => <StatCardSkeleton key={i} />)
        ) : (
          <>
            <StatCard
              title={t("totalMessages")}
              value={totalMessages}
              icon={MessageSquare}
              trend={null}
            />
            <StatCard
              title={t("delivered")}
              value={deliveredCount}
              icon={CheckCircle2}
              trend={null}
            />
            <StatCard
              title={t("inQueue")}
              value={queuedCount}
              icon={Clock}
              trend={null}
            />
            <StatCard
              title={t("failed")}
              value={failedCount}
              icon={AlertCircle}
              trend={null}
            />
          </>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Filter className="h-4 w-4" />
          {t("filters")}
        </div>

        <select
          value={channelFilter ?? ""}
          onChange={(e) => {
            setChannelFilter(e.target.value || undefined);
            setPage(1);
          }}
          className="rounded-lg border border-input bg-background px-3 py-1.5 text-sm shadow-sm"
        >
          <option value="">{t("allChannels")}</option>
          <option value="sms">SMS</option>
          <option value="whatsapp">WhatsApp</option>
          <option value="email">Email</option>
        </select>

        <select
          value={statusFilter ?? ""}
          onChange={(e) => {
            setStatusFilter(e.target.value || undefined);
            setPage(1);
          }}
          className="rounded-lg border border-input bg-background px-3 py-1.5 text-sm shadow-sm"
        >
          <option value="">{t("allStatuses")}</option>
          <option value="queued">{t("statusQueued")}</option>
          <option value="sent">{t("statusSent")}</option>
          <option value="delivered">{t("statusDelivered")}</option>
          <option value="read">{t("statusRead")}</option>
          <option value="failed">{t("statusFailed")}</option>
        </select>

        <button
          onClick={() => messagesQuery.refetch()}
          className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-input px-3 py-1.5 text-sm shadow-sm transition-colors hover:bg-muted"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", messagesQuery.isFetching && "animate-spin")} />
          {tc("search")}
        </button>
      </div>

      {/* Message Table */}
      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">{t("recipient")}</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">{t("channel")}</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">{t("category")}</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">{t("status")}</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">{t("sentAt")}</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">{t("body")}</th>
              </tr>
            </thead>
            <tbody>
              {messagesQuery.isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="border-b border-border">
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <Skeleton className="h-4 w-24" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : messages?.items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-muted-foreground">
                    {tc("noResults")}
                  </td>
                </tr>
              ) : (
                messages?.items.map((msg) => {
                  const channelInfo = CHANNEL_DISPLAY[msg.channel];
                  const statusInfo = STATUS_MAP[msg.status];
                  return (
                    <tr
                      key={msg.id}
                      className="border-b border-border transition-colors hover:bg-muted/20"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          {msg.channel === "email" ? (
                            <Mail className="h-3.5 w-3.5 text-muted-foreground" />
                          ) : (
                            <Phone className="h-3.5 w-3.5 text-muted-foreground" />
                          )}
                          <span className="font-mono text-xs">
                            {msg.channel === "email"
                              ? (msg.recipient_email ?? "—")
                              : msg.recipient_phone}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn("text-xs font-semibold", channelInfo.color)}>
                          {channelInfo.label}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="rounded-md bg-muted px-2 py-0.5 text-xs">
                          {msg.category.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge variant={statusInfo.variant}>
                          {statusInfo.label}
                        </StatusBadge>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        {msg.sent_at
                          ? new Date(msg.sent_at).toLocaleString()
                          : "-"}
                      </td>
                      <td className="max-w-[200px] truncate px-4 py-3 text-xs text-muted-foreground">
                        {msg.body}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {messages && messages.total > 0 && (
          <div className="flex items-center justify-between border-t border-border px-4 py-3">
            <span className="text-xs text-muted-foreground">
              {t("showing")} {(page - 1) * 20 + 1}-
              {Math.min(page * 20, messages.total)} {tc("totalItems")} {messages.total}
            </span>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="rounded-lg border border-input px-3 py-1 text-xs transition-colors hover:bg-muted disabled:opacity-40"
              >
                {tc("back")}
              </button>
              <button
                disabled={page * 20 >= messages.total}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg border border-input px-3 py-1 text-xs transition-colors hover:bg-muted disabled:opacity-40"
              >
                {tc("next")}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Templates Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">{t("templates")}</h2>
          <button className="inline-flex items-center gap-1.5 rounded-lg border border-input px-3 py-1.5 text-sm shadow-sm transition-colors hover:bg-muted">
            <Plus className="h-3.5 w-3.5" />
            {t("newTemplate")}
          </button>
        </div>

        {templatesQuery.isLoading ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-28 rounded-xl" />
            ))}
          </div>
        ) : templates?.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            {t("noTemplates")}
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {templates?.map((tmpl) => (
              <div
                key={tmpl.id}
                className="rounded-xl border border-border bg-card p-4 shadow-sm transition-colors hover:bg-muted/20"
              >
                <div className="mb-2 flex items-center justify-between">
                  <span className="font-medium text-foreground">{tmpl.name}</span>
                  <span className={cn("text-xs font-semibold", CHANNEL_DISPLAY[tmpl.channel]?.color)}>
                    {CHANNEL_DISPLAY[tmpl.channel]?.label}
                  </span>
                </div>
                <span className="mb-2 inline-block rounded-md bg-muted px-2 py-0.5 text-xs">
                  {tmpl.category.replace(/_/g, " ")}
                </span>
                <p className="line-clamp-2 text-xs text-muted-foreground">
                  {tmpl.body_template}
                </p>
                <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                  <span>{tmpl.language.toUpperCase()}</span>
                  <span className={tmpl.is_active ? "text-green-600 dark:text-green-400" : "text-red-500"}>
                    {tmpl.is_active ? t("active") : t("inactive")}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Send Message Dialog (simple inline form) */}
      {showSendDialog && (
        <SendMessageDialog
          onClose={() => setShowSendDialog(false)}
          templates={templates ?? []}
        />
      )}
    </div>
  );
}

// ── Send Message Dialog ─────────────────────────────────────────────────────

/**
 * Inline dialog for sending a new message.
 *
 * @param onClose - Callback to close dialog
 * @param templates - Available message templates
 * @returns Send message dialog component
 */
function SendMessageDialog({
  onClose,
  templates,
}: {
  onClose: () => void;
  templates: MessageTemplate[];
}) {
  const t = useTranslations("communications");
  const tc = useTranslations("common");
  const sendMessage = useSendMessage();

  const [form, setForm] = useState<{
    patient: Patient | null;
    channel: MessageChannel;
    category: MessageCategory;
    template_id: string;
    subject: string;
    body: string;
  }>({
    patient: null,
    channel: "sms",
    category: "custom",
    template_id: "",
    subject: "",
    body: "",
  });
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.patient) {
      setError(t("patientRequired"));
      return;
    }
    setError("");
    try {
      const result = await sendMessage.mutateAsync({
        patient_id: form.patient.id,
        channel: form.channel,
        category: form.category,
        template_id: form.template_id || undefined,
        body: form.body || undefined,
        subject: form.subject || undefined,
      });
      // A message can be recorded yet not delivered (e.g. the channel has no
      // provider credentials). Keep the dialog open and say why.
      if (result.status === "failed") {
        setError(result.error_message || t("sendFailed"));
        return;
      }
      onClose();
    } catch (err) {
      setError(
        err instanceof ApiError && err.message ? err.message : tc("retrySync")
      );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-xl">
        <h3 className="mb-4 text-lg font-semibold">{t("sendMessage")}</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <PatientLookup
            value={form.patient}
            onSelect={(patient) => setForm({ ...form, patient })}
            required
          />

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium">{t("channel")}</label>
              <select
                value={form.channel}
                onChange={(e) => setForm({ ...form, channel: e.target.value as MessageChannel })}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm"
              >
                <option value="sms">SMS</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="email">Email</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">{t("category")}</label>
              <select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value as MessageCategory })}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm"
              >
                <option value="appointment_reminder">Appointment Reminder</option>
                <option value="lab_result">Lab Result</option>
                <option value="prescription_alert">Prescription Alert</option>
                <option value="anc_reminder">ANC Reminder</option>
                <option value="immunization_reminder">Immunization Reminder</option>
                <option value="discharge_instructions">Discharge Instructions</option>
                <option value="follow_up">Follow Up</option>
                <option value="billing_notification">Billing Notification</option>
                <option value="custom">Custom</option>
              </select>
            </div>
          </div>

          {form.channel === "email" && (
            <div>
              <label className="mb-1 block text-sm font-medium">
                {t("subject")}
              </label>
              <input
                type="text"
                value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })}
                maxLength={200}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm"
                placeholder={t("subjectPlaceholder")}
              />
            </div>
          )}

          {templates.length > 0 && (
            <div>
              <label className="mb-1 block text-sm font-medium">{t("template")}</label>
              <select
                value={form.template_id}
                onChange={(e) => setForm({ ...form, template_id: e.target.value })}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm"
              >
                <option value="">{t("noTemplate")}</option>
                {templates
                  .filter((tmpl) => tmpl.channel === form.channel && tmpl.is_active)
                  .map((tmpl) => (
                    <option key={tmpl.id} value={tmpl.id}>
                      {tmpl.name}
                    </option>
                  ))}
              </select>
            </div>
          )}

          {!form.template_id && (
            <div>
              <label className="mb-1 block text-sm font-medium">{t("messageBody")}</label>
              <textarea
                value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })}
                rows={3}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm"
                placeholder={t("typeMessage")}
              />
            </div>
          )}

          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-input px-4 py-2 text-sm transition-colors hover:bg-muted"
            >
              {tc("cancel")}
            </button>
            <button
              type="submit"
              disabled={sendMessage.isPending}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
              {sendMessage.isPending ? tc("loading") : t("send")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
