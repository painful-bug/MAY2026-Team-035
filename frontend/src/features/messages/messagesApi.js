import { api } from '../../lib/api/client';

// Direct messages (0046): the chat dock's API. Thin, like every real-API file.

const post = (path, body = {}) => api(path, { method: 'POST', body: JSON.stringify(body) });

export const messagesApi = {
  /** Who I can start a thread with in one community. */
  recipients: (communityId) =>
    api(`/messages/recipients?communityId=${encodeURIComponent(communityId)}`),
  /** One mailbox across every community; RLS makes the list mine. */
  threads: () => api('/messages/threads'),
  thread: (threadId) => api(`/messages/threads/${threadId}`),
  /**
   * Open (or return) a thread — idempotent on the pair. Pass either
   * `{ communityId, recipientProfileId }` or `{ workOrderId }`.
   */
  openThread: (payload) => post('/messages/threads', payload),
  send: (threadId, body) => post(`/messages/threads/${threadId}/messages`, { body }),
};

/**
 * Ask the dock to open, optionally straight onto the New-message view for one
 * community. A window event rather than context plumbing, because the dock is
 * mounted outside <Routes> and its openers are scattered across portals.
 */
export function openChatDock(detail = {}) {
  window.dispatchEvent(new CustomEvent('hb:chat-open', { detail }));
}
