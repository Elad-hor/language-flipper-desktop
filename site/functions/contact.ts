// POST /contact — the contact form endpoint on Cloudflare Pages.
import { handleContact, type Env } from './_contact-handler';

export const onRequest: PagesFunction<Env> = ({ request, env }) =>
  handleContact(request, env);
