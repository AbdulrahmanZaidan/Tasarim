import crypto from 'node:crypto';
// Supabase CLI'nin yerel geliştirme için kullandığı herkesçe bilinen VARSAYILAN test gizli anahtarı (yalnızca yerel test ortamı)
const secret = 'super-secret-jwt-token-with-at-least-32-characters-long';
const b64 = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
export function sign(payload) {
  const h = b64({ alg: 'HS256', typ: 'JWT' }), p = b64(payload);
  const s = crypto.createHmac('sha256', secret).update(`${h}.${p}`).digest('base64url');
  return `${h}.${p}.${s}`;
}
const iat = 1700000000, exp = 2100000000;
export const ANON = sign({ iss: 'supabase-demo', role: 'anon', iat, exp });
export const SERVICE = sign({ iss: 'supabase-demo', role: 'service_role', iat, exp });
if (process.argv[2] === 'print') console.log(`ANON_KEY=${ANON}\nSERVICE_KEY=${SERVICE}`);
