// Yerel test ağ geçidi: Supabase'in Kong yönlendirmesinin basit karşılığı.
import http from 'node:http';
const routes = [['/rest/v1', 3000], ['/auth/v1', 9999], ['/storage/v1', 5000]];
const cors = {
  'access-control-allow-origin': '*',
  'access-control-allow-headers': 'authorization, x-client-info, apikey, content-type, prefer, range, accept-profile, content-profile, x-upsert, cache-control, x-supabase-api-version',
  'access-control-allow-methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD',
  'access-control-expose-headers': 'content-range, content-length, x-supabase-api-version',
};
http.createServer((req, res) => {
  if (req.method === 'OPTIONS') { res.writeHead(204, cors); return res.end(); }
  const r = routes.find(([p]) => req.url.startsWith(p + '/') || req.url === p || req.url.startsWith(p + '?'));
  if (!r) { res.writeHead(404, cors); return res.end('not found'); }
  const path = req.url.slice(r[0].length) || '/';
  const headers = { ...req.headers, host: `127.0.0.1:${r[1]}` };
  if (!headers.authorization && headers.apikey) headers.authorization = `Bearer ${headers.apikey}`;
  const up = http.request({ host: '127.0.0.1', port: r[1], path, method: req.method, headers }, (u) => {
    const h = { ...u.headers, ...cors };
    res.writeHead(u.statusCode || 502, h); u.pipe(res);
  });
  up.on('error', (e) => { res.writeHead(502, cors); res.end(String(e)); });
  req.pipe(up);
}).listen(54321, '127.0.0.1', () => console.log('gateway :54321'));
