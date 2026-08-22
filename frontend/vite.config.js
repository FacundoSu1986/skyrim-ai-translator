import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import site from './site.config.js'

/**
 * Inyecta los metadatos de `site.config.js` en `index.html` y emite los
 * artefactos de rastreo (`robots.txt`, `sitemap.xml`) durante el build, de
 * modo que la URL canonica viva en un unico archivo.
 */
function seoPlugin() {
  const absolute = (path) => `${site.url}${path.startsWith('/') ? path : `/${path}`}`

  const tokens = {
    '%SITE_URL%': site.url,
    '%SITE_LANG%': site.lang,
    '%SITE_NAME%': site.name,
    '%SITE_TITLE%': site.title,
    '%SITE_DESCRIPTION%': site.description,
    '%SITE_SOCIAL_DESCRIPTION%': site.socialDescription,
    '%SITE_KEYWORDS%': site.keywords.join(', '),
    '%SITE_AUTHOR%': site.author,
    '%SITE_REPOSITORY%': site.repository,
    '%SITE_THEME_COLOR%': site.themeColor,
    '%SITE_OG_IMAGE%': absolute(site.ogImage),
    '%SITE_OG_IMAGE_ALT%': site.ogImageAlt,
  }

  return {
    name: 'skyrim-translator-seo',
    transformIndexHtml(html) {
      return Object.entries(tokens).reduce(
        (acc, [token, value]) => acc.replaceAll(token, value),
        html,
      )
    },
    generateBundle() {
      const lastmod = new Date().toISOString().slice(0, 10)

      const sitemap = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ...site.routes.map((route) => [
          '  <url>',
          `    <loc>${absolute(route)}</loc>`,
          `    <lastmod>${lastmod}</lastmod>`,
          '    <changefreq>weekly</changefreq>',
          '    <priority>1.0</priority>',
          '  </url>',
        ].join('\n')),
        '</urlset>',
        '',
      ].join('\n')

      const robots = [
        '# https://www.robotstxt.org/robotstxt.html',
        'User-agent: *',
        'Allow: /',
        '',
        `Sitemap: ${absolute('/sitemap.xml')}`,
        '',
      ].join('\n')

      this.emitFile({ type: 'asset', fileName: 'sitemap.xml', source: sitemap })
      this.emitFile({ type: 'asset', fileName: 'robots.txt', source: robots })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  base: site.base,
  plugins: [react(), seoPlugin()],
})
