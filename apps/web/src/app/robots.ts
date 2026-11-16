import type { MetadataRoute } from "next";
import { SITE } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/app/", "/api/", "/login", "/signup", "/forgot-password", "/reset-password", "/verify-email", "/design"] }],
    sitemap: `${SITE.url}/sitemap.xml`,
  };
}
