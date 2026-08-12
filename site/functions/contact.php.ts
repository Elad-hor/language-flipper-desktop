// POST /contact.php — kept alive on purpose.
//
// The form posted here for the whole life of the Hostinger site. Keeping the
// route means the move off Hostinger has no window where a cached page, a
// bookmark, or a mid-flight submission hits a 404. It is the same handler as
// /contact; there is no PHP anywhere near it.
//
// Safe to delete once the site has been on Pages long enough that no cached
// copy of the old HTML is plausibly still in use.
import { handleContact, type Env } from './_contact-handler';

export const onRequest: PagesFunction<Env> = ({ request, env }) =>
  handleContact(request, env);
