// Verify the Pages contact function behaves exactly like contact.php did.
import { handleContact } from '../../functions/_contact-handler.ts';

const results = [];
const check = (name, ok, detail = '') => {
  results.push(ok);
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? `  — ${detail}` : ''}`);
};

let sent = [];
const env = { RESEND_API_KEY: 'test-key' };

globalThis.fetch = async (url, init) => {
  sent.push({ url, body: JSON.parse(init.body), auth: init.headers.Authorization });
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
check('sent to the right inbox', sent[0]?.body.to?.[0] === 'falafeltikunim@gmail.com', sent[0]?.body.to?.[0]);
check('reply_to is the visitor', sent[0]?.body.reply_to === 'a@b.com');
check('body carries the message', (sent[0]?.body.text || '').includes('hello'));
check('api key sent as bearer', sent[0]?.auth === 'Bearer test-key');

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
check('missing API key fails loudly, sends nothing', r.status === 500 && sent.length === 0);

// --- upstream failure -------------------------------------------------------
globalThis.fetch = async () => new Response('bad key', { status: 401 });
r = await handleContact(post(valid), env);
check('Resend error surfaces as 500, not a fake success', r.status === 500);

globalThis.fetch = async () => { throw new Error('network down'); };
r = await handleContact(post(valid), env);
check('network failure surfaces as 500', r.status === 500);

console.log(`\n=== ${results.filter(Boolean).length}/${results.length} passed ===`);
process.exit(results.every(Boolean) ? 0 : 1);
