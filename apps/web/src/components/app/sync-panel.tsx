"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Schemas } from "@oddvex/types";
import { Badge, Button, Notice } from "@/components/ui/primitives";
import { clientApi, ClientApiError } from "@/lib/client-api";
import { formatAge } from "@/lib/format";

type Connection = Schemas["SyncConnectionOut"];
type Run = Schemas["SyncRunOut"];
type Provider = Schemas["SyncProviderOut"];

/**
 * Sportsbook sync, wired to the provider-independent sync API.
 * Only a mock provider exists today, and the UI says so: no real account is contacted.
 */
export function SyncPanel({ providers, connections }: { providers: Provider[]; connections: Connection[] }) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ tone: "accent" | "error" | "warn"; text: string } | null>(null);
  const provider = providers[0];

  async function run(key: string, action: () => Promise<string | void>) {
    setBusy(key);
    setMessage(null);
    try {
      const text = await action();
      if (text) setMessage({ tone: "accent", text });
      router.refresh();
    } catch (caught) {
      setMessage({ tone: "error", text: caught instanceof ClientApiError ? caught.message : "That didn't work. Try again." });
    } finally {
      setBusy(null);
    }
  }

  const sync = (connection: Connection) =>
    run(`sync-${connection.id}`, async () => {
      const result = await clientApi<Run>(`/v1/sync/connections/${connection.id}/sync`, { method: "POST", body: {} });
      if (result.status === "failed") {
        setMessage({ tone: "warn", text: `Sync failed${result.retryable ? " and can be retried" : ""}: ${result.error_message ?? "no detail given"}.` });
        return;
      }
      return `Sync finished. ${result.imported_count} new ${result.imported_count === 1 ? "bet" : "bets"} imported, ${result.duplicate_count} already here.`;
    });

  return (
    <div className="space-y-4 p-4 sm:p-5">
      <Notice tone="warn" title="Demonstration only">
        This connects to a mock sportsbook that returns sample bets. No real sportsbook account is contacted, and OddVex never asks for a sportsbook password.
      </Notice>
      {connections.length === 0 ? (
        <p className="text-sm text-muted">No connections yet.</p>
      ) : (
        <ul className="divide-y divide-line rounded-cell border border-line">
          {connections.map((connection) => (
            <li key={connection.id} className="flex flex-wrap items-center justify-between gap-3 px-3 py-3">
              <div className="min-w-0">
                <p className="font-medium">
                  {connection.label || connection.provider_name} {connection.is_mock ? <Badge className="ml-1">Mock</Badge> : null}
                </p>
                <p className="text-sm text-muted">
                  {connection.bet_count} synced {connection.bet_count === 1 ? "bet" : "bets"}.{" "}
                  {connection.last_synced_at ? `Last synced ${formatAge(connection.last_synced_at)}.` : "Not synced yet."}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="secondary" disabled={busy !== null} onClick={() => sync(connection)}>
                  {busy === `sync-${connection.id}` ? "Syncing" : "Sync now"}
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  disabled={busy !== null}
                  aria-label={`Disconnect ${connection.label || connection.provider_name} and delete its bets`}
                  onClick={() =>
                    run(`del-${connection.id}`, async () => {
                      const out = await clientApi<Schemas["SyncConnectionDeleteOut"]>(`/v1/sync/connections/${connection.id}?delete_data=true`, { method: "DELETE" });
                      return `Disconnected. ${out.bets_deleted} synced ${out.bets_deleted === 1 ? "bet" : "bets"} deleted.`;
                    })
                  }
                >
                  Disconnect and delete bets
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {provider ? (
        <Button
          variant="secondary"
          disabled={busy !== null}
          onClick={() =>
            run("connect", async () => {
              await clientApi("/v1/sync/connections", { body: { provider: provider.key } });
              return `Connected to ${provider.name}. Choose Sync now to import its sample bets.`;
            })
          }
        >
          {busy === "connect" ? "Connecting" : `Connect ${provider.name}`}
        </Button>
      ) : null}
      <div aria-live="polite">{message ? <Notice tone={message.tone}>{message.text}</Notice> : null}</div>
    </div>
  );
}
