// Verify the Pages contact function behaves exactly like contact.php did.
import { handleContact } from '../../worker/contact-handler.ts';

const results = [];
const check = (name, ok, detail = '') => {
  results.push(ok);
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? `  — ${detail}` : ''}`);
};

let sent = [];
const env = { MAILGUN_API_KEY: 'test-key', MAILGUN_DOMAIN: 'mg.languageflipper.com' };

globalThis.fetch = async (url, init) => {
  // Mailgun takes form-encoded fields, not JSON.
  sent.push({
    url,
    body: Object.fromEntries(new URLSearchParams(init.body)),
    auth: init.headers.Authorization,
  });
  return new Response('{"id":"x"}', { status: 200 });
};

function post(fields) {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) fd.append(k, v);
  return new Request('https://languageflipper.com/contact', { method: 'POST', body: fd });
}

const valid = {
  first_name: 'Elad', last_name: 'Hor', email: 'a@b.com',
  company: 'Falafel', message: 'hello', redirect: '/contact-us/',
};

// --- happy path -------------------------------------------------------------
sent = [];
let r = await handleContact(post(valid), env);
check('valid submission redirects', r.status === 302, `status=${r.status}`);
check('redirects to ?sent=1 so the banner shows',
  (r.headers.get('location') || '').endsWith('/contact-us/?sent=1'), r.headers.get('location'));
check('one email sent', sent.length === 1);
check('sent to the right inbox', sent[0]?.body.to === 'falafeltikunim@gmail.com', sent[0]?.body.to);
check('Reply-To is the visitor', sent[0]?.body['h:Reply-To'] === 'a@b.com');
check('body carries the message', (sent[0]?.body.text || '').includes('hello'));
check('api key sent as basic auth', sent[0]?.auth === `Basic ${btoa('api:test-key')}`, sent[0]?.auth);
check('posts to the Mailgun messages endpoint for the domain',
  sent[0]?.url === 'https://api.mailgun.net/v3/mg.languageflipper.com/messages', sent[0]?.url);

// --- Hebrew redirect --------------------------------------------------------
sent = [];
r = await handleContact(post({ ...valid, redirect: '/he/צור-קשר/' }), env);
check('Hebrew submission returns to the Hebrew page',
  decodeURIComponent(r.headers.get('location') || '').endsWith('/he/צור-קשר/?sent=1'),
  r.headers.get('location'));

// --- honeypot ---------------------------------------------------------------
sent = [];
r = await handleContact(post({ ...valid, website: 'spam' }), env);
check('honeypot: fakes success', r.status === 302);
check('honeypot: sends NOTHING', sent.length === 0, `sent=${sent.length}`);

// --- validation -------------------------------------------------------------
sent = [];
r = await handleContact(post({ ...valid, email: 'not-an-email' }), env);
check('bad email rejected', r.status === 422 && sent.length === 0);

r = await handleContact(post({ ...valid, email: '' }), env);
check('missing email rejected', r.status === 422);

r = await handleContact(post({ ...valid, company: '' }), env);
check('missing company rejected', r.status === 422);

r = await handleContact(post({ ...valid, first_name: 'bad\r\nBcc: evil@x.com' }), env);
check('header injection rejected', r.status === 422, `status=${r.status}`);

// --- open redirect ----------------------------------------------------------
for (const [label, bad] of [
  ['absolute URL', 'https://evil.com/'],
  ['protocol-relative', '//evil.com/'],
  ['CRLF in path', '/ok/\r\nSet-Cookie: x'],
  ['not a path', 'evil'],
]) {
  sent = [];
  r = await handleContact(post({ ...valid, redirect: bad }), env);
  const loc = r.headers.get('location') || '';
  check(`open redirect blocked (${label})`,
    loc.startsWith('https://languageflipper.com/contact-us/?sent=1'), loc);
}

// --- method + config --------------------------------------------------------
r = await handleContact(new Request('https://languageflipper.com/contact'), env);
check('GET rejected', r.status === 405);

sent = [];
r = await handleContact(post(valid), {});
check('no provider configured fails loudly, sends nothing', r.status === 500 && sent.length === 0);

sent = [];
r = await handleContact(post(valid), { MAILGUN_API_KEY: 'k' });
check('Mailgun key without domain fails loudly, sends nothing',
  r.status === 500 && sent.length === 0);

// --- Resend path (the fallback when Mailgun is not configured) -------------
sent = [];
globalThis.fetch = async (url, init) => {
  sent.push({ url, body: JSON.parse(init.body), auth: init.headers.Authorization });
  return new Response('{"id":"x"}', { status: 200 });
};
r = await handleContact(post(valid), { RESEND_API_KEY: 'r-key' });
check('Resend used when only RESEND_API_KEY is set', r.status === 302 && sent.length === 1);
check('Resend endpoint', sent[0]?.url === 'https://api.resend.com/emails', sent[0]?.url);
check('Resend bearer auth', sent[0]?.auth === 'Bearer r-key', sent[0]?.auth);
check('Resend to/reply_to correct',
  sent[0]?.body.to?.[0] === 'falafeltikunim@gmail.com' && sent[0]?.body.reply_to === 'a@b.com');

// Mailgun wins when both are configured, so adding Resend later can't silently
// change which provider is in use.
sent = [];
globalThis.fetch = async (url, init) => {
  sent.push({ url });
  return new Response('{}', { status: 200 });
};
await handleContact(post(valid), { ...env, RESEND_API_KEY: 'r-key' });
check('Mailgun takes precedence when both are set',
  (sent[0]?.url || '').includes('mailgun'), sent[0]?.url);

// restore the Mailgun-shaped stub for the remaining cases
globalThis.fetch = async (url, init) => {
  sent.push({ url, body: Object.fromEntries(new URLSearchParams(init.body)) });
  return new Response('{}', { status: 200 });
};

// EU accounts must be able to override the region, or every send 401s.
sent = [];
globalThis.fetch = async (url, init) => {
  sent.push({ url, body: Object.fromEntries(new URLSearchParams(init.body)) });
  return new Response('{}', { status: 200 });
};
await handleContact(post(valid), { ...env, MAILGUN_API_BASE: 'https://api.eu.mailgun.net' });
check('EU region endpoint honoured',
  sent[0]?.url === 'https://api.eu.mailgun.net/v3/mg.languageflipper.com/messages', sent[0]?.url);

// --- upstream failure -------------------------------------------------------
globalThis.fetch = async () => new Response('bad key', { status: 401 });
r = await handleContact(post(valid), env);
check('Mailgun error surfaces as 500, not a fake success', r.status === 500);

globalThis.fetch = async () => { throw new Error('network down'); };
r = await handleContact(post(valid), env);
check('network failure surfaces as 500', r.status === 500);

console.log(`\n=== ${results.filter(Boolean).length}/${results.length} passed ===`);
process.exit(results.every(Boolean) ? 0 : 1);
