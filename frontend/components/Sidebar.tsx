"use client";

import type { ChatSummary } from "@/lib/types";

function relativeTime(ts: number): string {
  const diff = Math.max(0, Date.now() - ts);
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

export default function Sidebar({
  chats,
  activeId,
  onNew,
  onSwitch,
  onDelete,
  disabled,
}: {
  chats: ChatSummary[];
  activeId: string | null;
  onNew: () => void;
  onSwitch: (id: string) => void;
  onDelete: (id: string) => void;
  disabled?: boolean;
}) {
  return (
    <aside className="w-[260px] shrink-0 border-r border-border bg-parchmentAlt/60 flex flex-col h-screen sticky top-0">
      {/* Brand + new chat */}
      <div className="p-3 border-b border-border">
        <div className="flex items-center gap-2 px-1 py-2">
          <div className="h-7 w-7 rounded-md bg-accent grid place-items-center text-white text-sm font-semibold">
            L
          </div>
          <div>
            <div className="text-[13px] font-semibold text-ink leading-tight">
              Lenny's Podcast SME
            </div>
            <div className="text-[10.5px] text-inkMuted leading-tight">
              AI trained on every episode
            </div>
          </div>
        </div>
        <button
          onClick={onNew}
          disabled={disabled}
          className="mt-2 w-full flex items-center justify-center gap-2 rounded-lg border border-accent/30 bg-white hover:bg-accentSoft/60 text-accent text-[13px] font-medium py-2 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg width="14" height="14" viewBox="0 0 20 20" fill="none" aria-hidden>
            <path
              d="M10 4v12M4 10h12"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
            />
          </svg>
          New chat
        </button>
      </div>

      {/* Chat list */}
      <div className="flex-1 overflow-y-auto py-2 px-2">
        {chats.length === 0 ? (
          <p className="text-[12px] text-inkMuted px-2 py-4 leading-relaxed">
            No conversations yet. Ask your first question to get started.
          </p>
        ) : (
          <ul className="space-y-0.5">
            {chats.map((c) => (
              <li key={c.id}>
                <div
                  className={`group relative rounded-md text-[13px] transition ${
                    activeId === c.id
                      ? "bg-accentSoft/70 border border-accent/20"
                      : "hover:bg-white border border-transparent"
                  }`}
                >
                  <button
                    onClick={() => !disabled && onSwitch(c.id)}
                    disabled={disabled && activeId !== c.id}
                    className="w-full text-left px-3 py-2.5 pr-8 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <div className="truncate text-ink font-medium leading-snug">
                      {c.title || "New chat"}
                    </div>
                    <div className="text-[10.5px] text-inkMuted mt-0.5">
                      {relativeTime(c.updatedAt)}
                    </div>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm("Delete this conversation?")) onDelete(c.id);
                    }}
                    disabled={disabled}
                    aria-label="Delete chat"
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 focus:opacity-100 p-1.5 rounded hover:bg-white/70 text-inkMuted hover:text-accent transition disabled:opacity-0"
                  >
                    <svg width="13" height="13" viewBox="0 0 20 20" fill="none" aria-hidden>
                      <path
                        d="M5 6h10M8 6V4.5A1 1 0 0 1 9 3.5h2a1 1 0 0 1 1 1V6m-5 0v9a1 1 0 0 0 1 1h4a1 1 0 0 0 1-1V6"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                      />
                    </svg>
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-border text-[10.5px] text-inkMuted leading-relaxed space-y-1.5">
        <div>
          Built by{" "}
          <a
            href="https://www.linkedin.com/in/rahulthacker/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent font-medium hover:underline underline-offset-2"
          >
            Rahul Thacker
          </a>
        </div>
        <div>
          Unofficial fan project. Not affiliated with Lenny Rachitsky or Lenny's Newsletter.
        </div>
        <div>
          Conversations are stored in your browser only.
        </div>
      </div>
    </aside>
  );
}
