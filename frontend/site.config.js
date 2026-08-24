const defaultSiteUrl = (typeof process !== 'undefined' && process.env?.SITE_URL) || 'https://facundosu1986.github.io/skyrim-ai-translator';

/**
 * Computes the base path pathname from a site URL.
 * E.g. 'https://facundosu1986.github.io/skyrim-ai-translator' -> '/skyrim-ai-translator/'
 * E.g. '/' -> '/'
 *
 * @param {string} [url] - The site URL to parse.
 * @returns {string} Normalized base path with trailing slash.
 */
export function getBasePath(url = siteConfig?.siteUrl || defaultSiteUrl) {
  if (!url || url === '/') {
    return '/';
  }

  try {
    const parsed = new URL(url, 'https://example.local');
    let pathname = parsed.pathname;
    if (!pathname.startsWith('/')) {
      pathname = '/' + pathname;
    }
    if (!pathname.endsWith('/')) {
      pathname += '/';
    }
    return pathname;
  } catch {
    let clean = String(url).trim();
    if (!clean.startsWith('/')) {
      clean = '/' + clean;
    }
    if (!clean.endsWith('/')) {
      clean += '/';
    }
    return clean;
  }
}

/**
 * Generates structured Schema.org JSON-LD for SoftwareApplication reflecting truthful capabilities.
 *
 * @param {typeof siteConfig} [config] - Site configuration object.
 * @returns {Record<string, unknown>} Schema.org JSON-LD object.
 */
export function generateSoftwareApplicationSchema(config = siteConfig) {
  const rawUrl = config?.siteUrl || defaultSiteUrl;
  const siteUrl = rawUrl.endsWith('/') ? rawUrl : `${rawUrl}/`;
  const repoUrl = config?.repoUrl || 'https://github.com/FacundoSu1986/skyrim-ai-translator';
  const description = config?.description || 'AI-assisted Skyrim SE/AE mod localization tool with binary ESP/ESM parsing, lore-aware translation, DSD export, neural TTS staging, and Mod Organizer 2 integration.';

  return {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'Skyrim AI Translator',
    applicationCategory: 'MultimediaApplication',
    applicationSubCategory: 'DeveloperApplication',
    operatingSystem: 'Windows, Linux, macOS',
    description,
    url: siteUrl,
    downloadUrl: repoUrl,
    sameAs: [repoUrl],
    featureList: [
      'Binary ESP/ESM parsing',
      'Lore glossary translation',
      'DSD export',
      'Neural TTS staging',
      'MO2 integration',
    ],
    offers: {
      '@type': 'Offer',
      price: '0',
      priceCurrency: 'USD',
    },
  };
}

export const generateJsonLd = generateSoftwareApplicationSchema;

export const siteConfig = {
  siteUrl: defaultSiteUrl,
  repoUrl: 'https://github.com/FacundoSu1986/skyrim-ai-translator',
  title: 'Skyrim AI Translator | Skyrim SE/AE Mod Localization',
  description: 'AI-assisted Skyrim SE/AE mod localization tool with binary ESP/ESM parsing, lore-aware translation, DSD export, neural TTS staging, and Mod Organizer 2 integration.',
  getBasePath,
  generateSoftwareApplicationSchema,
  generateJsonLd,
};

export default siteConfig;
