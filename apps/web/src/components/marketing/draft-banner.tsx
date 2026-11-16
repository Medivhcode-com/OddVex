import clsx from "clsx";
import { Notice } from "@/components/ui/primitives";

/** Marks text that has not been through legal review. Pass children to scope it to one section. */
export function DraftBanner({ children, className }: { children?: React.ReactNode; className?: string }) {
  return (
    <div className={clsx("mx-auto mb-8 max-w-6xl px-4 sm:px-6", className)}>
      <Notice tone="warn" title="Preview draft">
        {children ?? (
          <>
            This document describes how the preview works today. It has not yet been reviewed by legal counsel and will be
            replaced by a final version before public launch.
          </>
        )}
      </Notice>
    </div>
  );
}
