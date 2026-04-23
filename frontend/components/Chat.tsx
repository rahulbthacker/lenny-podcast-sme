"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import CitationCard from "./CitationCard";
import type { Citation, Message, OutOfScope } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8787";

/**
 * Smoothly reveals `source` one character at a time, even when tokens
 * arrive from the network in chunky bursts.
 */
function useSmoothStream(source: string): string {
  const [displayed, setDisplayed] = useState<string>("");
  const sourceRef = useRef(source);
  sourceRef.current = source;

  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    let carry = 0;

    const tick = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      setDisplayed((current) => {
        const target = sourceRef.current;
        if (current.length >= target.length) return current;
        const gap = target.length - current.length;
        const base = 80;
        const rate = gap > 500 ? base * 2 : gap > 200 ? base * 1.5 : base;
        const advanceF = rate * dt + carry;
        const advance = Math.floor(advanceF);
        carry = advanceF - advance;
        if (advance < 1) return current;
        return target.slice(0, current.length + advance);
      });
      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return displayed;
}

const SUGGESTIONS = [
  "How do I transition into product management from engineering?",
  "What's the best way to run a kickoff for a new PM team?",
  "How should an early-stage startup think about pricing?",
  "What separates great PMs from good ones?",
];

export default function Chat({
  messages,
  setMessages,
  ensureActiveChat,
}: {
  messages: Message[];
  setMessages: (updater: Message[] | ((prev: Message[]) => Message[])) => void;
  ensureActiveChat: () => string;
}) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const send = useCallback(
    async (questionOverride?: string) => {
      const q = (questionOverride ?? input).trim();
      if (!q || loading) return;
      ensureActiveChat();
      setInput("");
      setLoading(true);
      setMessages((prev) => [
        ...prev,
        { role: "user", content: q },
        { role: "assistant", content: "", citations: [], streaming: true },
      ]);

      try {
        const res = await fetch(`${API_BASE}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: q, k: 8 }),
        });
        if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          for (const line of lines) {
            if (!line.trim()) continue;
            let evt: { type: string; data?: unknown };
            try {
              evt = JSON.parse(line);
            } catch {
              continue;
            }
            if (evt.type === "out_of_scope") {
              const oos = evt.data as OutOfScope;
              setMessages((prev) => {
                const copy = [...prev];
                const i = copy.length - 1;
                const last = copy[i];
                if (last.role === "assistant") {
                  copy[i] = { ...last, outOfScope: oos, streaming: false };
                }
                return copy;
              });
            } else if (evt.type === "citations") {
              const cites = evt.data as Citation[];
              setMessages((prev) => {
                const copy = [...prev];
                const i = copy.length - 1;
                const last = copy[i];
                if (last.role === "assistant") {
                  copy[i] = { ...last, citations: cites };
                }
                return copy;
              });
            } else if (evt.type === "token") {
              const piece = evt.data as string;
              setMessages((prev) => {
                const copy = [...prev];
                const i = copy.length - 1;
                const last = copy[i];
                if (last.role === "assistant") {
                  copy[i] = { ...last, content: last.content + piece };
                }
                return copy;
              });
            } else if (evt.type === "done") {
              setMessages((prev) => {
                const copy = [...prev];
                const i = copy.length - 1;
                const last = copy[i];
                if (last.role === "assistant") {
                  copy[i] = { ...last, streaming: false };
                }
                return copy;
              });
            }
          }
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Unknown error";
        setMessages((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          if (last && last.role === "assistant") {
            copy[copy.length - 1] = {
              ...last,
              content: `**Error:** ${msg}\n\nIs the backend reachable at ${API_BASE}?`,
              streaming: false,
            };
          }
          return copy;
        });
      } finally {
        setLoading(false);
      }
    },
    [input, loading, setMessages, ensureActiveChat]
  );

  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const empty = messages.length === 0;

  return (
    <div className="flex flex-col h-screen flex-1 min-w-0">
      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-6 py-10">
          {empty ? (
            <EmptyState onPick={(q) => send(q)} />
          ) : (
            <div className="space-y-10">
              {messages.map((m, i) => (
                <MessageBlock
                  key={i}
                  message={m}
                  messageIdx={i}
                  onSuggestion={(q) => send(q)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Composer */}
      <div className="border-t border-border bg-parchment">
        <div className="mx-auto max-w-3xl px-6 py-4">
          <div className="rounded-2xl border border-border bg-white shadow-soft focus-within:border-accent/60 transition">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKey}
              rows={1}
              placeholder="Ask anything from Lenny's Podcast — product, growth, career…"
              className="w-full resize-none bg-transparent px-4 py-3 outline-none text-[15px] placeholder:text-inkMuted max-h-48"
            />
            <div className="flex items-center justify-between px-3 pb-2">
              <span className="text-xs text-inkMuted pl-1">
                Press Enter to send · Shift+Enter for newline
              </span>
              <button
                onClick={() => send()}
                disabled={loading || !input.trim()}
                className="h-8 px-4 rounded-lg bg-accent text-white text-sm font-medium disabled:opacity-40 hover:bg-accentDark transition"
              >
                {loading ? "Thinking…" : "Ask"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="text-center">
      <h2 className="font-serif text-3xl sm:text-4xl text-ink">
        Ask Lenny's Podcast anything.
      </h2>
      <p className="mt-3 text-inkMuted max-w-xl mx-auto">
        I've read every transcript. Ask a question and I'll answer with citations,
        timestamps, and links back to the source episodes.
      </p>
      <div className="mt-10 grid sm:grid-cols-2 gap-3 max-w-2xl mx-auto text-left">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onPick(s)}
            className="rounded-xl border border-border bg-white hover:bg-parchmentAlt px-4 py-3 text-sm text-ink transition"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageBlock({
  message,
  messageIdx,
  onSuggestion,
}: {
  message: Message;
  messageIdx: number;
  onSuggestion?: (q: string) => void;
}) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-accentSoft border border-accent/20 px-4 py-3 text-[15px]">
          {message.content}
        </div>
      </div>
    );
  }
  if (message.outOfScope) {
    return (
      <div className="animate-fadeIn rounded-2xl border border-border bg-parchmentAlt/60 p-5">
        <p className="text-[15px] text-ink/90 leading-relaxed">
          {message.outOfScope.message}
        </p>
        <div className="mt-4 grid sm:grid-cols-2 gap-2">
          {message.outOfScope.suggestions.map((s) => (
            <button
              key={s}
              onClick={() => onSuggestion?.(s)}
              className="text-left text-[13.5px] rounded-lg border border-border bg-white hover:bg-parchment px-3 py-2 transition"
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    );
  }
  const renderChips = (children: React.ReactNode): React.ReactNode =>
    renderCitationChips(children, message.citations, messageIdx);

  const smoothed = useSmoothStream(message.content);
  const fullyRevealed =
    !message.streaming && smoothed.length >= message.content.length;
  const displayText = fullyRevealed ? message.content : smoothed;
  const showCursor = !fullyRevealed;

  return (
    <div className="space-y-4">
      <div className="prose-chat text-[15.5px] text-ink/95 leading-relaxed font-serif">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            em: ({ children }) => <em className="italic">{children}</em>,
            p: ({ children }) => <p>{renderChips(children)}</p>,
            li: ({ children }) => <li>{renderChips(children)}</li>,
          }}
        >
          {displayText || (message.streaming ? "…" : "")}
        </ReactMarkdown>
        {showCursor && <span className="stream-cursor" aria-hidden="true" />}
      </div>
      {fullyRevealed && message.citations.length > 0 && (
        <div className="animate-fadeIn">
          <p className="text-[14px] text-ink/80 mb-3 border-t border-border pt-4">
            Want to go deeper? Here are the episodes most relevant to your question — tap any card to listen.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {message.citations.map((c, idx) => (
              <CitationCard
                key={c.chunk_id}
                idx={idx + 1}
                c={c}
                domId={`citation-${messageIdx}-${idx}`}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function scrollToCitation(domId: string) {
  const el = document.getElementById(domId);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.remove("card-highlight");
  void el.offsetWidth;
  el.classList.add("card-highlight");
  window.setTimeout(() => el.classList.remove("card-highlight"), 1600);
}

function CitationChip({
  n,
  cite,
  domId,
}: {
  n: number;
  cite?: Citation;
  domId: string;
}) {
  return (
    <span className="citation-chip-wrap">
      <button
        type="button"
        onClick={() => scrollToCitation(domId)}
        className="citation-chip"
        aria-label={cite ? `Source ${n}: ${cite.episode_title}` : `Source ${n}`}
      >
        {n}
      </button>
      {cite && (
        <span className="citation-tooltip" role="tooltip">
          <span className="citation-tooltip-title">{cite.episode_title}</span>
          <span className="citation-tooltip-meta">
            {cite.episode_guest}
            {cite.episode_date ? ` · ${cite.episode_date}` : ""}
            {` · ${cite.start_ts}`}
          </span>
        </span>
      )}
    </span>
  );
}

function renderCitationChips(
  children: React.ReactNode,
  citations: Citation[],
  messageIdx: number
): React.ReactNode {
  if (typeof children === "string") {
    const parts = children.split(/(\[E\d+\])/g);
    return parts.map((p, i) => {
      const m = p.match(/^\[E(\d+)\]$/);
      if (m) {
        const n = parseInt(m[1], 10);
        const cite = citations[n - 1];
        return (
          <CitationChip
            key={i}
            n={n}
            cite={cite}
            domId={`citation-${messageIdx}-${n - 1}`}
          />
        );
      }
      return <span key={i}>{p}</span>;
    });
  }
  if (Array.isArray(children)) {
    return children.map((c, i) => (
      <span key={i}>{renderCitationChips(c, citations, messageIdx)}</span>
    ));
  }
  return children;
}
