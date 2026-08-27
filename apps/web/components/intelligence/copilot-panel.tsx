"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { Sparkles, Send, Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { CopilotChatRequest, CopilotChatResponse, CopilotChatTurn } from "@/lib/types";
import { Card, CardHeader, CardBody, Badge } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface DisplayMessage extends CopilotChatTurn {
  citations?: { incident_id: string; label: string }[];
  grounded?: boolean;
}

const MAX_HISTORY_TURNS = 12;

/**
 * Phase 5B -- conversational copilot over the existing AI/incident data.
 * Stateless server-side: the full turn history is resent with every request,
 * matching the backend's copilot/schemas.py contract. This component is used
 * both on the Intelligence overview (no focused incident) and on an incident
 * detail page (passes incidentId so the assistant's context is scoped to it).
 */
export function CopilotPanel({ incidentId, title }: { incidentId?: string; title?: string }) {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  async function sendMessage() {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    const userTurn: DisplayMessage = { role: "user", content: trimmed };
    const nextMessages = [...messages, userTurn];
    setMessages(nextMessages);
    setInput("");
    setSending(true);
    setError(null);

    const history = nextMessages.slice(0, -1).slice(-MAX_HISTORY_TURNS).map(({ role, content }) => ({ role, content }));

    try {
      const payload: CopilotChatRequest = { message: trimmed, history, incident_id: incidentId ?? null };
      const resp = await api.post<CopilotChatResponse>("/v1/insights/intelligence/copilot/chat", payload);
      setMessages((prev) => [...prev, { role: "assistant", content: resp.answer, citations: resp.citations, grounded: resp.grounded }]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't reach the copilot. Please try again.");
      setMessages((prev) => prev.slice(0, -1)); // drop the optimistic user turn so it can be retried cleanly
      setInput(trimmed);
    } finally {
      setSending(false);
    }
  }

  return (
    <Card className="flex flex-col">
      <CardHeader className="flex items-center gap-2">
        <Sparkles className="h-3.5 w-3.5 text-signal-amber" />
        <span className="text-xs font-medium text-graphite-700 dark:text-graphite-200">
          {title ?? "Ask Copilot"}
        </span>
      </CardHeader>
      <CardBody className="flex flex-col gap-3">
        <div ref={scrollRef} className="flex max-h-80 min-h-[6rem] flex-col gap-2.5 overflow-y-auto">
          {messages.length === 0 && !sending && (
            <p className="text-xs text-graphite-500">
              {incidentId
                ? "Ask about this incident \u2014 likely cause, recommendations, or what to check next."
                : "Ask about your delivery health, recent incidents, or what's failing right now."}
            </p>
          )}
          {messages.map((m, i) => (
            <MessageBubble key={i} message={m} />
          ))}
          {sending && (
            <div className="flex items-center gap-1.5 text-xs text-graphite-500">
              <Loader2 className="h-3 w-3 animate-spin" />
              Thinking…
            </div>
          )}
        </div>

        {error && <p className="text-xs text-signal-red">{error}</p>}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage();
          }}
          className="flex items-center gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={incidentId ? "Ask about this incident…" : "Ask Copilot a question…"}
            maxLength={2000}
            disabled={sending}
            className="h-9 flex-1 rounded border border-graphite-200 bg-white px-3 text-sm text-graphite-950 placeholder:text-graphite-400 outline-none transition-colors focus:border-signal-amber disabled:opacity-60 dark:border-graphite-700 dark:bg-graphite-900 dark:text-graphite-50"
          />
          <Button type="submit" size="sm" disabled={sending || !input.trim()} aria-label="Send">
            <Send className="h-3.5 w-3.5" />
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}

function MessageBubble({ message }: { message: DisplayMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex flex-col gap-1 ${isUser ? "items-end" : "items-start"}`}>
      <div
        className={`max-w-[85%] rounded-md px-3 py-2 text-xs leading-relaxed ${
          isUser
            ? "bg-signal-amber text-white"
            : "bg-graphite-50 text-graphite-900 dark:bg-graphite-800 dark:text-graphite-100"
        }`}
      >
        {message.content}
      </div>
      {!isUser && message.grounded === false && (
        <Badge tone="neutral">Not AI-grounded</Badge>
      )}
      {!isUser && message.citations && message.citations.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {message.citations.map((c) => (
            <Link
              key={c.incident_id}
              href={`/intelligence/${c.incident_id}`}
              className="rounded-sm bg-graphite-100 px-1.5 py-0.5 text-[10px] font-medium text-graphite-600 hover:bg-graphite-200 dark:bg-graphite-800 dark:text-graphite-300 dark:hover:bg-graphite-700"
            >
              {c.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
