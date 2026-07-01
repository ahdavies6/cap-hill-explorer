// Build step: encrypt build/data.json with SITE_PASSWORD (an env var / CI secret),
// then delete the plaintext so it is never published. If SITE_PASSWORD is unset
// (e.g. local dev), this is a no-op and data.json stays plaintext.
//
// Output build/data.enc is AES-256-GCM with a PBKDF2-SHA256 key. The ciphertext
// has the 16-byte GCM tag appended, matching what the browser's WebCrypto
// SubtleCrypto.decrypt expects, so index.html can decrypt it directly.
import { readFileSync, writeFileSync, rmSync, existsSync } from 'node:fs';
import { pbkdf2Sync, randomBytes, createCipheriv } from 'node:crypto';

const pw = process.env.SITE_PASSWORD;
const SRC = 'build/data.json';
const OUT = 'build/data.enc';
const ITER = 150000;

if (!pw) {
  console.log('[encrypt] SITE_PASSWORD not set — leaving data.json plaintext (dev mode)');
  process.exit(0);
}
if (!existsSync(SRC)) {
  console.error(`[encrypt] ${SRC} missing — run snapshot.py first`);
  process.exit(1);
}

const plaintext = readFileSync(SRC);
const salt = randomBytes(16);
const iv = randomBytes(12);
const key = pbkdf2Sync(pw, salt, ITER, 32, 'sha256');
const cipher = createCipheriv('aes-256-gcm', key, iv);
const body = Buffer.concat([cipher.update(plaintext), cipher.final()]);
const tag = cipher.getAuthTag();

const env = {
  v: 1,
  kdf: 'PBKDF2-SHA256',
  iter: ITER,
  salt: salt.toString('base64'),
  iv: iv.toString('base64'),
  ct: Buffer.concat([body, tag]).toString('base64'), // tag appended for WebCrypto
};
writeFileSync(OUT, JSON.stringify(env));
rmSync(SRC); // never publish the plaintext
console.log(`[encrypt] wrote ${OUT} (${env.ct.length} b64 chars) and removed plaintext ${SRC}`);
