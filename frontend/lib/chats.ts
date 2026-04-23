import type { ChatSummary, Message } from "./types";

const INDEX_KEY = "lenny:chats:index";
const ACTIVE_KEY = "lenny:active";
const chatKey = (id: string) => `lenny:chats:${id}`;

export function loadIndex(): ChatSummary[] {
  try {
    const raw = localStorage.getItem(INDEX_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw) as ChatSummary[];
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export function saveIndex(chats: ChatSummary[]): void {
  try {
    localStorage.setItem(INDEX_KEY, JSON.stringify(chats));
  } catch {}
}

export function loadMessages(id: string): Message[] {
  try {
    const raw = localStorage.getItem(chatKey(id));
    if (!raw) return [];
    const arr = JSON.parse(raw) as Message[];
    // Strip any stale streaming flag — a crashed/refreshed mid-stream
    // message should restore as a completed (possibly incomplete) record.
    return arr.map((m) =>
      m.role === "assistant" ? { ...m, streaming: false } : m
    );
  } catch {
    return [];
  }
}

export function saveMessages(id: string, messages: Message[]): void {
  try {
    localStorage.setItem(chatKey(id), JSON.stringify(messages));
  } catch {}
}

export function deleteChatStorage(id: string): void {
  try {
    localStorage.removeItem(chatKey(id));
  } catch {}
}

export function loadActive(): string | null {
  try {
    return localStorage.getItem(ACTIVE_KEY);
  } catch {
    return null;
  }
}

export function saveActive(id: string | null): void {
  try {
    if (id) localStorage.setItem(ACTIVE_KEY, id);
    else localStorage.removeItem(ACTIVE_KEY);
  } catch {}
}

export function deriveTitle(messages: Message[]): string {
  const firstUser = messages.find((m) => m.role === "user");
  if (!firstUser) return "New chat";
  const text = firstUser.content.trim().replace(/\s+/g, " ");
  if (text.length <= 48) return text;
  // Prefer breaking at a word boundary near 48 chars.
  const cut = text.slice(0, 48);
  const lastSpace = cut.lastIndexOf(" ");
  return (lastSpace > 30 ? cut.slice(0, lastSpace) : cut).trim() + "…";
}

export function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `c_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}
