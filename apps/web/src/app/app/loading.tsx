import { Skeleton } from "@/components/ui/primitives";

export default function Loading() {
  return (
    <div role="status" aria-label="Loading">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="mt-3 h-4 w-80 max-w-full" />
      <div className="mt-8 grid gap-4 md:grid-cols-2">
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
        <Skeleton className="h-64 md:col-span-2" />
      </div>
    </div>
  );
}
