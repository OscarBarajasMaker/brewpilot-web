#!/usr/bin/env python3
"""
prep.py - pre-deploy checks for BrewPilot.

WHAT CHANGED AND WHY, 2026-07-23.

This file used to inject the Google client ID into index.html from a repo
secret, and stamp sw.js with the build. Both jobs are gone, because both were
places where a correct publish depended on a step that only ran here.

  The ID now lives in client-id.js, committed to the repo, loaded by index.html
  in <head>. Any publish route produces a correct app, including uploading
  index.html from a phone through Working Copy, which no CI secret can help with.

  The service worker version now rides on the registration URL. index.html
  registers sw.js?v=<BUILD> and sw.js derives its own cache name from that
  query, so no script needs to rewrite it.

Leaving the old code here would have been worse than deleting it. Its index.html
regex no longer matches anything, and its sw.js regex no longer matches anything,
so both would have quietly done nothing while printing success. A no-op that
reports success is precisely how the empty client ID reached production and
survived there.

So this file now VERIFIES instead of writing. It fails the build rather than
letting a broken app deploy.
"""
import os
import re
import sys

fails = []

# ---------------------------------------------------------------- index.html
if not os.path.exists('index.html'):
    print('::error::index.html is missing')
    sys.exit(1)

html = open('index.html', encoding='utf-8').read()

if not re.search(r'<script\s+src\s*=\s*["\']client-id\.js["\']', html):
    fails.append('index.html does not load client-id.js. The client ID would have '
                 'nowhere to come from. This is an old build, rebuild and re-push.')

if re.search(r'googleusercontent\.com', html):
    fails.append('index.html contains a literal Google client ID. It belongs in '
                 'client-id.js, so that replacing index.html cannot lose it.')

if 'sw.js?v=' not in html:
    fails.append('index.html does not register sw.js with a ?v= version. The service '
                 'worker cache name could never change and users would keep an old shell.')

mb = re.search(r"BUILD\s*=\s*['\"]([^'\"]+)['\"]", html)
if not mb:
    fails.append('index.html has no build stamp, so there is no way to tell which '
                 'build is live.')
else:
    print('build: ' + mb.group(1))

# -------------------------------------------------------------- client-id.js
if not os.path.exists('client-id.js'):
    fails.append('client-id.js is missing from the repo. Run set-client-id.ps1 locally '
                 'and commit the file it writes.')
else:
    body = open('client-id.js', encoding='utf-8').read()
    m = re.search(r"BREWPILOT_CLIENT_ID\s*=\s*['\"]([^'\"]*)['\"]", body)
    val = m.group(1).strip() if m else ''
    if not val:
        fails.append('client-id.js does not set window.BREWPILOT_CLIENT_ID.')
    elif not val.endswith('.apps.googleusercontent.com'):
        fails.append('client-id.js does not hold a Google client ID: ' + val[:40])
    else:
        print('client ID: ' + val[:22] + '...')

# --------------------------------------------------------------------- sw.js
if not os.path.exists('sw.js'):
    fails.append('sw.js is missing')
else:
    sw = open('sw.js', encoding='utf-8').read()
    if '__BUILD_STAMP__' in sw:
        fails.append('sw.js still contains the __BUILD_STAMP__ placeholder.')
    if "searchParams.get('v')" not in sw:
        fails.append('sw.js does not derive its cache name from the ?v= query. That is '
                     'the old stamped sw.js, whose cache name freezes on any publish '
                     'route that does not rewrite it.')

# -------------------------------------------------------------------- report
print()
if fails:
    for f in fails:
        print('::error::' + f)
    print()
    print('%d problem(s). Not deploying.' % len(fails))
    sys.exit(1)
print('pre-deploy checks passed')
sys.exit(0)
