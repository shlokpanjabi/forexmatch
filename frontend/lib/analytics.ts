import { API_BASE } from "./api";

/**
 * Analytics is best-effort and must never affect the page.
 *
 * Events go through our own backend rather than a third-party script, so the
 * allow-list of events and properties is enforced server-side.
 */
export function track(
  event: string,
  sessionId: string | null,
  properties: Record<string, unknown> = {},
): void {
  if (!sessionId) return;
  void fetch(`${API_BASE}/api/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event, session_id: sessionId, properties }),
    keepalive: true,
  }).catch(() => {
    // Deliberately ignored.
  });
}
