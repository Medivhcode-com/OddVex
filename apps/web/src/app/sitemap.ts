import type { MetadataRoute } from "next";
import { POSTS } from "@/lib/posts";
import { SITE } from "@/lib/site";

const PAGES = [
  "", "/features", "/odds-comparison", "/player-props", "/bet-tracking", "/ai", "/pricing", "/about", "/blog",
  "/contact", "/help", "/privacy", "/terms", "/responsible-gambling", "/methodology", "/download",
];

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    ...PAGES.map((path) => ({ url: `${SITE.url}${path}`, changeFrequency: "weekly" as const, priority: path === "" ? 1 : 0.7 })),
    ...POSTS.map((post) => ({ url: `${SITE.url}/blog/${post.slug}`, lastModified: post.published, priority: 0.6 })),
  ];
}
