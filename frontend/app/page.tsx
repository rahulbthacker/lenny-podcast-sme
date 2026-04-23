"use client";

import Chat from "@/components/Chat";
import Sidebar from "@/components/Sidebar";
import { useChats } from "@/hooks/useChats";

export default function Home() {
  const {
    chats,
    activeId,
    messages,
    setMessages,
    newChat,
    switchChat,
    deleteChat,
    ensureActiveChat,
  } = useChats();

  const isStreaming = messages.some(
    (m) => m.role === "assistant" && m.streaming
  );

  return (
    <div className="flex min-h-screen">
      <Sidebar
        chats={chats}
        activeId={activeId}
        onNew={newChat}
        onSwitch={switchChat}
        onDelete={deleteChat}
        disabled={isStreaming}
      />
      <Chat
        messages={messages}
        setMessages={setMessages}
        ensureActiveChat={ensureActiveChat}
      />
    </div>
  );
}
