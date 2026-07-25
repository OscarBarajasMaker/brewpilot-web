// Proper scope analysis. Regex cannot do this: it cannot tell a declaration from a
// string fragment, and it cannot see multi-declarator var lists. acorn can.
// acorn resolution, portable. The first version of this file hardcoded a Linux
// container path, which would have failed on Oscar's Windows box on the first run.
// Try a local require, then the machine's global npm root, then say so plainly.
let acorn;
try { acorn = require('acorn'); }
catch (e) {
  try {
    const root = require('child_process').execSync('npm root -g', {stdio:['ignore','pipe','ignore']}).toString().trim();
    acorn = require(require('path').join(root, 'acorn'));
  } catch (e2) {
    console.error('undef.js needs acorn:  npm install -g acorn');
    process.exit(2);
  }
}
const fs=require('fs');

const html=fs.readFileSync(process.argv[2],'utf8');
const m=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
const js=m[m.length-1][1];
const ast=acorn.parse(js,{ecmaVersion:2022});

const GLOBALS=new Set(('window document console Math JSON Date Array Object String Number Boolean RegExp Error '+
 'Promise Map Set WeakMap WeakSet Symbol Proxy Reflect parseInt parseFloat isNaN isFinite encodeURIComponent '+
 'decodeURIComponent encodeURI decodeURI setTimeout setInterval clearTimeout clearInterval fetch alert confirm '+
 'prompt localStorage sessionStorage location navigator history screen XMLHttpRequest FormData URL '+
 'URLSearchParams Blob File FileReader Image Audio Event CustomEvent MutationObserver IntersectionObserver '+
 'ResizeObserver requestAnimationFrame cancelAnimationFrame performance crypto atob btoa Intl caches self '+
 'globalThis google gapi Notification TextEncoder TextDecoder AbortController structuredClone queueMicrotask '+
 'matchMedia getComputedStyle Uint8Array Float64Array ArrayBuffer BigInt Function eval arguments undefined '+
 'NaN Infinity HTMLElement Node NodeList Element NodeFilter CSS AudioContext webkitAudioContext').split(' '));

// collect every binding in every scope
const scopes=[]; const stack=[];
function push(node){ const s={node,names:new Set(),parent:stack[stack.length-1]||null}; scopes.push(s); stack.push(s); return s }
function pop(){ stack.pop() }
function declPat(p,s){ if(!p)return;
  if(p.type==='Identifier') s.names.add(p.name);
  else if(p.type==='ObjectPattern') p.properties.forEach(q=>declPat(q.value||q.argument,s));
  else if(p.type==='ArrayPattern') p.elements.forEach(q=>declPat(q,s));
  else if(p.type==='AssignmentPattern') declPat(p.left,s);
  else if(p.type==='RestElement') declPat(p.argument,s);
}
function hoist(body,s){ (body||[]).forEach(n=>{
  if(!n) return;
  if(n.type==='FunctionDeclaration'&&n.id) s.names.add(n.id.name);
  if(n.type==='VariableDeclaration') n.declarations.forEach(d=>declPat(d.id,s));
  if(n.type==='ClassDeclaration'&&n.id) s.names.add(n.id.name);
  ['body','consequent','alternate'].forEach(k=>{ const c=n[k];
    if(Array.isArray(c)) hoist(c,s); else if(c&&c.type==='BlockStatement') hoist(c.body,s); });
  if(n.type==='TryStatement'){ hoist(n.block.body,s); if(n.handler) hoist(n.handler.body.body,s); if(n.finalizer) hoist(n.finalizer.body,s) }
  if(n.type==='ForStatement'&&n.init&&n.init.type==='VariableDeclaration') n.init.declarations.forEach(d=>declPat(d.id,s));
  if((n.type==='ForOfStatement'||n.type==='ForInStatement')&&n.left.type==='VariableDeclaration') n.left.declarations.forEach(d=>declPat(d.id,s));
  if(n.type==='LabeledStatement') hoist([n.body],s);
})}
const used=[];
function walk(n,parent){
  if(!n||typeof n.type!=='string') return;
  const fn=/Function(Declaration|Expression)|ArrowFunctionExpression/.test(n.type);
  if(n.type==='Program'){ const s=push(n); hoist(n.body,s); n.body.forEach(c=>walk(c,n)); pop(); return }
  if(fn){ const s=push(n); (n.params||[]).forEach(p=>declPat(p,s)); if(n.id) s.names.add(n.id.name);
          if(n.body.type==='BlockStatement') hoist(n.body.body,s); walkKids(n,s); pop(); return }
  if(n.type==='CatchClause'){ const s=push(n); declPat(n.param,s); hoist(n.body.body,s); walkKids(n,s); pop(); return }
  if(n.type==='Identifier'){
    if(parent&&parent.type==='MemberExpression'&&parent.property===n&&!parent.computed) return;
    if(parent&&parent.type==='Property'&&parent.key===n&&!parent.computed) return;
    used.push({name:n.name,scope:stack[stack.length-1],start:n.start});
    return;
  }
  walkKids(n,stack[stack.length-1]);
}
function walkKids(n){ for(const k in n){ if(k==='type'||k==='start'||k==='end')continue;
  const v=n[k];
  if(Array.isArray(v)) v.forEach(c=>c&&typeof c.type==='string'&&walk(c,n));
  else if(v&&typeof v.type==='string') walk(v,n); } }
walk(ast,null);

const bad=new Map();
for(const u of used){
  let s=u.scope, ok=false;
  while(s){ if(s.names.has(u.name)){ ok=true;break } s=s.parent }
  if(!ok && !GLOBALS.has(u.name)) bad.set(u.name,(bad.get(u.name)||0)+1);
}
const out=[...bad.entries()].sort();
console.log('undeclared identifiers:', out.length);
out.forEach(([n,c])=>console.log('   '+n+'  x'+c));
// non-zero exit so update.ps1 can refuse to publish, the way audit.py does
process.exit(out.length ? 1 : 0);
