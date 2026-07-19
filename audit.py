#!/usr/bin/env python3
"""
audit.py - catches the class of bug that got through repeatedly this session.

Every one had the same shape: something referred to a name that did not exist,
nothing threw, and the failure was invisible until a screenshot arrived.

  renderDurability()  looked up #duraTitleEl        -> never existed, early
                                                       returned forever, the
                                                       whole feature was dead
  insights render     wrote into #insBody           -> never existed
  retitleCtas()       looked up #duraGoBtn          -> never existed, no-op
  update.ps1          read deployed_index.html      -> nothing ever wrote it
  44 i18n keys        added to en:{} only           -> Spanish silently fell
                                                       back to English
  set-client-id.ps1   matched 'GOOGLE_CLIENT_ID=''' -> prettier ships "" 

JS does not error on a missing id: getElementById returns null and the code
quietly does nothing. That is why these survived. A grep does not catch them
either, because the SOURCE says one thing and prettier ships another. So this
runs against the BUILT file, which is the only text that is true.

Exit code is non-zero on failure, so update.ps1 can refuse to publish.
"""
import re, sys, json, os

# Bump this whenever a check is added or changed.
#
# Why it exists: Oscar published with a stale audit.py and it printed ALL CLEAR.
# The reachability and exec-revival checks were simply absent, so they could not
# fail. The ONLY tell was the invariant count - 433 instead of 665 - and that is
# data-dependent, so it is not a tell anyone can rely on. A green check that is
# not checking is the exact failure this file exists to prevent, so the file had
# better not be able to do it to itself. Print the version next to the count.
AUDIT_VERSION = 'v4-2026-07-17'

HTML = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/render/index_v5.html'
src = open(HTML, encoding='utf-8').read()

fails, warns, checks = [], [], 0

def fail(cat, msg):
    fails.append((cat, msg))
def warn(cat, msg):
    warns.append((cat, msg))

# ---------------------------------------------------------------- helpers
def js_blob(s):
    m = re.findall(r'<script>(.*?)</script>', s, re.S)
    return m[-1] if m else ''

