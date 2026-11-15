import { Notice } from "@/components/ui/primitives";

export function DraftBanner() {
  return (
    <div className="mx-auto mb-8 max-w-6xl px-4 sm:px-6">
      <Notice tone="warn" title="Preview draft">
        This document describes how the preview works today. It has not yet been reviewed by legal counsel and will be
        replaced by a final version before public launch.
      </Notice>
    </div>
  );
}
