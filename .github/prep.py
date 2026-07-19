import os, re, sys

idx = 'index.html'
html = open(idx, encoding='utf-8').read()

cid = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
pat = r'GOOGLE_CLIENT_ID\s*=\s*(\'[^\']*\'|"[^"]*")'
m = re.search(pat, html)
if not m:
    print('::warning::GOOGLE_CLIENT_ID not found in index.html (build predates Google sign-in)')
else:
    cur = m.group(1).strip('\'"')
    if cur:
        print('client ID already present:', cur[:22] + '...')
    elif cid:
        html = re.sub(pat, 'GOOGLE_CLIENT_ID = "' + cid + '"', html, count=1)
        open(idx, 'w', encoding='utf-8').write(html)
        if cid not in open(idx, encoding='utf-8').read():
            print('::error::wrote index.html but the client ID is not in it'); sys.exit(1)
        print('client ID injected and verified on disk:', cid[:22] + '...')
    else:
        print('::warning::GOOGLE_CLIENT_ID secret is empty; the app ships without Google sign-in')

mb = re.search(r"BUILD\s*=\s*['\"]([^'\"]+)['\"]", html)
if mb and os.path.exists('sw.js'):
    stamp = mb.group(1)
    sw = open('sw.js', encoding='utf-8').read()
    sw = re.sub(r"var CACHE = '[^']*';", "var CACHE = 'brewpilot-" + stamp + "';", sw)
    open('sw.js', 'w', encoding='utf-8').write(sw)
    print('sw.js cache stamped: brewpilot-' + stamp)
else:
    print('::warning::no build stamp or sw.js found; cache not restamped')