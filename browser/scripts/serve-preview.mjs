/** Local static server applying the same _headers policy used by Pages. */
import http from 'node:http';
import {readFile, stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root = path.resolve(fileURLToPath(new URL('../dist/', import.meta.url)));
const types = {'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json','.wasm':'application/wasm','.zip':'application/zip','.txt':'text/plain; charset=utf-8'};
const policies = [];
let current;
for (const line of (await readFile(path.join(root, '_headers'), 'utf8')).split('\n')) {
  if (line.startsWith('/')) {current = {pattern:line.trim(),headers:{}}; policies.push(current);}
  else if (current && line.includes(':')) {const pos=line.indexOf(':'); current.headers[line.slice(0,pos).trim()] = line.slice(pos+1).trim();}
}
const port = Number(process.env.PORT || 4173);
http.createServer(async (req,res) => {
  if (!['GET','HEAD'].includes(req.method)) {res.writeHead(405);res.end();return;}
  try {
    const pathname = decodeURIComponent(new URL(req.url,'http://localhost').pathname);
    let file = path.resolve(root, '.' + pathname);
    if (file !== root && !file.startsWith(root + path.sep)) throw new Error('path');
    if ((await stat(file)).isDirectory()) file = path.join(file,'index.html');
    const headers = {'Content-Type': types[path.extname(file)] || 'application/octet-stream'};
    for (const policy of policies) if (policy.pattern.endsWith('*') ? pathname.startsWith(policy.pattern.slice(0,-1)) : pathname===policy.pattern) Object.assign(headers,policy.headers);
    const bytes = await readFile(file);res.writeHead(200,headers);res.end(req.method==='HEAD'?undefined:bytes);
  } catch {res.writeHead(404,{'Content-Type':'text/plain'});res.end('Not found');}
}).listen(port,'127.0.0.1',()=>console.log(`Static preview: http://127.0.0.1:${port}`));
