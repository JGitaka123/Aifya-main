import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");
const useStandaloneOutput =
  process.env.NEXT_OUTPUT_STANDALONE ?? (process.platform === "win32" ? "false" : "true");
const apiRewriteBaseUrl =
  process.env.API_REWRITE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000/api/v1";

const nextConfig: NextConfig = {
  ...(useStandaloneOutput === "true" ? { output: "standalone" as const } : {}),
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiRewriteBaseUrl.replace(/\/$/, "")}/:path*`,
      },
    ];
  },
  images: {
    remotePatterns: [
      {
        protocol: "http",
        hostname: "localhost",
        port: "9000",
        pathname: "/aifya-documents/**",
      },
    ],
  },
};

// next-intl 3.x still registers its Turbopack resolve alias under
// `experimental.turbo`, so Next 15.5 warns about that deprecated key on every
// dev start. Move it to the supported `turbopack.resolveAlias` entry.
function migrateLegacyTurbopackAliases(config: NextConfig): NextConfig {
  const experimental = config.experimental as
    | { turbo?: { resolveAlias?: Record<string, string> } }
    | undefined;
  const resolveAlias = experimental?.turbo?.resolveAlias;
  if (!resolveAlias) return config;

  const remaining = { ...experimental };
  delete remaining.turbo;

  const migrated: NextConfig = {
    ...config,
    turbopack: {
      ...config.turbopack,
      resolveAlias: { ...resolveAlias, ...config.turbopack?.resolveAlias },
    },
  };
  if (Object.keys(remaining).length > 0) {
    migrated.experimental = remaining as typeof migrated.experimental;
  } else {
    delete migrated.experimental;
  }
  return migrated;
}

export default migrateLegacyTurbopackAliases(withNextIntl(nextConfig));
