"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/primitives";
import { clientApi, ClientApiError } from "@/lib/client-api";
import { formatAge } from "@/lib/format";
import type { AssistantReply } from "@/lib/types";

type Turn = { id: number; question: string; reply?: AssistantReply; error?: string };

export function AssistantChat({ examples }: { examples: string[] }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const nextId = useRef(1);
  const endRef = useRef<HTMLDivElement>(null);

  async function ask(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    const id = nextId.current++;
    setTurns((current) => [...current, { id, question: text }]);
    setInput("");
    setBusy(true);
    try {
      const reply = await clientApi<AssistantReply>("/v1/assistant/query", { body: { message: text } });
      setTurns((current) => current.map((turn) => (turn.id === id ? { ...turn, reply } : turn)));
    } catch (caught) {
      const error =
        caught instanceof ClientApiError && caught.status === 429
          ? "You've asked a lot of questions quickly. Wait a minute, then ask again."
          : caught instanceof ClientApiError
            ? caught.message
            : "OddVex AI couldn't answer. Try again.";
      setTurns((current) => current.map((turn) => (turn.id === id ? { ...turn, error } : turn)));
    } finally {
      setBusy(false);
      requestAnimationFrame(() => endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" }));
    }
  }

  return (
    <div className="flex min-h-[60dvh] flex-col">
      <div className="flex-1 space-y-5 p-4 sm:p-5" aria-live="polite">
        {turns.length === 0 ? (
          <div>
            <p className="text-muted">Try one of these, or ask your own question.</p>
            <ul className="mt-3 flex flex-wrap gap-2">
              {examples.map((example) => (
                <li key={example}>
                  <button type="button" onClick={() => ask(example)} className="min-h-10 rounded-full border border-line px-4 text-left text-sm hover:border-line-strong hover:bg-raised">
                    {example}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {turns.map((turn) => (
          <div key={turn.id} className="space-y-3">
            <p className="ml-auto w-fit max-w-[85%] rounded-panel rounded-br-sm bg-raised px-4 py-2.5">
              <span className="sr-only">You asked: </span>
              {turn.question}
            </p>
            {turn.error ? (
              <p role="alert" className="max-w-[92%] rounded-panel rounded-bl-sm border border-error/40 bg-error-soft px-4 py-3 text-sm">
                {turn.error}
              </p>
            ) : turn.reply ? (
              <div className="max-w-[92%] rounded-panel rounded-bl-sm border border-line bg-bg px-4 py-3">
                <span className="sr-only">OddVex AI answered: </span>
                <p className="whitespace-pre-line leading-relaxed">{turn.reply.answer}</p>
                {turn.reply.suggestions.length ? (
                  <ul className="mt-3 flex flex-wrap gap-2">
                    {turn.reply.suggestions.map((suggestion) => (
                      <li key={suggestion.href + suggestion.label}>
                        <Link href={suggestion.href} className="inline-flex min-h-9 items-center rounded-full border border-line-strong px-3 text-sm font-medium hover:bg-raised">
                          {suggestion.label}
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : null}
                <div className="mt-3 space-y-1 border-t border-line pt-2 text-xs text-muted">
                  {turn.reply.sources.length ? (
                    <p>
                      Sources:{" "}
                      {turn.reply.sources.map((source) => `${source.label} (${source.data_mode} data, updated ${formatAge(source.as_of)})`).join("; ")}
                    </p>
                  ) : (
                    <p>No data was used for this answer.</p>
                  )}
                  <p>{turn.reply.disclaimer}</p>
                </div>
              </div>
            ) : (
              <p role="status" className="ov-skeleton w-fit rounded-panel px-4 py-3 text-sm text-muted">
                Looking that up
              </p>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          ask(input);
        }}
        className="sticky bottom-16 flex gap-2 border-t border-line bg-surface p-3 sm:p-4 lg:bottom-0"
      >
        <label htmlFor="assistant-input" className="sr-only">
          Ask OddVex AI
        </label>
        <input
          id="assistant-input"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          maxLength={500}
          autoComplete="off"
          placeholder="Ask about a price, a player or your bets"
          className="min-h-11 min-w-0 flex-1 rounded-cell border border-line-strong bg-bg px-3 placeholder:text-muted/70"
        />
        <Button type="submit" disabled={busy || !input.trim()}>
          Ask
        </Button>
      </form>
    </div>
  );
}
