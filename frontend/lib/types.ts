import type { Citation } from "@/components/CitationCard";

export type { Citation };

export type OutOfScope = { message: string; suggestions: string[] };

export type Message =
  | { role: "user"; content: string }
  | {
      role: "assistant";
      content: string;
      citations: Citation[];
      streaming?: boolean;
      outOfScope?: OutOfScope;
    };

export type ChatSummary = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
};
