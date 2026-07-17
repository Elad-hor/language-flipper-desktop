import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://languageflipper.com',
  trailingSlash: 'always',
  build: { format: 'directory' },
  compressHTML: false,
  integrations: [
    sitemap({
      // Stamp every entry with the build date so Google sees fresh lastmod values.
      serialize(item) {
        item.lastmod = new Date().toISOString();
        return item;
      },
    }),
  ],
});
