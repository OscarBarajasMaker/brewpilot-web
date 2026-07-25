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
AUDIT_VERSION = 'v14-2026-07-25'

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

# ======================================= 13. THE ID AND THE VERSION STAY OUTSIDE
# Build 12a3b2 went live with GOOGLE_CLIENT_ID = "" and a service worker whose
# cache name was frozen two builds back. Both had one cause: index.html was
# uploaded straight to the repo from a phone, and a correctness step lived in a
# PowerShell script on a PC that was not involved. A publish route that a script
# cannot reach must not be a route that can be wrong.
#
# So the ID moved into client-id.js and the SW version moved onto the
# registration URL. These checks keep them there.
if not re.search(r'<script\s+src\s*=\s*["\']client-id\.js["\']', src):
    fail('client-id', 'index.html does not load client-id.js -> the client ID has nowhere to come from')
if 'BREWPILOT_CLIENT_ID' not in JS:
    fail('client-id', 'GOOGLE_CLIENT_ID is not read from window.BREWPILOT_CLIENT_ID -> it is baked inline again')
if 'googleusercontent.com' in src:
    fail('client-id', 'a literal Google client ID is baked into index.html -> replacing this file loses it')
checks += 3

# ================================================ 14. SW VERSION IS DERIVED
# If the registration loses its ?v= the cache name silently freezes and users
# keep an old shell after a publish. Network first hides that until they are
# offline, which is the worst kind of bug: invisible until it is not.
if not re.search(r'register\(\s*["\']sw\.js\?v=', JS):
    fail('sw-version', 'the service worker is not registered as sw.js?v=<BUILD> -> the cache name cannot change')
checks += 1

# ================================ 15. THE PHONE PICKERS STAY PICKERS
# iOS shows a datalist only as keyboard suggestions, never as a tappable list,
# so an <input list=...> reads as free text on the device it is used on. Origin,
# varietal and region were exactly that: typed by hand, misspellings and all,
# into fields the app already had the answers for. pickerize() upgrades them to
# real selects at boot. These checks make sure the upgrade is still wired up and
# still points at elements that exist.
m_pk = re.search(r'function pickerizeAll\(\)\s*\{(.*?)\}', JS, re.S)
if not m_pk:
    fail('picker', 'pickerizeAll() is gone -> origin and varietal fall back to free text on iOS')
else:
    pk_ids = re.findall(r'["\']([A-Za-z0-9_]+)["\']', m_pk.group(1))
    if not pk_ids:
        fail('picker', 'pickerizeAll() upgrades no fields at all')
    for i in pk_ids:
        if i not in known:
            fail('picker', "pickerizeAll() upgrades '%s' but no element has that id" % i)
    checks += len(pk_ids)
if not re.search(r'pickerizeAll\(\s*\)', JS.replace('function pickerizeAll()', '')):
    fail('picker', 'pickerizeAll() is defined but never called -> the fields stay free text')
checks += 1

# The rotation used to open a bare prompt(), which meant retyping a coffee the
# app already knows, on a phone keyboard, with a typo creating a duplicate entry.
m_ra = re.search(r'function rotAdd\(\)\s*\{', JS)
if m_ra:
    i = m_ra.end() - 1
    d = 0; j = i
    while j < len(JS):
        if JS[j] == '{': d += 1
        elif JS[j] == '}':
            d -= 1
            if d == 0: break
        j += 1
    if re.search(r'\bprompt\s*\(', JS[i:j+1]):
        fail('picker', 'rotAdd() calls prompt() again -> the coffee has to be retyped by hand')
    checks += 1

