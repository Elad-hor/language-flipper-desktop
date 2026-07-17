<?php
// contact.php — receives the Language Flipper contact form and emails it.
// NOTES: mail() is the baseline; if the host's mail() has poor Gmail deliverability,
// it can be swapped for SMTP at deploy time — the form/action stays the same.
declare(strict_types=1);

const TO = 'falafeltikunim@gmail.com';

function fail(int $code, string $msg): never {
  http_response_code($code);
  header('Content-Type: text/plain; charset=utf-8');
  echo $msg;
  exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') fail(405, 'Method not allowed');

// Where to send the user back to (their own language page). Only accept a safe
// same-site absolute path; anything else falls back to the English contact page.
$redirect = $_POST['redirect'] ?? '/contact-us/';
if (!is_string($redirect) || $redirect === '' || $redirect[0] !== '/'
    || strncmp($redirect, '//', 2) === 0 || preg_match('/[\r\n]/', $redirect)) {
  $redirect = '/contact-us/';
}
$success = $redirect . '?sent=1';

// Honeypot: real users leave 'website' empty; bots fill it.
if (!empty($_POST['website'] ?? '')) { header('Location: ' . $success); exit; }

$first   = trim($_POST['first_name'] ?? '');
$last    = trim($_POST['last_name'] ?? '');
$email   = trim($_POST['email'] ?? '');
$company = trim($_POST['company'] ?? '');
$message = trim($_POST['message'] ?? '');

if ($email === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) fail(422, 'Valid email required');
if ($company === '') fail(422, 'Company required');

// Header-injection guard
foreach ([$first, $last, $email, $company] as $v) {
  if (preg_match('/[\r\n]/', $v)) fail(422, 'Invalid input');
}

$subject = 'Language Flipper contact from ' . ($first !== '' ? $first : 'website');
$body = "Name: $first $last\nEmail: $email\nCompany: $company\n\nMessage:\n$message\n";
$headers = 'From: Language Flipper <no-reply@languageflipper.com>' . "\r\n"
         . 'Reply-To: ' . $email . "\r\n"
         . 'Content-Type: text/plain; charset=utf-8';

if (!mail(TO, $subject, $body, $headers)) fail(500, 'Send failed');

header('Location: ' . $success);
exit;
