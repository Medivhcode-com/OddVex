import { ButtonLink } from "@/components/ui/primitives";

export default function NotFound() {
  return (
    <main id="main" className="mx-auto grid min-h-dvh max-w-xl place-content-center px-6 text-center">
      <p className="num text-sm text-muted">404</p>
      <h1 className="mt-2 text-title font-semibold">This page is off the board</h1>
      <p className="mt-3 text-muted">The link may be old, or the game may have been removed.</p>
      <div className="mt-6 flex justify-center gap-3">
        <ButtonLink href="/">Go to the home page</ButtonLink>
        <ButtonLink href="/app" variant="secondary">
          Open the app
        </ButtonLink>
      </div>
    </main>
  );
}
