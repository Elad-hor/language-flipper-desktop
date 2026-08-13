/**
 * Contact form handler — the replacement for contact.php.
 *
 * Hostinger ran the form through PHP mail(); a static host has no PHP, so this
 * runs in a Cloudflare Worker and hands the message to Mailgun or Resend.
 *
 * Behaviour is deliberately identical to the PHP version, because the form
 * markup and the success banner both depend on it:
 *   - POST only
 *   - honeypot field `website`; if filled, pretend success and send nothing
 *   - `email` required and valid, `company` required
 *   - reject CR/LF in header-bound fields (header injection)
 *   - redirect back to `redirect` + "?sent=1", where ContactForm.astro reveals
 *     the success banner client-side. Hebrew submissions carry their own
 *     Hebrew path, which is why the redirect is echoed rather than hardcoded.
 *   - only same-site absolute paths are accepted as a redirect target, so this
 *     can't be turned into an open redirect
 *
 * Routed from worker/index.ts for both /contact and /contact.php: the old
 * .php route is kept alive so no cached page or bookmark breaks during the
 * move off Hostinger.
 */

/**
 * Either provider works — whichever is configured wins, Mailgun first.
 * Two are supported because Mailgun's free plan caps API keys (and wants a
 * card), while Resend's does not; there is no reason to be blocked on whichever
 * signup happens to be more awkward on the day.
 */
export interface ContactEnv {
  /** Mailgun private API key. A secret — never in wrangler.jsonc. */
  MAILGUN_API_KEY?: string;
  /** The sending domain as configured in Mailgun, e.g. mg.languageflipper.com. */
  MAILGUN_DOMAIN?: string;
  /**
   * Mailgun region endpoint. EU accounts MUST set this to
   * https://api.eu.mailgun.net — the US default returns 401 for EU domains,
   * which looks exactly like a bad API key.
   */
  MAILGUN_API_BASE?: string;

  /** Resend API key. A secret. Used when Mailgun is not configured. */
  RESEND_API_KEY?: string;

  /** Optional overrides; the defaults match the PHP version. */
  CONTACT_TO?: string;
  CONTACT_FROM?: string;
}

interface SendResult {
  ok: boolean;
  detail: string;
}

async function sendViaMailgun(
  env: ContactEnv, to: string, from: string, replyTo: string,
  subject: string, text: string,
): Promise<SendResult> {
  // Mailgun takes form-encoded fields and HTTP Basic auth with the literal
  // username "api".
  const params = new URLSearchParams({ from, to, subject, text, 'h:Reply-To': replyTo });
  const base = (env.MAILGUN_API_BASE || 'https://api.mailgun.net').replace(/\/+$/, '');
  const url = `${base}/v3/${encodeURIComponent(env.MAILGUN_DOMAIN!)}/messages`;

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Basic ${btoa(`api:${env.MAILGUN_API_KEY}`)}`,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: params.toString(),
  });
  // A 401 here usually means the region is wrong (an EU domain hitting the US
  // endpoint) rather than a bad key — see MAILGUN_API_BASE.
  return { ok: res.ok, detail: `Mailgun ${res.status} ${res.ok ? '' : await res.text()}` };
}

async function sendViaResend(
  env: ContactEnv, to: string, from: string, replyTo: string,
  subject: string, text: string,
): Promise<SendResult> {
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ from, to: [to], reply_to: replyTo, subject, text }),
  });
  return { ok: res.ok, detail: `Resend ${res.status} ${res.ok ? '' : await res.text()}` };
}

const DEFAULT_TO = 'falafeltikunim@gmail.com';
// Must be on the Mailgun sending domain, or delivery is rejected.
const DEFAULT_FROM = 'Language Flipper <no-reply@languageflipper.com>';

function textResponse(status: number, body: string): Response {
  return new Response(body, {
    status,
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
}

/** Same rule as the PHP: a same-site absolute path, no protocol-relative, no CR/LF. */
function safeRedirect(raw: unknown): string {
  if (typeof raw !== 'string') return '/contact-us/';
  if (raw === '' || raw[0] !== '/' || raw.startsWith('//') || /[\r\n]/.test(raw)) {
    return '/contact-us/';
  }
  return raw;
}

function isEmail(value: string): boolean {
  // Intentionally permissive, matching FILTER_VALIDATE_EMAIL's practical effect:
  // reject the obviously malformed, don't try to out-clever RFC 5322.
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

export async function handleContact(request: Request, env: ContactEnv): Promise<Response> {
  if (request.method !== 'POST') return textResponse(405, 'Method not allowed');

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return textResponse(400, 'Bad request');
  }

  const str = (k: string) => String(form.get(k) ?? '').trim();

  const redirect = safeRedirect(form.get('redirect'));
  const success = `${redirect}?sent=1`;

  // Honeypot: bots fill it, humans never see it. Report success, send nothing.
  if (str('website') !== '') return Response.redirect(new URL(success, request.url).toString(), 302);

  const first = str('first_name');
  const last = str('last_name');
  const email = str('email');
  const company = str('company');
  const message = str('message');

  if (email === '' || !isEmail(email)) return textResponse(422, 'Valid email required');
  if (company === '') return textResponse(422, 'Company required');
  for (const v of [first, last, email, company]) {
    if (/[\r\n]/.test(v)) return textResponse(422, 'Invalid input');
  }

  const useMailgun = Boolean(env.MAILGUN_API_KEY && env.MAILGUN_DOMAIN);
  const useResend = Boolean(env.RESEND_API_KEY);

  if (!useMailgun && !useResend) {
    // Loud, because a silently unconfigured form loses real enquiries.
    //
    // The response body distinguishes "nobody configured this" from "the
    // provider rejected it". Both used to return a bare "Send failed", which
    // made a missing environment variable indistinguishable from a bad API key
    // without reading the Worker logs. It names no values, only which case it
    // is, so it leaks nothing useful to anyone else.
    // Report WHICH piece is missing, as booleans. Values are never included,
    // so this reveals nothing sensitive — but it turns "it doesn't work" into
    // a one-line answer instead of a guessing game.
    const present =
      `mailgun_key=${Boolean(env.MAILGUN_API_KEY)} ` +
      `mailgun_domain=${Boolean(env.MAILGUN_DOMAIN)} ` +
      `resend_key=${Boolean(env.RESEND_API_KEY)}`;
    console.error(`No mail provider configured — ${present}`);
    return textResponse(500, `Send failed: no mail provider configured (${present})`);
  }

  const subject = `Language Flipper contact from ${first !== '' ? first : 'website'}`;
  const body =
    `Name: ${first} ${last}\n` +
    `Email: ${email}\n` +
    `Company: ${company}\n\n` +
    `Message:\n${message}\n`;

  const to = env.CONTACT_TO || DEFAULT_TO;
  const from = env.CONTACT_FROM || DEFAULT_FROM;

  try {
    // `email` becomes Reply-To so hitting reply in Gmail answers the visitor,
    // not the robot.
    const result = useMailgun
      ? await sendViaMailgun(env, to, from, email, subject, body)
      : await sendViaResend(env, to, from, email, subject, body);

    if (!result.ok) {
      console.error(`Mail provider rejected the message: ${result.detail}`);
      // Include the provider and status code, but never its response body —
      // that can echo back configuration details.
      const status = result.detail.split(' ').slice(0, 2).join(' ');
      return textResponse(500, `Send failed: provider rejected (${status})`);
    }
  } catch (err) {
    console.error(`Mail provider request failed: ${err}`);
    return textResponse(500, 'Send failed: provider unreachable');
  }

  return Response.redirect(new URL(success, request.url).toString(), 302);
}
