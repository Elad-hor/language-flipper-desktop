import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://languageflipper.com',
  trailingSlash: 'always',
  build: { format: 'directory' },
  compressHTML: false,
});
