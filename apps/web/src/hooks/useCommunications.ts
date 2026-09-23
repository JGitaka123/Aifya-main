"use client";

import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  MessageResponse,
  MessageListResponse,
  SendMessageRequest,
  BulkMessageRequest,
  CommunicationPreference,
  MessageTemplate,
  MessageTemplateCreate,
} from "@aifya/shared";

// ── Messages ────────────────────────────────────────────────────────────────

/**
 * Hook for fetching paginated message list.
 *
 * @param page - Page number (1-based)
 * @param perPage - Items per page
 * @param channel - Optional channel filter
 * @param status - Optional status filter
 * @returns Query result with paginated messages
 */
export function useMessages(
  page: number = 1,
  perPage: number = 20,
  channel?: string,
  status?: string,
) {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("per_page", String(perPage));
  if (channel) params.set("channel", channel);
  if (status) params.set("status", status);
  const qs = params.toString();

  return useOfflineQuery<MessageListResponse>({
    queryKey: ["communications", "messages", page, perPage, channel, status],
    queryFn: () =>
      apiClient.get<MessageListResponse>(`/communications/messages?${qs}`),
    refetchInterval: 30_000,
  });
}

/**
 * Hook for fetching a single message by ID.
 *
 * @param messageId - Message UUID
 * @returns Query result with message details
 */
export function useMessage(messageId: string | undefined) {
  return useOfflineQuery<MessageResponse>({
    queryKey: ["communications", "message", messageId],
    queryFn: () =>
      apiClient.get<MessageResponse>(`/communications/messages/${messageId}`),
    enabled: !!messageId,
  });
}

// ── Send Message ────────────────────────────────────────────────────────────

/**
 * Hook for sending a single patient message.
 *
 * @returns Mutation for sending messages
 */
export function useSendMessage() {
  return useOfflineMutation<MessageResponse, SendMessageRequest>(
    {
      mutationFn: (data: SendMessageRequest) =>
        apiClient.post<MessageResponse>(
          "/communications/messages/send",
          data,
          generateId(),
        ),
    },
    { url: "/api/v1/communications/messages/send", method: "POST" },
  );
}

/**
 * Hook for sending bulk messages.
 *
 * @returns Mutation for bulk message sending
 */
export function useBulkSend() {
  return useOfflineMutation<{ message_ids: string[] }, BulkMessageRequest>(
    {
      mutationFn: (data: BulkMessageRequest) =>
        apiClient.post<{ message_ids: string[] }>(
          "/communications/messages/bulk",
          data,
          generateId(),
        ),
    },
    { url: "/api/v1/communications/messages/bulk", method: "POST" },
  );
}

// ── Patient Preferences ─────────────────────────────────────────────────────

/**
 * Hook for fetching patient communication preferences.
 *
 * @param patientId - Patient UUID
 * @returns Query result with communication preferences
 */
export function useCommPreferences(patientId: string | undefined) {
  return useOfflineQuery<CommunicationPreference>({
    queryKey: ["communications", "preferences", patientId],
    queryFn: () =>
      apiClient.get<CommunicationPreference>(
        `/communications/preferences/${patientId}`,
      ),
    enabled: !!patientId,
  });
}

/**
 * Hook for updating patient communication preferences.
 *
 * @returns Mutation for updating preferences
 */
export function useUpdateCommPreferences(patientId: string) {
  return useOfflineMutation<
    CommunicationPreference,
    Partial<CommunicationPreference>
  >(
    {
      mutationFn: (data: Partial<CommunicationPreference>) =>
        apiClient.put<CommunicationPreference>(
          `/communications/preferences/${patientId}`,
          data,
          generateId(),
        ),
    },
    {
      url: `/api/v1/communications/preferences/${patientId}`,
      method: "PUT",
    },
  );
}

// ── Templates ───────────────────────────────────────────────────────────────

/**
 * Hook for fetching message templates.
 *
 * @returns Query result with template list
 */
export function useMessageTemplates() {
  return useOfflineQuery<MessageTemplate[]>({
    queryKey: ["communications", "templates"],
    queryFn: () =>
      apiClient.get<MessageTemplate[]>("/communications/templates"),
    refetchInterval: 120_000,
  });
}

/**
 * Hook for creating a new message template.
 *
 * @returns Mutation for template creation
 */
export function useCreateTemplate() {
  return useOfflineMutation<MessageTemplate, MessageTemplateCreate>(
    {
      mutationFn: (data: MessageTemplateCreate) =>
        apiClient.post<MessageTemplate>(
          "/communications/templates",
          data,
          generateId(),
        ),
    },
    { url: "/api/v1/communications/templates", method: "POST" },
  );
}