# ================================ 16. THE PRE-I18N BOOT WINDOW
# t() is reachable from the boot sequence at the tail of the source script, which
# is concatenated BEFORE the blob that assigns I18N. var hoists the name and not
# the value, so I18N[LANG] read a property of undefined and threw. Both callers
# were async, so it surfaced as an unhandled rejection instead of a script abort:
# the page booted, nothing was visibly wrong, and applyHwLocks() silently never
# ran for the life of the build. Two checks, because two separate things had to
# be true for that to cost anything.
m_t = re.search(r'function t\(k\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_t:
    fail('boot-order', 't(k) is gone or reshaped -> the pre-I18N guard cannot be verified')
elif 'typeof I18N' not in m_t.group(1):
    fail('boot-order', 't(k) does not guard on I18N being defined -> any boot-time caller '
                       'that reaches it throws again, and async callers hide it as a rejection')
checks += 1

# The flag that closes a one-time boot block must be set AFTER the work it guards,
# or a thrower skips the rest and no later call ever retries it.
m_r = re.search(r'async function refresh\(\)\s*\{', JS)
if not m_r:
    fail('boot-order', 'refresh() is gone -> the one-time boot block cannot be verified')
else:
    i = m_r.end() - 1
    d = 0; j = i
    while j < len(JS):
        if JS[j] == '{': d += 1
        elif JS[j] == '}':
            d -= 1
            if d == 0: break
        j += 1
    rbody = JS[i:j+1]
    p_flag = rbody.find('M_INIT = true')
    p_hw   = rbody.find('applyHwLocks()')
    if p_flag < 0 or p_hw < 0:
        fail('boot-order', 'refresh() no longer sets M_INIT or no longer calls applyHwLocks()')
    elif p_flag < p_hw:
        fail('boot-order', 'refresh() sets M_INIT before applyHwLocks() -> a throw above it '
                           'skips the lock and the block never runs again')
    checks += 1

# ================================ 17. THE SHOT ROW REACHES THE SHEET
# The metric tail is appended to COLNAMES by concat rather than typed into the
# literal, so the list that defines the sheet header and the list bpApplyShot
# writes values from are one array. If that ever becomes two, a row is written
# with values under the wrong names and nothing errors.
if not re.search(r'\]\.concat\(BP_METRIC_COLS\)', JS):
    fail('schema', 'COLNAMES no longer concatenates BP_METRIC_COLS -> the metric columns '
                   'never reach the sheet header and every metric is written under a name '
                   'that does not exist')
if 'BP_METRIC_COLS.map(' not in JS:
    fail('schema', 'bpApplyShot no longer builds its tail from BP_METRIC_COLS -> the header '
                   'and the values can drift apart silently')
checks += 2

# A brew row that never goes through bpApplyShot is written at the OLD width, so
# its metric columns land empty and its shot_id, peak_bar and avg_flow_mls stay
# blank even when a handoff supplied them.
m_ls = re.search(r'async function logshot\(\)\s*\{', JS)
if m_ls:
    i = m_ls.end() - 1
    d = 0; j = i
    while j < len(JS):
        if JS[j] == '{': d += 1
        elif JS[j] == '}':
            d -= 1
            if d == 0: break
        j += 1
    if 'bpApplyShot(' not in JS[i:j+1]:
        fail('schema', 'logshot() builds a row without bpApplyShot() -> the row is written at '
                       'the old width and every metric column is dropped')
    checks += 1

# gRead must not pin a column bound at all. Too narrow and it returns a
# truncated header while gEnsureHeader, gPatchRow and gInvList all key off
# rows[0], so writes land under names that were never read. Too wide and the
# Sheets API answers 400 instead of clamping, which is what shipped: every read
# of the Inventory tab failed at once and took inventory, the coffee identity
# gate and the header migration with it. Both failure modes come from the same
# decision, so the invariant is that the decision is not made.
m_gr = re.search(r'function gRead\(tab\)\s*\{.*?\n      \}', JS, re.S)
if not m_gr:
    fail('schema', 'gRead is gone or reshaped, so the read range cannot be verified')
elif re.search(r'tab\s*\+\s*"!', m_gr.group(0)):
    fail('schema', 'gRead pins an A1 column range. Too narrow silently truncates the header, '
                   'too wide is a 400 on every read of a narrower tab. Ask for the tab by name.')
checks += 1

# ============================ 18. ONBOARDING DOES NOT EAT THE HANDOFF
# Both features move the visible tab on a timer, and onboarding fires second, so
# it silently won: a device that had never completed setup received the shot,
# filled the form, then jumped to settings and left the metrics on a tab nobody
# was looking at. Real, and invisible unless you happen to test on a fresh
# browser profile. The guard has to stay in front of that redirect.
m_ob = re.search(r'localStorage\.getItem\("onboarded"\)(.*?)openPanel\("setPanel"', JS, re.S)
if not m_ob:
    fail('handoff', 'the onboarding redirect is gone or reshaped, so its handoff guard cannot be verified')
elif 'BPSHOT' not in m_ob.group(1):
    fail('handoff', 'the onboarding redirect is not guarded on BPSHOT -> a handoff arriving on a '
                    'device that never finished setup gets pulled off the log form and the shot '
                    'metrics are stranded on a tab the person is not looking at')
checks += 1

# ============================ 19. ADOPTION IS BY SCHEMA, NOT BY NAME
# gListLogs matches any spreadsheet whose NAME CONTAINS BrewPilot. That is a
# search filter, not an identity test: a stray file in a signed-in account was
# adopted silently and every row went into it. The zero-rows branch of gAutoLink
# adopts a candidate outright with no further test, which is the branch it came
# in through, so the filter has to sit in front of the scoring, not inside it.
m_al = re.search(r'async function gAutoLink\(\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_al:
    fail('adoption', 'gAutoLink is gone or reshaped, so its schema filter cannot be verified')
else:
    if 'gRealLogs(' not in m_al.group(1):
        fail('adoption', 'gAutoLink does not filter through gRealLogs -> a spreadsheet is adopted '
                         'on a name substring alone and every row goes into a file this app '
                         'never created')
    if re.search(r'gAdopt\(\s*files\[', m_al.group(1)):
        fail('adoption', 'gAutoLink still adopts straight from the unfiltered files list')
    checks += 2

m_hs = re.search(r'async function gHasSchema\(id\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_hs:
    fail('adoption', 'gHasSchema is gone -> nothing tests that an adopted file is actually a log')
else:
    b = m_hs.group(1)
    if 'SHOT_TAB' not in b or 'INV_TAB' not in b:
        fail('adoption', 'gHasSchema no longer requires BOTH the Shot Log and Inventory tabs -> '
                         'an export or someone else\'s tool passes as ours')
    checks += 1

# Every gAdopt call has to pass the name it already has. gAdopt(id) alone leaves
# GNAME pointing at the PREVIOUS sheet, so the status line names the wrong file
# with full confidence, which is worse than naming none.
bad_adopt = [c for c in re.findall(r'gAdopt\(([^)]*)\)', JS) if ',' not in c and 'name' not in c]
if bad_adopt:
    fail('adoption', 'gAdopt called without a name at %d call site(s) -> the status line keeps the '
                     'previous sheet name against the new sheet data' % len(bad_adopt))
checks += 1

# Something on screen must say WHICH spreadsheet is being written to.
m_ss = re.search(r'function renderSheetStatus\(\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_ss:
    fail('adoption', 'renderSheetStatus is gone, so the sheet identity line cannot be verified')
elif 'GNAME' not in m_ss.group(1):
    fail('adoption', 'renderSheetStatus does not mention GNAME -> nothing on screen says which '
                     'spreadsheet is being written to and a stray looks like the real one')
checks += 1

if '<meta name="mobile-web-app-capable"' not in BODY:
    fail('meta', 'the unprefixed mobile-web-app-capable meta is gone -> only Safari reads the '
                 'apple- prefixed one')
checks += 1

# ============================ 20. THE LANE STORE
# A lane is one row per (coffee, type). Every invariant here exists because the
# alternative is a baseline that silently means something other than it says.

# The type is part of the identity. A lane keyed on the coffee alone collects
# espresso, soup and filter into one baseline the first time it is written, and
# nothing about the resulting number looks wrong.
m_li = re.search(r'function laneId\(coffee, type\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_li:
    fail('lane', 'laneId is gone, so the lane key cannot be verified')
else:
    b = m_li.group(1)
    if 'laneNormType' not in b:
        fail('lane', 'laneId does not normalise the type -> Espresso and espresso become two lanes')
    if not re.search(r'if \(!c \|\| !t\) return ""', b):
        fail('lane', 'laneId returns an id without a type -> all three styles collapse into one '
                     'baseline and a style switch reads as a grind collapse')
    checks += 2

# Filing must require canonical inventory identity, and must re-check it rather
# than trust a flag: logAction has a catch path that calls logshot() without
# ever running bpCoffeeGate.
m_lr = re.search(r'async function laneRecord\(cols\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_lr:
    fail('lane', 'laneRecord is gone -> no shot is ever filed into a lane')
else:
    if 'laneEligible(' not in m_lr.group(1):
        fail('lane', 'laneRecord does not gate on laneEligible -> a single dose or an unplaced '
                     'name starts a lane, and one bag becomes two thin histories')
    checks += 1

m_le = re.search(r'function laneEligible\(coffee\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_le:
    fail('lane', 'laneEligible is gone, so the lane gate cannot be verified')
else:
    b = m_le.group(1)
    if 'bpInInventory' not in b:
        fail('lane', 'laneEligible no longer requires inventory identity')
    if 'bpIsSingle' not in b:
        fail('lane', 'laneEligible no longer excludes single doses -> a one-off dose starts a '
                     'lane that can never gain a second shot')
    checks += 2

# A shot that never reaches laneRecord is a shot the lane store never sees, and
# the only symptom is a baseline that stops moving.
m_ls2 = re.search(r'async function logshot\(\)\s*\{', JS)
if m_ls2:
    i = m_ls2.end() - 1
    d = 0; j = i
    while j < len(JS):
        if JS[j] == '{': d += 1
        elif JS[j] == '}':
            d -= 1
            if d == 0: break
        j += 1
    if 'laneRecord(' not in JS[i:j+1]:
        fail('lane', 'logshot() never calls laneRecord -> rows reach the sheet and no lane is '
                     'ever updated')
    checks += 1

# Filing a shot must not be able to erase a note typed into the sheet by hand.
m_lu = re.search(r'async function gLaneUpsert\(lane\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_lu:
    fail('lane', 'gLaneUpsert is gone, so the note-preserving patch cannot be verified')
else:
    b = m_lu.group(1)
    if 'gPatchRow(' not in b:
        fail('lane', 'gLaneUpsert no longer patches named columns -> the row is rebuilt and every '
                     'column it does not know about is lost')
    if 'note_date' not in b:
        fail('lane', 'gLaneUpsert no longer excludes note and note_date from the patch -> filing a '
                     'shot wipes a note written by hand in the sheet')
    checks += 2

# The history cell is pipe-delimited. A grind setting typed as 3|4 would split
# the cell and shift every field after it.
m_hc = re.search(r'function laneCellSafe\(v\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_hc or not re.search(r'replace\(/\[[^\]]*\|', m_hc.group(1)):
    fail('lane', 'laneCellSafe no longer strips the pipe separator -> a value containing a pipe '
                 'splits the history cell and every field after it shifts')
checks += 1

# Five, newest first. A drifting window length changes what every baseline means.
if not re.search(r'var LANE_HIST = 5', JS):
    fail('lane', 'LANE_HIST is not 5 -> the rolling history length no longer matches the h1..h5 '
                 'columns the schema provides')
if 'hist.unshift(' not in JS:
    fail('lane', 'the history is no longer written newest first')
checks += 2

# Filter has no measured baseline. Inventing one is worse than saying so.
m_sd = re.search(r'var LANE_SEED = \{(.*?)\n      \};', JS, re.S)
if not m_sd:
    fail('lane', 'LANE_SEED is gone, so the baselines cannot be verified')
else:
    b = m_sd.group(1)
    if not re.search(r'filter:\s*null', b):
        fail('lane', 'LANE_SEED.filter is no longer null -> a filter baseline was invented and '
                     'there are no measured filter shots behind it')
    if 'espresso' not in b or 'soup' not in b:
        fail('lane', 'LANE_SEED lost a measured type')
    checks += 2

# laneBaseline has to say where its numbers came from, or the population figure
# gets mistaken for this bag's own.
m_lb = re.search(r'function laneBaseline\(coffee, type\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_lb:
    fail('lane', 'laneBaseline is gone')
else:
    b = m_lb.group(1)
    for tag in ('"lane"', '"type"', '"none"'):
        if tag not in b:
            fail('lane', 'laneBaseline no longer reports source %s -> a caller cannot tell this '
                         'bag\'s own baseline from the population figure' % tag)
    checks += 3

# The shot row is read by column NAME. An index written here is correct until a
# column moves and then silently wrong.
m_sf = re.search(r'function laneShotFromCols\(cols\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_sf:
    fail('lane', 'laneShotFromCols is gone')
elif 'COLNAMES.indexOf(' not in m_sf.group(1):
    fail('lane', 'laneShotFromCols reads the row by literal index instead of by COLNAMES name -> '
                 'appending a column silently shifts every metric it reads')
checks += 1

# ============================ 21. THE BUILT FILE IS LF
# Python text mode translates '\n' to os.linesep on write, so a build on Windows
# emits CRLF. The build stamp is a sha1 of the string still in MEMORY, which is
# LF either way, so a CRLF build prints a stamp identical to a Linux build while
# the file on disk differs in every line. The stamp is the check the whole
# verification ritual rests on, and that is exactly the case it cannot see.
if b'\r' in open(HTML, 'rb').read():
    n = open(HTML, 'rb').read().count(b'\r')
    fail('newline', 'the built file contains %d carriage returns -> this was written in text '
                    'mode on Windows. The build stamp will still match a Linux build while the '
                    'bytes do not. Rebuild with a generator that pins newline=%s' % (n, "''"))
checks += 1

# ============================ 22. PASS 3: PENDING WRITES AND THE ADVICE SURFACE
# A lane write can fail on quota, a permission change or being offline. The cache
# still advances, so without a pending mark the next reconcile overwrites it from
# the sheet and the shot vanishes from the baseline with nothing on screen.
m_lr3 = re.search(r'async function laneRecord\(cols\)\s*\{(.*?)\n      \}', JS, re.S)
if m_lr3 and not re.search(r'_pending\s*=\s*1', m_lr3.group(1)):
    fail('lane', 'laneRecord no longer marks a failed sheet write as pending -> the cache claims '
                 'the shot was filed and the next reconcile silently drops it')
checks += 1

m_ll3 = re.search(r'async function gLaneList\(\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_ll3:
    fail('lane', 'gLaneList is gone')
else:
    b = m_ll3.group(1)
    if '_pending' not in b:
        fail('lane', 'gLaneList overwrites the cache without checking for pending lanes -> a lane '
                     'ahead of the sheet loses exactly the shots it is ahead by')
    if 'gLaneFlush(' not in b:
        fail('lane', 'gLaneList no longer retries pending writes before reading')
    checks += 2

# Flow numbers cannot reach taste without TDS. Every comparison carries the
# caveat, or the tool starts making a claim it cannot support.
m_la = re.search(r'function laneAdvise\(coffee, type, shot\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_la:
    fail('lane', 'laneAdvise is gone')
else:
    b = m_la.group(1)
    if 'laneNoTaste' not in b:
        fail('lane', 'laneAdvise no longer carries the taste caveat -> it implies flow numbers '
                     'describe flavour, which they cannot without TDS')
    if '"none"' not in b:
        fail('lane', 'laneAdvise no longer handles a missing baseline separately -> filter shots '
                     'get compared against a number that does not exist')
    checks += 2

# The filing outcome must reach the screen. laneRecord runs after the row is
# saved, where nobody would look, so a silent decline reads as success.
m_ls3 = re.search(r'async function logshot\(\)\s*\{', JS)
if m_ls3:
    i = m_ls3.end() - 1
    d = 0; j = i
    while j < len(JS):
        if JS[j] == '{': d += 1
        elif JS[j] == '}':
            d -= 1
            if d == 0: break
        j += 1
    if 'laneNote(' not in JS[i:j+1]:
        fail('lane', 'logshot discards the laneRecord result -> a coffee that never starts a lane '
                     'looks exactly like one that did')
    checks += 1

if not re.search(r'INSIGHT_FNS = \[\s*insightsLane', JS):
    fail('lane', 'insightsLane is not wired into INSIGHT_FNS -> the lane store records and '
                 'nothing ever reads it')
checks += 1

# ============================ 23. PASS 4a: THE PRE-SHOT CARD
# The card must be chosen by what the lane CONTAINS, never by the hardware
# picker. M_GAG is a declared setting and a declaration can be wrong: Gaggiuino
# can be selected while the ESP reported nothing, or a shot logged from a phone
# with the machine off. Reading the flag would promise a physics read the lane
# cannot deliver.
m_rc = re.search(r'function renderLaneCard\(\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_rc:
    fail('card', 'renderLaneCard is gone -> the lane store has no pre-shot surface')
else:
    b = m_rc.group(1)
    if 'M_GAG' in b:
        fail('card', 'renderLaneCard reads M_GAG -> the card would promise a flow read based on a '
                     'hardware setting rather than on whether this lane actually has flow data')
    if 'laneCardData(' not in b:
        fail('card', 'renderLaneCard no longer builds its state through laneCardData')
    checks += 2

m_cd = re.search(r'function laneCardData\(coffee, type\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_cd:
    fail('card', 'laneCardData is gone')
else:
    b = m_cd.group(1)
    if 'physics' not in b or 'h.resistance' not in b:
        fail('card', 'laneCardData no longer derives physics from the resistance actually present '
                     'in this lane history')
    checks += 1

m_nu = re.search(r'function laneNudge\(d\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_nu:
    fail('card', 'laneNudge is gone')
elif not re.search(r'if \(!d\.physics', m_nu.group(1)):
    fail('card', 'laneNudge no longer refuses to advise without flow data -> a grind direction '
                 'derived from nothing would read as a measurement')
checks += 1

# Both fields gate the card, so either one changing last has to redraw it.
for fn in ('updateCoffeeHint', 'renderLogForm'):
    m = re.search(r'function ' + fn + r'\(\)\s*\{(.{0,400})', JS, re.S)
    if not m or 'renderLaneCard()' not in m.group(1):
        fail('card', '%s does not redraw the lane card -> the card goes stale whenever that field '
                     'is the one that changed last' % fn)
    checks += 1

# Lane values are user text. A coffee name or grind setting can be anything.
m_ln = re.search(r'function laneLine\(el, txt, dim\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_ln or 'textContent' not in m_ln.group(1) or 'innerHTML' in m_ln.group(1):
    fail('card', 'laneLine no longer writes lane values as text -> a coffee name is user input and '
                 'would become markup')
checks += 1

# ============================ 24. PASS 4b: THE ROTATION CHIP
# Both manual add paths do ROT.push({ coffee: n }), so a rotation entry carries
# ONLY a name until a shot is logged with it. Filling the form from the entry
# alone left every other field blank. Inventory is the source of truth for what a
# coffee IS, and copying those fields onto the entry instead would have gone
# stale the moment the bag was corrected in the sheet.
m_fe = re.search(r'function fillEntry\(e\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_fe:
    fail('rotation', 'fillEntry is gone')
else:
    b = m_fe.group(1)
    if 'coffeeIdentity(' not in b:
        fail('rotation', 'fillEntry no longer resolves the coffee identity -> a chip added from '
                         'the picker carries only a name and fills nothing else')
    if re.search(r'getElementById\("(varietal|roast)"\)\.value\s*=', b):
        fail('rotation', 'fillEntry assigns straight to the varietal or roast SELECT -> a value '
                         'with no matching option is silently dropped')
    checks += 2

# A select ignores an assignment to a value it has no option for. Inventory can
# hold a varietal that is not in the built-in list.
m_sa = re.search(r'function setSelAny\(id, val\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_sa:
    fail('rotation', 'setSelAny is gone')
elif 'createElement("option")' not in m_sa.group(1):
    fail('rotation', 'setSelAny no longer appends an unknown value as an option -> a varietal '
                     'outside the built-in list vanishes with no error')
checks += 1

m_ir = re.search(r'function invRowByName\(name\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_ir:
    fail('rotation', 'invRowByName is gone')
elif not (re.search(r'var k = bpNorm\(name\)', m_ir.group(1))
          and re.search(r'bpNorm\(rows\[i\]\.coffee\)', m_ir.group(1))):
    fail('rotation', 'invRowByName does not normalise BOTH sides of the comparison -> casing or '
                     'punctuation splits one bag into two identities')
checks += 1

# The identity lookup must consult BOTH sources. A coffee can have logged shots
# and no Inventory row at all, and those shots carry the same identity columns,
# so Inventory alone would leave a brewed coffee presenting an empty form.
m_ci = re.search(r'function coffeeIdentity\(name\)\s*\{(.*?)\n      \};\n      \}', JS, re.S)
if not m_ci:
    m_ci = re.search(r'function coffeeIdentity\(name\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_ci:
    fail('rotation', 'coffeeIdentity is gone')
else:
    b = m_ci.group(1)
    if 'invRowByName(' not in b:
        fail('rotation', 'coffeeIdentity no longer consults Inventory')
    if 'lastShotByName(' not in b:
        fail('rotation', 'coffeeIdentity no longer falls back to logged shots -> a coffee with '
                         'history but no Inventory row fills nothing')
    checks += 2

m_ls4 = re.search(r'function lastShotByName\(name\)\s*\{(.*?)\n      \}', JS, re.S)
if not m_ls4:
    fail('rotation', 'lastShotByName is gone')
elif 'rows.length - 1' not in m_ls4.group(1):
    fail('rotation', 'lastShotByName no longer scans newest first -> an old shot overrides a '
                     'later correction')
checks += 2

# ---------------------------------------------------------------- report
print()
print('  audit of %s' % os.path.basename(HTML))
print('  audit.py %s  (%d invariants checked)' % (AUDIT_VERSION, checks))
print()
if warns:
    for c, m in warns:
        print('  WARN  [%s] %s' % (c, m))
    print()
if fails:
    for c, m in fails:
        print('  FAIL  [%s] %s' % (c, m))
    print()
    print('  %d FAILURE(S). Do not publish.' % len(fails))
    sys.exit(1)
print('  ALL CLEAR')
sys.exit(0)
