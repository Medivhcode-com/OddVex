import { PageIntro } from "@/components/marketing/chrome";
import { ButtonLink } from "@/components/ui/primitives";

export type FeatureCopy = {
  title: string;
  lede: string;
  cta: { href: string; label: string };
  points: { title: string; body: string }[];
  limits: string[];
};

export function FeaturePage({ copy }: { copy: FeatureCopy }) {
  return (
    <>
      <PageIntro title={copy.title} lede={copy.lede}>
        <ButtonLink href={copy.cta.href} size="lg">
          {copy.cta.label}
        </ButtonLink>
        <ButtonLink href="/methodology" variant="secondary" size="lg">
          Read the methodology
        </ButtonLink>
      </PageIntro>
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <dl className="grid gap-x-12 gap-y-8 border-t border-line pt-10 md:grid-cols-2">
          {copy.points.map((point) => (
            <div key={point.title}>
              <dt className="text-lg font-semibold">{point.title}</dt>
              <dd className="mt-2 max-w-prose leading-relaxed text-muted">{point.body}</dd>
            </div>
          ))}
        </dl>
        <section aria-labelledby="limits" className="mt-14 rounded-panel border border-line bg-surface p-6">
          <h2 id="limits" className="font-semibold">
            What to keep in mind
          </h2>
          <ul className="mt-3 list-disc space-y-1.5 pl-5 text-muted">
            {copy.limits.map((limit) => (
              <li key={limit}>{limit}</li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}
