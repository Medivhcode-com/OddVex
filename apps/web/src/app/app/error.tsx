"use client";

import { Button } from "@/components/ui/primitives";
import { readAppError } from "@/lib/app-error";

/**
 * The error screen of every `/app` page. In a production build only the error's `digest`
 * arrives here (name and message are replaced on the way), so that is all it reads.
 */
export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const { unreachable, reference } = readAppError(error);
  return (
    <div role="alert" className="mx-auto max-w-lg rounded-panel border border-line bg-surface px-6 py-10 text-center">
      <h1 className="text-lg font-semibold">{unreachable ? "OddVex can't reach its data service" : "This screen failed to load"}</h1>
      <p className="mt-2 text-muted">
        {unreachable
          ? "Nothing is wrong with your account. The data service is not responding, so there are no prices to show."
          : "Something went wrong while loading this data. Your bets and settings are not affected."}
      </p>
      <Button onClick={reset} className="mt-5">
        Try again
      </Button>
      {reference ? <p className="num mt-4 text-xs text-muted">Reference {reference}</p> : null}
    </div>
  );
}