def strip_comments(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    s = re.sub(r'(?m)^\s*//.*$', '', s)
    return s

JS = strip_comments(js_blob(src))
BODY = re.sub(r'<script>.*?</script>', '', src, flags=re.S)

# ============================================================ 1. INVENTED IDS
# The big one. getElementById('x') where no id="x" exists anywhere. Silent null,
# silent no-op, dead feature. This alone would have caught three bugs.
ids_in_html = set(re.findall(r'\bid\s*=\s*["\']([^"\']+)["\']', src))
# ids created at runtime count as real
ids_made = set(re.findall(r'\.id\s*=\s*["\']([^"\']+)["\']', JS))
ids_made |= set(re.findall(r'setAttribute\(\s*["\']id["\']\s*,\s*["\']([^"\']+)["\']', JS))
known = ids_in_html | ids_made

looked_up = set(re.findall(r'getElementById\(\s*["\']([^"\']+)["\']\s*\)', JS))
for i in sorted(looked_up - known):
    fail('invented-id', "getElementById('%s') but no element has that id -> silent no-op" % i)
checks += len(looked_up)

# ================================================== 2. QUERY SELECTOR TARGETS
# Same failure via a different door: querySelector('.thing') that matches nothing.
sel = set(re.findall(r'querySelector(?:All)?\(\s*["\']([.#][A-Za-z0-9_-]+)["\']\s*\)', JS))
classes = set()
for m in re.finditer(r'class\s*=\s*["\']([^"\']+)["\']', src):
    classes |= set(m.group(1).split())
made_classes = set()
for m in re.finditer(r'className\s*=\s*["\']([^"\']+)["\']', JS):
    made_classes |= set(m.group(1).split())
for m in re.finditer(r'classList\.add\(\s*["\']([^"\']+)["\']', JS):
    made_classes.add(m.group(1))
for s2 in sorted(sel):
    name = s2[1:]
    if s2.startswith('#'):
        if name not in known:
            fail('dead-selector', "querySelector('%s') matches no element" % s2)
    else:
        if name not in classes and name not in made_classes:
            fail('dead-selector', "querySelector('%s') matches no class" % s2)
checks += len(sel)

# ==================================================== 3. I18N KEY PARITY
# 44 keys were English-only while Spanish is the DEFAULT language.
m = re.search(r'var I18N\s*=\s*\{', JS)
if not m:
    fail('i18n', 'I18N dictionary not found at all')
else:
    i = m.end(); d = 1; j = i
    while j < len(JS) and d > 0:
        if JS[j] == '{': d += 1
        elif JS[j] == '}': d -= 1
        j += 1
    blob = JS[i:j]
    esi = blob.find('es:')
    if esi < 0:
        fail('i18n', 'no es:{} dictionary found')
    else:
        en = dict(re.findall(r'(\w+):\s*"((?:[^"\\]|\\.)*)"', blob[:esi]))
        es = dict(re.findall(r'(\w+):\s*"((?:[^"\\]|\\.)*)"', blob[esi:]))
        for k in sorted(set(en) - set(es)):
            fail('i18n', "key '%s' is English-only -> renders in English for the default language" % k)
        for k in sorted(set(es) - set(en)):
            warn('i18n', "key '%s' is in es but not en" % k)
        checks += len(en)

        # 3b. every t('key') must resolve, or it renders as the raw key
        used = set(re.findall(r"\bt\(\s*['\"]([A-Za-z0-9_]+)['\"]\s*\)", JS))
        for k in sorted(used - set(en)):
            fail('i18n', "t('%s') called but the key does not exist -> renders blank or raw" % k)
        checks += len(used)

        # 3b2. data-i18n ATTRIBUTES must resolve too.
        # 3b only checks t('key') calls in JS. applyLang() also does
        #   el.textContent = t(el.getAttribute('data-i18n'))
        # for every [data-i18n] element, and t() returns the KEY when it misses.
        # So a stale attribute renders the literal string 's2t' on screen. Nothing
        # caught that, and the wizard is built almost entirely from these.
        attrs = set(re.findall(r'''data-i18n\s*=\s*["']([A-Za-z0-9_]+)["']''', src))
        for k in sorted(attrs - set(en)):
            fail('i18n', "data-i18n='%s' but the key does not exist -> the raw key renders on screen" % k)
        checks += len(attrs)
        attrs_ph = set(re.findall(r'''data-i18n-ph\s*=\s*["']([A-Za-z0-9_]+)["']''', src))
        for k in sorted(attrs_ph - set(en)):
            fail('i18n', "data-i18n-ph='%s' but the key does not exist -> the raw key renders as the placeholder" % k)
        checks += len(attrs_ph)

        # 3c. placeholders must match between languages, or {n} prints literally
        for k in sorted(set(en) & set(es)):
            pe = set(re.findall(r'\{(\w+)\}', en[k]))
            ps = set(re.findall(r'\{(\w+)\}', es[k]))
            if pe != ps:
                fail('i18n', "key '%s' placeholders differ: en%s vs es%s" % (k, sorted(pe), sorted(ps)))

# ============================================== 4. UNRESOLVED PLACEHOLDERS
for ph in re.findall(r'__[A-Z_]{4,}__', src):
    fail('placeholder', "'%s' was never substituted at build time" % ph)
checks += 1

# ================================================ 5. STALE CONNECTEDNESS
# Four functions each decided "am I connected" separately and I fixed them one
# at a time as Oscar found each. Assert the pattern is gone, not the instances.
for m in re.finditer(r'connected\s*=\s*!!\(\s*WEBHOOK\s*&&\s*WEBHOOK\(\)\s*\)', JS):
    fail('stale-check', 'a connectedness check still reads WEBHOOK() only, ignoring Google Drive')
checks += 1

# ==================================================== 6. FUNCTIONS EXIST
# Calling an undefined function throws, but often inside a try{}catch{} that
# swallows it. Check the ones the repaint chain depends on.
# Was a hardcoded list, which meant a new function could be called and never
# defined without anyone noticing: renderLogPlan slipped through exactly that
# way, called inside a try/catch that swallowed the ReferenceError.
# Now: anything called inside a try{} that is never defined anywhere.
defined = set(re.findall(r'function\s+(\w+)\s*\(', JS))
defined |= set(re.findall(r'(?:var|let|const)\s+(\w+)\s*=', JS))   # incl. aliases: var _rh2 = renderHero
defined |= set(re.findall(r'(\w+)\s*[:=]\s*(?:async\s+)?function', JS))
BUILTIN = {'if','for','while','switch','catch','return','typeof','function','new',
           'parseInt','parseFloat','String','Number','Boolean','Array','Object','JSON',
           'Math','Date','alert','confirm','fetch','setTimeout','setInterval','isNaN',
           'isFinite','encodeURIComponent','decodeURIComponent','Promise','RegExp','Error'}
swallowed = re.findall(r'try\s*\{\s*(\w+)\s*\(\s*\)\s*;?\s*\}\s*catch', JS)
for fn in sorted(set(swallowed)):
    if fn in BUILTIN or fn in defined: continue
    fail('missing-fn', "try{ %s() }catch{} but %s is never defined -> the error is swallowed and the feature is silently dead" % (fn, fn))
checks += len(swallowed)

# ================================================ 7. THE SCOPE MUST NOT CREEP
# drive.file is non-sensitive: that is the whole reason there is no verification
# wall. auth/spreadsheets is SENSITIVE and would bring the wall back.
if 'auth/drive.file' not in src:
    fail('oauth', 'the drive.file scope is missing entirely')
if re.search(r"scope\s*[:=]\s*['\"][^'\"]*auth/spreadsheets", JS):
    fail('oauth', 'requests auth/spreadsheets, which is SENSITIVE and re-triggers verification')
if re.search(r"prompt\s*:\s*['\"]consent['\"]", JS):
    fail('oauth', "forces prompt:'consent', costing a needless tap on every renewal")
checks += 3

# ==================================================== 8. ENCODING / ASCII
if re.search(r'Ã|â€|Â', src):
    fail('encoding', 'mojibake found: the file was written with the wrong encoding')
if '\u2014' in src:
    fail('encoding', 'em-dash found (breaks the PowerShell parser)')
for icon in ['\u25C9', '\u25A2', '\u25CE']:
    if src.count(icon) != 1:
        warn('icons', 'icon %r appears %d times, expected 1' % (icon, src.count(icon)))
checks += 2

# ============================================ 9. THE TEMPLATE LEAK GUARD
WORKING = '1-mVIfljFg5rjtA55q_KrXv0Fshqk-okwhpCmnpW-WlM'
if WORKING in src:
    fail('privacy', "Oscar's PERSONAL working sheet id is in the shipped file")
checks += 1

# ==================================================== 10. BUILD STAMP
if not re.search(r'BUILD\s*=\s*["\']\d{4}-\d{2}-\d{2}-\d{4}-[0-9a-f]{6}["\']', src):
    fail('build', 'no build stamp: there is no way to tell which build is live')
checks += 1

# ============================================ 11. REACHABILITY, NOT SPELLING
# Every check above asks "does this name resolve". logFilter passed all of them:
# nothing was misspelled, no id was invented, every t() key existed. It was simply
# a write path that never called dataMode(), so a Drive user's brew went nowhere.
# 437 invariants said ALL CLEAR on that build. The check has to encode the
# invariant that was violated, not the symptom that happened to be visible.
#
# The invariant: if a function builds a brew row, it must route through the data
# layer. logshot did. logFilter did not. This one line fails the build that shipped.
for m in re.finditer(r'(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*\{', JS):
    name = m.group(1)
    i = m.end() - 1
    d = 0; j = i
    while j < len(JS):
        if JS[j] == '{': d += 1
        elif JS[j] == '}':
            d -= 1
            if d == 0: break
        j += 1
    body = JS[i:j+1]
    if re.search(r'\blet\s+cols\s*=\s*\[', body) and 'dataMode(' not in body:
        fail('unreachable', "%s() builds a brew row but never calls dataMode() -> the write "
                            "goes nowhere for whichever mode it forgot" % name)
    checks += 1

# ================================================== 12. /exec STAYS AMPUTATED
# Deleting a branch is easy. Keeping it deleted is the part that needs a machine.
# Comments are stripped from JS already, so a historical note does not trip this.
if re.search(r'\bWEBHOOK\s*\(', JS):
    fail('exec-revival', 'WEBHOOK() is called again: the /exec branch is growing back')
if re.search(r"['\"]action=", JS):
    fail('exec-revival', "an 'action=' Apps Script call is back in the JS")
if re.search(r'\bWEBHOOK_URL\b', JS):
    fail('exec-revival', 'WEBHOOK_URL is back')
if 'SHEET_TEMPLATE_URL' in JS:
    fail('exec-revival', 'SHEET_TEMPLATE_URL is back: that is the legacy copy-a-template flow')
if 'script.google.com/macros' in src:
    fail('exec-revival', 'an Apps Script /macros URL is in the shipped file')
checks += 5

# ---------------------------------------------------------------- report
print()
print('  audit of %s' % os.path.basename(HTML))
print('  audit.py %s  (%d invariants checked)' % (AUDIT_VERSION, checks))
print()
if warns:
    for c, m in warns:
        print('  WARN  [%s] %s' % (c, m))
    print()
# ---- inline handler references must resolve (onclick/onchange/oninput) ----
# undef.js parses script scope but not inline HTML handlers, so a handler calling a
# deleted function (e.g. the /exec amputation leaving onclick=saveWebhook) slips both
# gates and dies at runtime. Catch it here.
_defined = set(re.findall(r'function\s+([A-Za-z_$][\w$]*)\s*\(', src))
_defined |= set(re.findall(r'(?:var|let|const)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function|\()', src))
_hbuiltins = {'document','if','return','localStorage','JSON','setTimeout','alert','confirm',
              'parseFloat','parseInt','Math','this','var','getElementById','sendPrompt'}
for _h in re.findall(r'on(?:click|change|input)\s*=\s*["\']([^"\']+)["\']', src):
    for _fn in re.findall(r'([A-Za-z_$][\w$]*)\s*\(', _h):
        if _fn not in _defined and _fn not in _hbuiltins:
            fail('dangling-handler', "inline handler calls undefined function " + _fn + "()")

if fails:
    for c, m in fails:
        print('  FAIL  [%s] %s' % (c, m))
    print()
    print('  %d FAILURE(S). Do not publish.' % len(fails))
    sys.exit(1)
print('  ALL CLEAR')
sys.exit(0)
