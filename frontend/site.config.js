/**
 * Fuente única de verdad para los metadatos publicos del sitio.
 *
 * La consume `vite.config.js`, que sustituye los tokens `%SITE_*%` de
 * `index.html` y emite `robots.txt` + `sitemap.xml` en cada build. Mantener
 * estos datos en un solo sitio evita que la URL canónica, el sitemap y las
 * etiquetas Open Graph se desincronicen.
 *
 * Para desplegar en otro dominio basta con exportar SITE_URL antes del build:
 *   SITE_URL=https://mi-dominio.dev npm run build
 */

const DEFAULT_SITE_URL = 'https://facundosu1986.github.io/skyrim-ai-translator';

/** Normaliza la URL base: sin barra final, para poder concatenar rutas. */
function normalizeUrl(raw) {
  const value = (raw || DEFAULT_SITE_URL).trim();
  return value.endsWith('/') ? value.slice(0, -1) : value;
}

export const siteUrl = normalizeUrl(process.env.SITE_URL);

/**
 * `base` de Vite derivado de la URL: al publicar en
 * `usuario.github.io/repo` los assets cuelgan de `/repo/`, no de la raíz.
 */
export function resolveBase(url = siteUrl) {
  const { pathname } = new URL(url);
  return pathname.endsWith('/') ? pathname : `${pathname}/`;
}

export const site = {
  url: siteUrl,
  base: resolveBase(),
  lang: 'es',
  name: 'Skyrim AI Translator',
  shortName: 'Skyrim Translator',
  title:
    'Skyrim AI Translator | Traductor de mods y doblaje neural para Skyrim SE/AE',
  description:
    'Traductor automático de mods de Skyrim Special Edition y Anniversary Edition: '
    + 'procesa archivos .esp y .strings, traduce respetando el glosario de lore, '
    + 'genera doblaje neural con Edge-TTS y exporta a Dynamic String Distributor '
    + 'con inyección directa en Mod Organizer 2.',
  /** Resumen corto para tarjetas sociales, donde el texto se trunca antes. */
  socialDescription:
    'Traduce mods de Skyrim SE/AE y genera doblaje neural automático, con '
    + 'exportación a DSD e inyección directa en Mod Organizer 2.',
  keywords: [
    'traductor mods Skyrim',
    'Skyrim Special Edition español',
    'traducción automática mods',
    'Dynamic String Distributor',
    'Mod Organizer 2',
    'doblaje neural Skyrim',
    'text to speech Skyrim',
    'localización de videojuegos',
    'traducir esp Skyrim',
    'SKSE',
  ],
  author: 'FacundoSu1986',
  repository: 'https://github.com/FacundoSu1986/skyrim-ai-translator',
  themeColor: '#070a0e',
  ogImage: '/social/og-image.png',
  ogImageAlt:
    'Emblema nórdico de Skyrim AI Translator sobre fondo de obsidiana, con el '
    + 'texto "Skyrim AI Translator" y las etiquetas ESP/STRINGS, Edge-TTS, DSD y MO2.',
  /** Rutas que se listan en el sitemap (la SPA sirve una sola página). */
  routes: ['/'],
};

export default site;
