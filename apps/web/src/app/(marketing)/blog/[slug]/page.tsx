import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Prose } from "@/components/marketing/chrome";
import { getPost, POSTS } from "@/lib/posts";
import { SITE } from "@/lib/site";

type Props = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return POSTS.map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const post = getPost((await params).slug);
  if (!post) return {};
  return {
    title: post.title,
    description: post.description,
    alternates: { canonical: `/blog/${post.slug}` },
    openGraph: { type: "article", title: post.title, description: post.description, publishedTime: post.published },
  };
}

const dateFmt = new Intl.DateTimeFormat("en-US", { dateStyle: "long", timeZone: "UTC" });

export default async function Page({ params }: Props) {
  const post = getPost((await params).slug);
  if (!post) notFound();
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.title,
    description: post.description,
    datePublished: post.published,
    author: { "@type": "Organization", name: SITE.name },
    publisher: { "@type": "Organization", name: SITE.company },
  };
  return (
    <article className="pt-14 sm:pt-20">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <Link href="/blog" className="text-sm text-muted underline underline-offset-4 hover:text-ink">
          All posts
        </Link>
        <h1 className="mt-4 max-w-3xl text-title font-semibold">{post.title}</h1>
        <p className="mt-3 text-sm text-muted">
          <time dateTime={post.published}>{dateFmt.format(new Date(post.published))}</time>, {post.minutes} minute read
        </p>
      </div>
      <Prose>
        {post.sections.map((section) => (
          <section key={section.heading}>
            <h2>{section.heading}</h2>
            {section.paragraphs.map((paragraph) => (
              <p key={paragraph.slice(0, 40)}>{paragraph}</p>
            ))}
          </section>
        ))}
        <p className="mt-10 border-t border-line pt-6 text-sm">
          This article is educational. It is not betting advice and nothing in it predicts an outcome. See the{" "}
          <Link href="/methodology">methodology</Link> for the exact formulas OddVex uses.
        </p>
      </Prose>
    </article>
  );
}
