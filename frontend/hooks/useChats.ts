"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatSummary, Message } from "@/lib/types";
import {
  deleteChatStorage,
  deriveTitle,
  loadActive,
  loadIndex,
  loadMessages,
  newId,
  saveActive,
  saveIndex,
  saveMessages,
} from "@/lib/chats";

export function useChats() {
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessagesState] = useState<Message[]>([]);
  const hydrated = useRef(false);

  // Hydrate from localStorage on mount.
  useEffect(() => {
    const index = loadIndex().sort((a, b) => b.updatedAt - a.updatedAt);
    setChats(index);
    const active = loadActive();
    if (active && index.some((c) => c.id === active)) {
      setActiveId(active);
      setMessagesState(loadMessages(active));
    }
    hydrated.current = true;
  }, []);

  // Persist messages whenever they change. Also upsert the chat into the
  // index — a chat becomes "real" (gets a sidebar entry) once it has at
  // least one user message.
  useEffect(() => {
    if (!hydrated.current) return;
    if (!activeId) return;
    if (messages.length === 0) return;
    saveMessages(activeId, messages);
    setChats((prev) => {
      const existing = prev.find((c) => c.id === activeId);
      const now = Date.now();
      if (existing) {
        const updated: ChatSummary = {
          ...existing,
          title: existing.title || deriveTitle(messages),
          updatedAt: now,
        };
        const next = [updated, ...prev.filter((c) => c.id !== activeId)];
        saveIndex(next);
        return next;
      }
      const created: ChatSummary = {
        id: activeId,
        title: deriveTitle(messages),
        createdAt: now,
        updatedAt: now,
      };
      const next = [created, ...prev];
      saveIndex(next);
      return next;
    });
  }, [messages, activeId]);

  const setMessages = useCallback(
    (updater: Message[] | ((prev: Message[]) => Message[])) => {
      setMessagesState((prev) =>
        typeof updater === "function"
          ? (updater as (p: Message[]) => Message[])(prev)
          : updater
      );
    },
    []
  );

  const newChat = useCallback(() => {
    const id = newId();
    setActiveId(id);
    setMessagesState([]);
    saveActive(id);
  }, []);

  const switchChat = useCallback((id: string) => {
    setActiveId(id);
    setMessagesState(loadMessages(id));
    saveActive(id);
  }, []);

  const deleteChat = useCallback(
    (id: string) => {
      deleteChatStorage(id);
      setChats((prev) => {
        const next = prev.filter((c) => c.id !== id);
        saveIndex(next);
        return next;
      });
      if (id === activeId) {
        setActiveId(null);
        setMessagesState([]);
        saveActive(null);
      }
    },
    [activeId]
  );

  // Ensure there's always an active chat target for the composer.
  const ensureActiveChat = useCallback(() => {
    if (!activeId) {
      const id = newId();
      setActiveId(id);
      saveActive(id);
      return id;
    }
    return activeId;
  }, [activeId]);

  return {
    chats,
    activeId,
    messages,
    setMessages,
    newChat,
    switchChat,
    deleteChat,
    ensureActiveChat,
    hydrated: hydrated.current,
  };
}
