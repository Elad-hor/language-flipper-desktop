/**
 * Cloudflare Worker entry point for languageflipper.com.
 *
 * The site is static (Astro → dist/), served by Workers Static Assets. This
 * Worker exists for one reason: the contact form, which ran on PHP mail() at
 * Hostinger and has nowhere to run on a static host.
 *
 * Workers Static Assets serves a matching file before invoking this Worker, so
 * in practice only /contact and /contact.php reach the code below; the
 * ASSETS.fetch fallback is belt-and-braces for anything else that gets here.
 *
 * Not Pages Functions: Cloudflare has put Pages into maintenance and routes
 * new Git-connected projects through Workers. `_headers` and `_redirects` in
 * the assets directory are honoured by Workers Static Assets too, so the
 * redirects and cache rules ported from .htaccess still apply.
 */

import { handleContact, type ContactEnv } from './contact-handler';

export interface Env extends ContactEnv {
  /** Binding to the built static site (see assets.binding in wrangler.jsonc). */
  ASSETS: { fetch: (request: Request) => Promise<Response> };
}

// /contact is the real endpoint. /contact.php is kept because the form posted
// there for the whole life of the Hostinger site — this way the move has no
// window where a cached page or an in-flight submission hits a 404.
const CONTACT_ROUTES = new Set(['/contact', '/contact.php']);

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const { pathname } = url;

    // One canonical origin. www, non-www and http each served the site in full,
    // so Google treated them as three competing websites and split the ranking
    // between them. Scheme and host are corrected in a single hop, so
    // http://www never costs two redirects.
    const wrongHost = url.hostname.startsWith('www.');
    const wrongScheme = url.protocol === 'http:';
    if (wrongHost || wrongScheme) {
      if (wrongHost) url.hostname = url.hostname.slice(4);
      if (wrongScheme) url.protocol = 'https:';
      return Response.redirect(url.toString(), 301);
    }

    if (CONTACT_ROUTES.has(pathname)) {
      return handleContact(request, env);
    }

    return env.ASSETS.fetch(request);
  },
};
