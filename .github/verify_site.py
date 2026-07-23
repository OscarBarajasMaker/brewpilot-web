#!/usr/bin/env python3
"""
verify_site.py - the assembled _site must contain everything index.html asks for.

Why this exists, precisely:

The workflow builds _site from an explicit copy list:

    cp index.html manifest.json sw.js _site/

On 2026-07-23 the app started loading client-id.js, which holds the Google OAuth
client ID. The file was committed, it was on main, raw.githubusercontent served
it, and the repo listing showed it sitting next to index.html. But it was not on
that copy list, so it never reached _site, and the deployed site returned 404 for
it from every edge. Google sign in was off for every user for hours.

Nothing failed. The workflow was green. undef.js was green. audit.py was green,
944 invariants. Every gate we had checked the SOURCE and none of them checked
what was actually being shipped. The copy list was a correctness step with no
test behind it, which is the same shape as every other bug this project has hit.

So: parse the index.html that is ABOUT TO BE DEPLOYED, collect every local file
it references, and assert each one is present in _site. A new asset added to the
app now breaks the build the first time it is missed, loudly, before deploy,
instead of silently 404ing in production.

Usage:  python3 .github/verify_site.py _site
Exit code is non-zero on failure, so the workflow stops.
"""
import os
import re
import sys

site = sys.argv[1] if len(sys.argv) > 1 else '_site'

idx_path = os.path.join(site, 'index.html')
if not os.path.exists(idx_path):
    print('::error::%s does not exist. The site was not assembled.' % idx_path)
    sys.exit(1)

html = open(idx_path, encoding='utf-8').read()

# Every local reference index.html makes. Remote URLs are somebody else's
# problem: the Google Identity script is loaded from accounts.google.com and
# must not be required to exist here.
refs = set()
for m in re.finditer(r'<script[^>]+src\s*=\s*["\']([^"\']+)["\']', html):
    refs.add(m.group(1))
for m in re.finditer(r'<link[^>]+href\s*=\s*["\']([^"\']+)["\']', html):
    refs.add(m.group(1))

# The service worker is registered from JS, not from a tag, and it carries a
# ?v= query. Catch it too, since a missing sw.js breaks installs silently.
for m in re.finditer(r'register\(\s*["\']([^"\'?]+)', html):
    refs.add(m.group(1))

local = []
for r in sorted(refs):
    if r.startswith('http://') or r.startswith('https://') or r.startswith('//'):
        continue
    if r.startswith('data:') or r.startswith('#'):
        continue
    local.append(r.split('?')[0].lstrip('./'))

missing = []
for r in sorted(set(local)):
    if not os.path.exists(os.path.join(site, r)):
        missing.append(r)

print('index.html references %d local files:' % len(set(local)))
for r in sorted(set(local)):
    mark = 'MISSING' if r in missing else 'ok'
    print('   %-28s %s' % (r, mark))

if missing:
    print()
    for r in missing:
        print("::error::index.html loads '%s' but it is not in %s. "
              "Add it to the Assemble site copy list in the workflow." % (r, site))
    sys.exit(1)

# The one asset whose CONTENT has to be right, not merely present. An empty
# client-id.js would pass the existence check above and still ship an app that
# cannot reach Google Drive, which is the exact outage this file was born from.
cid_path = os.path.join(site, 'client-id.js')
if os.path.exists(cid_path):
    body = open(cid_path, encoding='utf-8').read()
    m = re.search(r"BREWPILOT_CLIENT_ID\s*=\s*['\"]([^'\"]*)['\"]", body)
    val = m.group(1).strip() if m else ''
    if not val.endswith('.apps.googleusercontent.com'):
        print("::error::%s does not set a Google client ID. Google sign in would be "
              "off for every user." % cid_path)
        sys.exit(1)
    print()
    print('client-id.js carries a real ID: %s...' % val[:22])

print()
print('site assembly verified')
sys.exit(0)
