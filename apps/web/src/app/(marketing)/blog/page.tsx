import type { Metadata } from "next";
import Link from "next/link";
import { PageIntro } from "@/components/marketing/chrome";
import { POSTS } from "@/lib/posts";

export const metadata: Metadata = {
  title: "Blog",
  description: "Plain-language explanations of betting math: implied probability, the vig, expected value and sample size.",
  alternates: { canonical: "/blog" },
};

const dateFmt = new Intl.DateTimeFormat("en-US", { dateStyle: "long", timeZone: "UTC" });

export default function Page() {
  return (
    <>
      <PageIntro title="Betting math, explained plainly" lede="Short reads on how prices work and how to avoid fooling yourself with them." />
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <ul className="divide-y divide-line border-y border-line">
          {[...POSTS].reverse().map((post) => (
            <li key={post.slug} className="py-6">
              <Link href={`/blog/${post.slug}`} className="group block max-w-3xl">
                <h2 className="text-xl font-semibold tracking-tight group-hover:underline group-hover:underline-offset-4">{post.title}</h2>
                <p className="mt-2 text-muted">{post.description}</p>
                <p className="mt-2 text-sm text-muted">
                  <time dateTime={post.published}>{dateFmt.format(new Date(post.published))}</time>, {post.minutes} minute read
                </p>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}
