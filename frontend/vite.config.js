import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { siteConfig, getBasePath, generateSoftwareApplicationSchema } from './site.config.js'

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export function seoPlugin(config = siteConfig) {
  const rawUrl = config?.siteUrl || 'https://facundosu1986.github.io/skyrim-ai-translator';
  const siteUrl = rawUrl.replace(/\/+$/, '');
  const canonicalUrl = `${siteUrl}/`;
  const sitemapUrl = `${siteUrl}/sitemap.xml`;

  return {
    name: 'vite-plugin-seo',
    transformIndexHtml(html) {
      const schemaGenerator = config?.generateSoftwareApplicationSchema || generateSoftwareApplicationSchema;
      const schema = schemaGenerator(config);
      const jsonLdSafeString = JSON.stringify(schema, null, 2).replace(/</g, '\\u003c');

      const seoTags = [
        `<!-- Canonical & Metadata -->`,
        `<link rel="canonical" href="${canonicalUrl}" />`,
        `<meta name="description" content="${escapeHtml(config.description)}" />`,
        `<meta name="application-name" content="${escapeHtml(schema.name)}" />`,
        `<meta name="author" content="FacundoSu1986" />`,
        `<meta name="robots" content="index, follow" />`,
        `<!-- OpenGraph Metadata -->`,
        `<meta property="og:type" content="website" />`,
        `<meta property="og:title" content="${escapeHtml(config.title)}" />`,
        `<meta property="og:description" content="${escapeHtml(config.description)}" />`,
        `<meta property="og:url" content="${canonicalUrl}" />`,
        `<meta property="og:site_name" content="${escapeHtml(schema.name)}" />`,
        `<meta property="og:image" content="${siteUrl}/favicon.svg" />`,
        `<!-- Twitter Cards -->`,
        `<meta name="twitter:card" content="summary" />`,
        `<meta name="twitter:title" content="${escapeHtml(config.title)}" />`,
        `<meta name="twitter:description" content="${escapeHtml(config.description)}" />`,
        `<meta name="twitter:image" content="${siteUrl}/favicon.svg" />`,
        `<!-- JSON-LD Structured Data -->`,
        `<script type="application/ld+json">\n${jsonLdSafeString}\n    </script>`,
      ].join('\n    ');

      if (html.includes('<!-- %SEO_METADATA% -->')) {
        return html.replace('<!-- %SEO_METADATA% -->', seoTags);
      }
      if (html.includes('<!-- SEO_PLACEHOLDER -->')) {
        return html.replace('<!-- SEO_PLACEHOLDER -->', seoTags);
      }
      return html.replace('</head>', `    ${seoTags}\n  </head>`);
    },
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: 'robots.txt',
        source: `User-agent: *\nAllow: /\nSitemap: ${sitemapUrl}\n`,
      });

      this.emitFile({
        type: 'asset',
        fileName: 'sitemap.xml',
        source: `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  <url>\n    <loc>${canonicalUrl}</loc>\n    <changefreq>monthly</changefreq>\n    <priority>1.0</priority>\n  </url>\n</urlset>\n`,
      });
    },
  };
}

// https://vite.dev/config/
export default defineConfig({
  base: getBasePath(siteConfig.siteUrl),
  plugins: [react(), seoPlugin(siteConfig)],
})
