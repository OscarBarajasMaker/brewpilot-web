#!/usr/bin/env python3
# BrewPilot webapp build.
#
#   src_v5.html   markup for the five tab panels + the core <script>   (editable)
#   build_v5.py   shell, theme tokens, CSS, i18n + feature JS, pipeline (editable)
#
# Emits index_v5.html (prettified webapp) and panel_v5.h (compact firmware string).
#
# Reconstructed 2026-07-24 from the live site, build 2026-07-23-2112-35d874,
# after the previous generator was lost to a wiped sandbox. Acceptance test was
# byte equality against that live file. See RECONSTRUCTION NOTES at the bottom.
import re, subprocess, tempfile, os, hashlib, datetime, shutil

HERE  = os.path.dirname(os.path.abspath(__file__)) or '.'
SRC   = os.path.join(HERE, 'src_v5.html')
OUT   = os.path.join(HERE, 'index_v5.html')
PANEL = os.path.join(HERE, 'panel_v5.h')

# Kill the outputs first. A build that aborts halfway used to leave the PREVIOUS
# index_v5.html sitting there, and it would sail through the audit while the
# actual change never shipped. Now an aborted build leaves nothing to audit.
for _f in (OUT, PANEL):
    try: os.unlink(_f)
    except OSError: pass

# ---------------------------------------------------------------------------
# must_replace: a replace that cannot silently do nothing.
# Kept from the original generator. The historical patch list is empty now
# (every migration it carried is baked into the source), but any NEW edit
# should go through it rather than a bare .replace().
_LANDED = []

def must_replace(text, old, new, what, count=1):
    n = text.count(old)
    if n == 0:
        raise SystemExit(
            "\n  BUILD ABORTED: %s\n"
            "  Pattern not found, so this replace would have silently done nothing:\n"
            "    %r\n"
            "  Check the BUILT file, not the source: prettier normalises quotes\n"
            "  and spacing, so patterns copied from either side can miss.\n" % (what, old[:110]))
    if count and n != count:
        raise SystemExit("\n  BUILD ABORTED: %s\n  Expected %d occurrence(s), found %d.\n" % (what, count, n))
    _LANDED.append((what, old, new))
    return text.replace(old, new)

def must_ship(assembled):
    """must_replace proves a pattern EXISTED. This proves the edit still SHIPPED.
    ASSEMBLED is pre-prettier, so exact match is valid here. Do not move this
    below the prettier call."""
    ghosts = []
    for what, old, new in _LANDED:
        wrapping = bool(old) and bool(new) and (old in new)
        if old and not wrapping and old in assembled:
            ghosts.append((what, 'the OLD text is still in the shipped page')); continue
        probe = (new or '').strip()[:80]
        if probe and probe not in assembled:
            ghosts.append((what, 'the NEW text never reached the shipped page'))
    if ghosts:
        print("\n  BUILD ABORTED: %d replace(s) reported success but did not ship." % len(ghosts))
        for what, why in ghosts: print("    %-42s %s" % (what, why))
        raise SystemExit(1)
    print("must_ship: %d replace(s) verified in the assembled page" % len(_LANDED))

def cut(s, a):
    """Split at the newline BEFORE anchor a, so every piece starts on a line boundary."""
    i = s.find(a)
    if i == -1:      raise SystemExit('BUILD ABORTED: missing cut anchor ' + a[:60])
    if s.count(a)!=1: raise SystemExit('BUILD ABORTED: ambiguous cut anchor ' + a[:60])
    j = s.rfind('\n', 0, i)
    return s[:j], s[j:]

# ---------- the single editable markup input ----------
# index_v5.html cannot be fed back in: it is post-prettier and carries the
# shell blobs below, so a rebuild from the built file would double them.
html   = open(SRC, encoding='utf-8').read()
body   = re.search(r'<body>(.*?)<script>', html, re.S).group(1)
script = re.search(r'<script>(.*)</script>', html, re.S).group(1)


# ---------- theme tokens ----------
BASE = ['bg', 'panel', 'panel2', 'line', 'line2', 'text', 'dim', 'pressure', 'flow', 'temp', 'weight', 'warn', 'sel-bg', 'sel-line', 'sel-text', 'hi-bg', 'hi-line', 'hi-text', 'danger-bg', 'danger-line', 'danger-text', 'rec-bg', 'rec-line', 'rec-text']
THEMES = {
  'ristretto': ['#13161a', '#1b1f24', '#242a31', '#2f3742', '#3e4753', '#e8ecf1', '#98a2ad', '#e8833a', '#4ca5e8', '#e5484d', '#3fb950', '#e3b341', '#16233a', '#4a7fb5', '#8fc4ff', '#14241c', '#2f6f4f', '#8fdcb0', '#241618', '#6f3a3e', '#ff9a9a', '#1a1522', '#3a2f4a', '#c8a2ff'],
  'cortado'  : ['#f3ede3', '#ffffff', '#ede6da', '#dad0c2', '#c8bcaa', '#2a2019', '#6e6355', '#c2601f', '#1668c4', '#c93c41', '#2a9d45', '#b8860b', '#f3e6d5', '#c2601f', '#9a4a16', '#e7f6ec', '#2a9d45', '#1e7a34', '#fbe7e7', '#c93c41', '#b23138', '#f1eaf6', '#8a6dbf', '#6b44b0'],
  'coldbrew' : ['#0c0f12', '#131820', '#1b222c', '#29323f', '#3a4553', '#e8eef4', '#8f9aa8', '#e8873a', '#4ca5e8', '#e5484d', '#3fb950', '#e3b341', '#0e2233', '#2e6c9e', '#7fc4f5', '#0e2418', '#2f7a4f', '#7fdca8', '#241214', '#6f3438', '#ff9a9a', '#141024', '#3a2f5a', '#b9a2f5'],
}
DEFAULT_THEME = 'ristretto'   # the one that owns :root

def theme_css(name, vals):
    sel = ':root' if name == DEFAULT_THEME else '[data-theme="%s"]' % name
    return sel + '{' + ''.join('--%s:%s;' % (k, v) for k, v in zip(BASE, vals)) + '}'

THEME_CSS = '\n'.join(theme_css(n, v) for n, v in THEMES.items())

# ---------- stylesheet body (everything after the theme blocks) ----------
CSS_REST = r'''
      * {
        box-sizing: border-box;
      }
      body {
        margin: 0 auto;
        max-width: 520px;
        padding: 0;
        min-height: 100vh;
        min-height: 100dvh;
        display: flex;
        flex-direction: column;
        font-family:
          "Inter",
          -apple-system,
          system-ui,
          sans-serif;
        background: var(--bg);
        color: var(--text);
      }
      h1 {
        display: none;
      }
      .appbar {
        position: sticky;
        top: 0;
        z-index: 20;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: calc(14px + env(safe-area-inset-top)) 16px 10px;
        background: var(--bg);
        border-bottom: 1px solid var(--line);
      }
      .brand {
        font-weight: 800;
        font-size: 18px;
      }
      .brand span {
        color: var(--pressure);
      }
      .themebtns {
        display: flex;
        gap: 6px;
      }
      .tdot {
        width: 16px;
        height: 16px;
        border-radius: 50%;
        border: 1px solid var(--line);
        cursor: pointer;
      }
      .tdot.on {
        outline: 2px solid var(--pressure);
        outline-offset: 1px;
      }
      .wrap {
        padding: 14px 16px 0;
        flex: 1 0 auto;
      }
      .tabpanel {
        display: none;
      }
      .tabpanel.on {
        display: block;
      }
      .hero {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 16px;
        margin-bottom: 14px;
      }
      .herotop {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
      }
      .herophase {
        font-size: 12px;
        letter-spacing: 0.06em;
        color: var(--dim);
        text-transform: uppercase;
      }
      .heronum {
        font-family: "JetBrains Mono", monospace;
        font-size: 30px;
        font-weight: 600;
      }
      .herosub {
        color: var(--dim);
        font-size: 12px;
        margin-top: 2px;
      }
      .spark {
        display: flex;
        align-items: flex-end;
        gap: 5px;
        height: 60px;
        margin-top: 14px;
      }
      .spark i {
        flex: 1;
        border-radius: 2px 2px 0 0;
        display: block;
        background: var(--pressure);
      }
      .sparkcap {
        display: flex;
        justify-content: space-between;
        font-size: 10px;
        color: var(--dim);
        margin-top: 6px;
        font-family: "JetBrains Mono", monospace;
      }
      .tabbar {
        position: sticky;
        bottom: 0;
        width: 100%;
        flex: 0 0 auto;
        z-index: 20;
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        padding: 4px 0 max(4px, env(safe-area-inset-bottom));
        background: var(--bg);
        border-top: 1px solid var(--line);
      }
      .tab {
        text-align: center;
        cursor: pointer;
        color: var(--dim);
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.05em;
        padding: 7px 4px 2px;
        border-radius: 12px;
      }
      .tab .ic {
        font-size: 20px;
        line-height: 1;
        margin-bottom: 2px;
      }
      .tab.on {
        color: var(--pressure);
      }
      /* restored from the original stylesheet, tokenized. dropping these was a bug:
   button lost color/border/padding, so browsers fell back to system blue text. */
      #state {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 14px;
        margin-bottom: 16px;
        font-size: 15px;
        line-height: 1.7;
        color: var(--text);
      }
      .dot {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 7px;
        vertical-align: middle;
      }
      .row {
        display: flex;
        gap: 10px;
        margin-bottom: 10px;
      }
      button {
        flex: 1;
        padding: 16px;
        font-size: 16px;
        font-weight: 600;
        border: 0;
        border-radius: 12px;
        color: #fff;
        background: var(--flow);
        font-family:
          "Inter",
          -apple-system,
          system-ui,
          sans-serif;
        cursor: pointer;
        -webkit-appearance: none;
        appearance: none;
      }
      button:active {
        opacity: 0.7;
      }
      .warm {
        background: var(--pressure);
      }
      .off {
        background: var(--panel2);
      }
      .grn {
        background: var(--weight);
      }
      /* iOS Safari applies its own native rendering to form controls and ignores
   `color`, which is what made the grinder select render gold instead of white.
   -webkit-text-fill-color is the property it actually honours. Same class of bug
   as the buttons rendering system-blue before appearance was reset. Cannot be
   reproduced in headless Chromium, which computes the correct colour. */
      select {
        flex: 2;
        padding: 15px;
        font-size: 16px;
        border-radius: 12px;
        border: 1px solid var(--line);
        background: var(--panel);
        color: var(--text);
        -webkit-text-fill-color: var(--text);
        opacity: 1;
      }
      select option {
        color: var(--text);
        background: var(--panel);
        -webkit-text-fill-color: var(--text);
      }
      input,
      textarea {
        -webkit-text-fill-color: var(--text);
        opacity: 1;
      }
      input::placeholder,
      textarea::placeholder {
        color: var(--dim);
        -webkit-text-fill-color: var(--dim);
        opacity: 1;
      }
      /* Safari tints autofilled fields yellow and ignores background; this holds the theme */
      input:-webkit-autofill,
      select:-webkit-autofill {
        -webkit-text-fill-color: var(--text);
        box-shadow: 0 0 0 1000px var(--panel) inset;
      }
      label {
        color: var(--dim);
        font-size: 13px;
        display: block;
        margin: 14px 0 6px;
      }
      .mut {
        color: var(--dim);
        font-size: 12px;
        text-align: center;
        margin-top: 14px;
      }
      .fl {
        color: var(--dim);
        font-size: 11px;
        margin: 0 0 3px 2px;
      }
      .fin {
        width: 100%;
        min-width: 0;
        max-width: 100%;
        box-sizing: border-box;
        padding: 12px;
        font-size: 15px;
        border-radius: 10px;
        border: 1px solid var(--line);
        background: var(--panel);
        color: var(--text);
        margin-bottom: 8px;
      }
      /* Defensive box sizing. NOTE: min-width:0 was measured to make no difference
   in Chromium; width:100% already lets these shrink. It is kept as standard
   flex hygiene, not as the fix for the iOS overlap.
   The actual iOS lever is -webkit-appearance: iOS gives date inputs a native
   intrinsic size that ignores width:100% (same family as the select colour
   bug and the system-blue buttons). Cannot be reproduced headless. */
      input,
      select,
      textarea,
      button {
        min-width: 0;
        max-width: 100%;
        box-sizing: border-box;
      }
      input[type="date"] {
        -webkit-appearance: none;
        appearance: none;
        width: 100%;
        min-width: 0;
      }
      input[type="date"]::-webkit-date-and-time-value {
        text-align: left;
        margin: 0;
      }
      input[type="date"]::-webkit-calendar-picker-indicator {
        margin-left: 2px;
      }
      /* a cell that must own its line */
      .fcell.fullrow {
        flex: 1 1 100%;
      }
      .frow {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .fcell {
        flex: 1 1 90px;
        min-width: 0;
      }
      input {
        background: var(--panel);
        border: 1px solid var(--line);
        color: var(--text);
      }
      input[type="number"] {
        font-family: "JetBrains Mono", monospace;
      }
      .sub {
        color: var(--dim);
      }

      .chip {
        display: inline-block;
        padding: 8px 12px;
        border-radius: 18px;
        font-size: 13px;
        cursor: pointer;
        border: 1px solid var(--line);
        background: var(--panel);
        color: var(--text);
      }
      .chip.on {
        border-color: var(--sel-line);
        background: var(--sel-bg);
        color: var(--sel-text);
      }
      .chip.sm {
        padding: 7px 11px;
        border-radius: 16px;
        font-size: 12px;
      }
      .chip.xs {
        padding: 6px 10px;
        border-radius: 15px;
        font-size: 11px;
      }
      .chip.hi {
        border-color: var(--hi-line);
        background: var(--hi-bg);
      }
      .chip.hi.on {
        color: var(--hi-text);
      }
      .chip.rec {
        border-color: var(--rec-line);
        background: var(--rec-bg);
        color: var(--rec-text);
      }

      .rightbar {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .langtoggle {
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 4px 9px;
        font-size: 11px;
        font-weight: 700;
        color: var(--dim);
        cursor: pointer;
      }
      body.role-logmgr #machineOnly,
      body.role-logmgr #tierCard {
        display: none !important;
      }
      .tool {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 13px 14px;
        margin-bottom: 12px;
      }
      .toolhd {
        font-size: 13px;
        font-weight: 700;
        margin-bottom: 8px;
      }
      .convrow {
        display: flex;
        gap: 8px;
        align-items: flex-end;
        flex-wrap: wrap;
      }
      .convcell {
        flex: 1 1 90px;
        min-width: 0;
      }
      .convout {
        margin-top: 10px;
        font-family: "JetBrains Mono", monospace;
        font-size: 15px;
        color: var(--hi-text);
      }
      .rolerow {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
        margin-bottom: 6px;
      }
      .wizmask {
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.6);
        z-index: 40;
        display: none;
        align-items: flex-end;
        justify-content: center;
      }
      .wizmask.on {
        display: flex;
      }
      .wizcard {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 16px 16px 0 0;
        width: 100%;
        max-width: 520px;
        padding: 18px 18px 26px;
        max-height: 88vh;
        overflow: auto;
      }
      .wiztitle {
        font-size: 16px;
        font-weight: 800;
        margin-bottom: 4px;
      }
      .wizstep {
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 12px;
        margin-top: 10px;
        font-size: 13px;
        line-height: 1.5;
      }
      .wizn {
        display: inline-block;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        background: var(--pressure);
        color: #0b0e12;
        font-weight: 800;
        font-size: 12px;
        text-align: center;
        line-height: 20px;
        margin-right: 8px;
      }
      .wizok {
        color: var(--hi-text);
      }
      .dura {
        border: 1px solid var(--warn);
        background: var(--panel);
        border-radius: 12px;
        padding: 12px 13px;
        margin-bottom: 12px;
      }
      .durahd {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 13.5px;
      }
      .durabolt {
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: var(--warn);
        color: #0b0e12;
        font-weight: 800;
        font-size: 12px;
        text-align: center;
        line-height: 18px;
        flex: none;
      }
      .durab {
        font-size: 12px;
        color: var(--dim);
        line-height: 1.55;
        margin-top: 7px;
      }
      .durarow {
        display: flex;
        gap: 8px;
        margin-top: 10px;
        flex-wrap: wrap;
      }
      .durabtn {
        flex: 1 1 150px;
        border: none;
        border-radius: 9px;
        padding: 11px;
        font-weight: 700;
        font-size: 13px;
        cursor: pointer;
        color: #0b0e12;
      }
      .durabtn2 {
        flex: 0 0 auto;
        background: transparent;
        border: 1px solid var(--line);
        color: var(--dim);
        border-radius: 9px;
        padding: 11px 13px;
        font-size: 12.5px;
        cursor: pointer;
      }
      .duracount {
        font-size: 11px;
        color: var(--warn);
        margin-top: 8px;
        font-family: "JetBrains Mono", monospace;
      }
      .durasafe {
        border-color: var(--hi-line);
      }
      .durasafe .durabolt {
        background: var(--weight);
      }
      #hwMask.on {
        display: flex;
      }
      .hwT {
        font-size: 16px;
        font-weight: 700;
        color: var(--text);
        margin-bottom: 8px;
        line-height: 1.35;
      }
      .hwB {
        font-size: 13px;
        color: var(--dim);
        line-height: 1.6;
      }
      .hwGH {
        font-size: 12px;
        font-weight: 700;
        color: var(--dim);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin: 14px 0 6px;
      }
      .hwGHlink {
        color: var(--sel-text);
        cursor: pointer;
      }
      .hwList {
        display: flex;
        flex-direction: column;
        gap: 5px;
      }
      .hwLi {
        display: flex;
        gap: 8px;
        font-size: 13px;
        color: var(--text);
        line-height: 1.5;
      }
      .hwDot {
        color: var(--pressure);
        font-weight: 900;
        flex: 0 0 auto;
      }
      .hwOk {
        font-size: 12.5px;
        color: var(--text);
        background: var(--panel2);
        border: 1px solid var(--line);
        border-left: 3px solid var(--pressure);
        border-radius: 0 9px 9px 0;
        padding: 10px 12px;
        margin-top: 12px;
        line-height: 1.55;
      }
      .helpq {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 17px;
        height: 17px;
        margin-left: 6px;
        border: 1px solid var(--line);
        border-radius: 50%;
        color: var(--dim);
        font-size: 11px;
        font-weight: 700;
        cursor: pointer;
        vertical-align: middle;
        -webkit-tap-highlight-color: transparent;
      }
      .helpq.on {
        border-color: var(--sel-line);
        color: var(--sel-text);
        background: var(--sel-bg);
      }
      .helpbox {
        background: var(--panel2);
        border: 1px solid var(--sel-line);
        border-left: 3px solid var(--sel-line);
        border-radius: 8px;
        padding: 9px 11px;
        margin: 7px 0;
        font-size: 12px;
        line-height: 1.55;
        color: var(--dim);
        font-weight: 400;
      }
      .csbad {
        border-color: var(--warn);
      }
      .cswarn {
        color: var(--warn);
        font-size: 11.5px;
        margin-top: 7px;
        line-height: 1.5;
      }
      .inst {
        border: 1px solid var(--sel-line);
        background: var(--panel);
        border-radius: 12px;
        padding: 12px 13px;
        margin-bottom: 12px;
      }
      .instrow {
        display: flex;
        align-items: center;
        gap: 11px;
      }
      .instico {
        width: 40px;
        height: 40px;
        border-radius: 9px;
        flex: none;
      }
      .instmeta {
        flex: 1;
        min-width: 0;
      }
      .insttitle {
        font-size: 13.5px;
        font-weight: 700;
        line-height: 1.3;
      }
      .instsub {
        font-size: 11.5px;
        color: var(--dim);
        margin-top: 3px;
        line-height: 1.45;
      }
      .instx {
        flex: none;
        width: 28px;
        height: 28px;
        padding: 0;
        border: 0;
        border-radius: 50%;
        background: transparent;
        color: var(--dim);
        font-size: 20px;
        line-height: 1;
        cursor: pointer;
      }
      .instbtn {
        width: 100%;
        margin-top: 11px;
        padding: 12px;
        font-size: 14px;
      }
      .instios {
        margin-top: 10px;
        display: flex;
        flex-direction: column;
        gap: 7px;
      }
      .iosrow {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12.5px;
        color: var(--dim);
      }
      .iosn {
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: var(--sel-line);
        color: var(--text);
        font-size: 11px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        flex: none;
      }
      .iosglyph {
        color: var(--sel-text);
        font-weight: 700;
      }
      [data-theme="cortado"] button {
        color: #ffffff;
      }
      [data-theme="cortado"] .off {
        color: var(--text);
      }
      .off {
        color: var(--text);
      }
      .inslock {
        border: 1px solid var(--warn);
        background: var(--panel);
        border-radius: 12px;
        padding: 16px;
        text-align: left;
      }
      .inslockT {
        font-size: 14px;
        font-weight: 700;
        margin-bottom: 6px;
      }
      .inslockB {
        font-size: 12.5px;
        color: var(--dim);
        line-height: 1.55;
      }
      .cs {
        border: 1px solid var(--line);
        background: var(--panel2);
        border-radius: 10px;
        padding: 10px 12px;
        margin: 8px 0;
      }
      .csHd {
        font-size: 11px;
        letter-spacing: 0.06em;
        color: var(--dim);
        text-transform: uppercase;
      }
      .csV {
        font-family: "JetBrains Mono", monospace;
        font-size: 18px;
        font-weight: 600;
        color: var(--hi-text);
        margin-top: 4px;
      }
      .csS {
        font-size: 11.5px;
        color: var(--dim);
        margin-top: 4px;
        line-height: 1.5;
      }
      .wsub {
        font-size: 12.5px;
        color: var(--dim);
        line-height: 1.55;
        margin: 6px 0 0 28px;
      }
      .kbd {
        background: var(--panel2);
        border: 1px solid var(--line);
        border-radius: 5px;
        padding: 1px 6px;
        color: var(--text);
        font-size: 12px;
        white-space: nowrap;
      }
      .wizbtn {
        display: inline-block;
        margin: 8px 0 0 28px;
        background: var(--sel-bg);
        border: 1px solid var(--sel-line);
        color: var(--sel-text);
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 13px;
        font-weight: 600;
        text-decoration: none;
      }
      .wizwarn {
        border-color: var(--warn);
      }
      .wizn2 {
        background: var(--warn);
      }
      .wshot {
        display: block;
        width: calc(100% - 28px);
        margin: 10px 0 0 28px;
        border: 1px solid var(--line);
        border-radius: 8px;
      }
      .wizerr {
        color: var(--danger-text);
      }
      .logmoderow {
        display: flex;
        gap: 8px;
        margin: 0 0 12px;
      }
      .logmoderow button {
        flex: 1;
        padding: 11px 8px;
        border-radius: 10px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
      }
      .csfacs {
        margin-top: 6px;
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
      }
      .csfac {
        font-size: 11px;
        padding: 3px 8px;
        border-radius: 7px;
        background: var(--panel);
        border: 1px solid var(--line);
        color: var(--dim);
      }
      .csfacbig {
        color: var(--sel-text);
        border-color: var(--sel-line);
        font-weight: 600;
      }
      .sheetlink {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        width: 100%;
        padding: 11px 12px;
        border-radius: 10px;
        border: 1px solid var(--line);
        background: var(--panel);
        color: var(--dim);
        font-size: 13px;
        font-weight: 500;
        text-decoration: none;
        box-sizing: border-box;
        cursor: pointer;
      }
      .ratechips {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 6px;
        margin: 2px 0 6px;
      }
      .ratechip {
        min-width: 0;
        min-height: 46px;
        padding: 0;
        border-radius: 9px;
        font:
          600 16px/1 ui-monospace,
          monospace;
        cursor: pointer;
        -webkit-tap-highlight-color: transparent;
        touch-action: manipulation;
      }
      .ratewordlbl {
        font-size: 12px;
        color: var(--dim);
        min-height: 16px;
        margin-bottom: 6px;
      }
      .planbox {
        margin: 0 0 12px;
      }
    '''
CSS = THEME_CSS + CSS_REST

# ---------- shell blobs (verbatim; edit in place) ----------
HEAD = r'''<!doctype html>
<html lang="es" data-theme="ristretto">
  <head>
    <meta charset="utf-8" />
    <script>
      try {
        var _t = localStorage.getItem("theme");
        if (_t) document.documentElement.setAttribute("data-theme", _t);
      } catch (e) {}
    </script>
    <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover" />
    <script src="https://accounts.google.com/gsi/client" async defer></script>
    <script src="client-id.js"></script>
    <meta name="apple-mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
    <meta name="apple-mobile-web-app-title" content="BrewPilot" />
    <meta name="theme-color" content="#0E1116" />
    <link rel="manifest" href="manifest.json" />
    <link rel="apple-touch-icon" href="apple-touch-icon.png" />
    <link rel="icon" type="image/png" sizes="192x192" href="icon-192.png" />
    <title>BrewPilot</title>
    <style>'''
SHELL_OPEN = r'''</style>
  </head>
  <body>
    '''
APPBAR_H = r'''<div class="appbar">
      <div class="brand notranslate" translate="no">Brew<span>Pilot</span></div>
      <div class="rightbar">
        <div class="langtoggle" id="langBtn" onclick="setLang(LANG === 'es' ? 'en' : 'es')">ES</div>
        <div class="themebtns">
          <div
            class="tdot on"
            data-t="ristretto"
            style="background: #13161a"
            onclick="setTheme('ristretto')"
          ></div>
          <div
            class="tdot"
            data-t="coldbrew"
            style="background: #0c0f12"
            onclick="setTheme('coldbrew')"
          ></div>
          <div
            class="tdot"
            data-t="cortado"
            style="background: #f3ede3"
            onclick="setTheme('cortado')"
          ></div>
        </div>
      </div>
    </div>
    '''
WRAP_DURA = r'''<div class="wrap">
      <div class="dura" id="duraBanner" style="display: none">
        <div class="durahd">
          <span class="durabolt">!</span
          ><b data-i18n="duraT">Your brews are only in this browser</b>
        </div>
        <div class="durab" data-i18n="duraB">
          Nothing is backed up. Clearing your browser data, or leaving the site unused for about a
          week on iPhone, can erase it. Connect a Google Sheet (5 min, one time) to keep your
          history for good and get better insights.
        </div>
        <div class="durarow">
          <button
            class="grn durabtn"
            onclick="document.getElementById('wizMask').classList.add('on')"
            data-i18n="duraGo"
          >
            Save to Google Drive</button
          ><button class="durabtn2" onclick="exportLocal()" data-i18n="duraExp">
            Export backup
          </button>
        </div>
        <div class="duracount" id="duraCount"></div>
      </div>
      '''
TABHOME_O = r'''<div class="tabpanel on" id="tab-home">
        '''
INSTALL_H = r'''<div class="inst" id="instCard" style="display: none">
          <div class="instrow">
            <img class="instico" src="icon-192.png" alt="" />
            <div class="instmeta">
              <div class="insttitle" data-i18n="instT">Add BrewPilot to your home screen</div>
              <div class="instsub" id="instSub" data-i18n="instB">
                Opens like an app, full screen, and keeps your data safer.
              </div>
            </div>
            <button class="instx" id="instX" aria-label="close">&times;</button>
          </div>
          <button class="grn instbtn" id="instBtn" style="display: none" data-i18n="instGo">
            Install
          </button>
          <div class="instios" id="instIos" style="display: none">
            <div class="iosrow">
              <span class="iosn">1</span><span data-i18n="ios1">Tap the Share button below</span>
              <span class="iosglyph">&#x2191;</span>
            </div>
            <div class="iosrow">
              <span class="iosn">2</span
              ><span data-i18n="ios2">Scroll and tap Add to Home Screen</span>
            </div>
          </div>
        </div>
        '''
HERO_H = r'''<div class="hero">
          <div class="herotop">
            <div>
              <div class="herophase" id="heroPhase">Ready to log</div>
              <div class="herosub" id="heroSub">your coffee companion</div>
            </div>
            <div class="heronum" id="heroNum">--</div>
          </div>
          <div class="spark" id="heroSpark"></div>
          <div class="sparkcap">
            <span data-i18n="recentShots">recent shots</span><span data-i18n="rating">rating</span>
          </div>
        </div>'''
SEP_LOG = r'''
      </div>
      <div class="tabpanel" id="tab-log">
        <div id="logModeRow" class="logmoderow">
          <button
            data-mode="before"
            class="off"
            onclick="setLogMode('before')"
            data-i18n="logModeBefore"
          >
            About to brew</button
          ><button
            data-mode="after"
            class="on"
            onclick="setLogMode('after')"
            data-i18n="logModeAfter"
          >
            Already brewed
          </button>
        </div>
        <div id="logMethodRow" class="logmoderow"></div>
        <div id="gagForm">'''
SEP_BEANS = r'''
        </div>
      </div>
      <div class="tabpanel" id="tab-beans">'''
SEP_GRIND = r'''
      </div>
      <div class="tabpanel" id="tab-grind">'''
SEP_INS = r'''
      </div>
      <div class="tabpanel" id="tab-insights">'''
TAIL_HTML = r'''
      </div>
    </div>
    <div class="tabbar">
      <div class="tab on" data-tab="home" onclick="showTab('home')">
        <div class="ic">◉</div>
        <span data-i18n="home">HOME</span>
      </div>
      <div class="tab" data-tab="log" onclick="showTab('log')">
        <div class="ic">+</div>
        <span data-i18n="log">LOG</span>
      </div>
      <div class="tab" data-tab="beans" onclick="showTab('beans')">
        <div class="ic">▢</div>
        <span data-i18n="beans">BEANS</span>
      </div>
      <div class="tab" data-tab="grind" onclick="showTab('grind')">
        <div class="ic">⚙</div>
        <span data-i18n="grindTab">GRIND</span>
      </div>
      <div class="tab" data-tab="insights" onclick="showTab('insights')">
        <div class="ic">◎</div>
        <span data-i18n="insights">INSIGHTS</span>
      </div>
    </div>
    <div class="wizmask" id="wizMask">
      <div class="wizcard">
        <div class="wiztitle" data-i18n="wizSetupTitle">Set up BrewPilot</div>
        <div class="mut" style="text-align: left" data-i18n="wizSetupIntro">
          Pick what you do. Everything works right away. Save to Google Drive when you want it kept.
        </div>
        <div class="wizstep">
          <span class="wizn">1</span><b data-i18n="wizWhat">What do you want to do?</b>
          <div class="rolerow" id="wizRole" style="margin-top: 8px"></div>
          <div id="wizMethodWrap">
            <div class="fl" style="margin-top: 10px" data-i18n="wizMethods">What do you brew?</div>
            <div class="rolerow" id="wizMethods"></div>
            <div class="fl" style="margin-top: 10px" data-i18n="wizHw">What gear do you have?</div>
            <div class="rolerow" id="wizHw"></div>
            <div class="fl" style="margin-top: 10px" data-i18n="wizGrinders">
              Which grinders do you own?
            </div>
            <div class="rolerow" id="wizGrinders" style="max-height: 132px; overflow: auto"></div>
            <div class="cswarn" id="wizEspNote" style="display: none"></div>
          </div>
        </div>
        <div class="wiztitle" data-i18n="setupSheet">Save my brews to Google Drive</div>
        <div class="mut" style="text-align: left" data-i18n="wizIntro">
          Everything already works. Do this when you want your history kept and synced across
          devices.
        </div>
        <div class="wizstep" id="wizDriveStep">
          <span class="wizn">2</span><b data-i18n="wizDriveT">One tap, and the sheet is yours</b>
          <div class="wsub" data-i18n="wizDriveB">
            BrewPilot creates a spreadsheet in your own Drive and writes your brews to it. Nothing
            to copy, no scripts to deploy, no URL to paste. You can open it any time; it is a normal
            sheet that belongs to you.
          </div>
          <button
            class="grn"
            style="width: 100%; margin-top: 10px"
            onclick="goConnectSheet()"
            data-i18n="wizDriveGo"
          >
            Save my brews to Google Drive
          </button>
          <div id="wizMsg" style="font-size: 12px; margin-top: 8px"></div>
        </div>
        <button
          class="off"
          style="width: 100%; margin-top: 12px"
          onclick="document.getElementById('wizMask').classList.remove('on')"
          data-i18n="close"
        >
          Close
        </button>
      </div>
    </div>
    <script>'''
SHELL_JS = r'''
      function setTheme(t) {
        document.documentElement.setAttribute("data-theme", t);
        try {
          localStorage.setItem("theme", t);
        } catch (e) {}
        document.querySelectorAll(".tdot").forEach(function (d) {
          d.classList.toggle("on", d.dataset.t === t);
        });
      }
      function showTab(name) {
        document.querySelectorAll(".tabpanel").forEach(function (p) {
          p.classList.toggle("on", p.id === "tab-" + name);
        });
        document.querySelectorAll(".tab").forEach(function (t) {
          t.classList.toggle("on", t.dataset.tab === name);
        });
        if (name === "beans") openPanel("invPanel", toggleInv);
        if (name === "insights") openPanel("insPanel", toggleInsights);
        if (name === "grind")
          try {
            grindHelperInit();
          } catch (e) {}
        window.scrollTo(0, 0);
      }
      function openPanel(id, fn) {
        var p = document.getElementById(id);
        if (p && p.style.display === "none") fn();
      }
      function renderHero() {
        var box = document.getElementById("heroSpark");
        if (!box) return;
        var ratings = [];
        (typeof IROWS !== "undefined" ? IROWS : []).forEach(function (o) {
          var r = parseFloat(o.rating);
          if (!isNaN(r) && r > 0) ratings.push(r);
        });
        ratings.reverse();
        var _htot = ratings.length;
        ratings = ratings.slice(0, 8);
        var num = document.getElementById("heroNum"),
          phase = document.getElementById("heroPhase"),
          sub = document.getElementById("heroSub");
        if (!ratings.length) {
          num.textContent = "--";
          box.innerHTML = "";
          phase.textContent = t("noShots");
          sub.textContent = t("logToBegin");
          return;
        }
        num.textContent = ratings[0];
        phase.textContent = t("lastRating");
        sub.textContent = _htot + " " + (LANG === "es" ? "registrados" : "logged");
        var cs = getComputedStyle(document.documentElement),
          w = cs.getPropertyValue("--weight").trim(),
          a = cs.getPropertyValue("--pressure").trim(),
          tc = cs.getPropertyValue("--temp").trim();
        box.innerHTML = "";
        ratings
          .slice()
          .reverse()
          .forEach(function (v) {
            var i = document.createElement("i");
            i.style.height = (v / 10) * 60 + "px";
            i.style.background = v >= 8 ? w : v >= 6 ? a : tc;
            box.appendChild(i);
          });
      }

      (function () {
        var t = "ristretto";
        try {
          t = localStorage.getItem("theme") || "ristretto";
        } catch (e) {}
        setTheme(t);
      })();
'''
FEATURES_JS = r'''
      var I18N = {
        en: {
          wizDriveT: "One tap, and the sheet is yours",
          wizDriveB:
            "BrewPilot creates a spreadsheet in your own Drive and writes your brews to it. Nothing to copy, no scripts to deploy, no URL to paste. You can open it any time; it is a normal sheet that belongs to you.",
          wizDriveGo: "Save my brews to Google Drive",
          csConical: "Click counts are approximate: makers quote burr travel, not grind size.",
          wShot: "shot",
          wBrew: "brew",
          logEntry: "Log a {w}",
          logModeBefore: "About to brew",
          logModeAfter: "Already brewed",
          logStartBtn: "Start this brew",
          logSaveBtn2: "Save this brew",
          rateNone: "Tap to rate",
          rate1: "Undrinkable",
          rate2: "Bad",
          rate3: "Poor",
          rate4: "Meh",
          rate5: "Okay",
          rate6: "Fine",
          rate7: "Good",
          rate8: "Very good",
          rate9: "Excellent",
          rate10: "Best yet",
          fRegion: "Region",
          fRegionPh: "Rwanda, Huye",
          instBA:
            "A browser tab gets discarded, so you sign in to Google again every so often. Installed, BrewPilot stays signed in, opens like a real app and works offline. One tap.",
          gSaveFirst: "Save your brews to Google Drive first, in Settings.",
          welTitleG: "Welcome to the BrewPilot beta",
          welBodyG:
            "Log a brew and you get insights straight away, no setup. To keep your history safe and synced across devices, save it to your own Google Drive: one tap, and the sheet is yours.",
          welFootG: "Not now? Everything works offline and stays on this device.",
          gSaveFailed:
            "Could not save to Drive. Your brew is still on this device and will sync next time.",
          gNotSetUp: "Google sign-in is not configured in this build yet.",
          gAuthFailed: "Google sign-in did not complete. Nothing was saved to Drive.",
          gConnect: "Save my brews to Google Drive",
          gConnectSub:
            "One tap. BrewPilot creates a sheet in your Drive and writes to it. No copying, no scripts, no pasting URLs.",
          gConnected: "Saving to your Google Drive",
          gConnectedSub:
            "Your brews go to BrewPilot Log in your Drive. Open it any time, it is a normal spreadsheet that belongs to you.",
          gOpenSheet: "Open my sheet",
          gDisconnect: "Disconnect",
          durSheetT: "Your brews are backed up",
          durSheetB:
            "{n} brews are in your Google Sheet. Clearing this browser will not lose them.",
          durIOSTabT: "iOS will delete your brews",
          durIOSTabB:
            "Safari wipes a site’s data after 7 days of not opening it. That is iOS policy and no setting in this app can stop it. Add BrewPilot to your home screen, or save your brews to Google Drive. {n} brews at stake.",
          durInstalledT: "Installed, so your brews stay",
          durInstalledB:
            "Home screen apps are exempt from the 7 day wipe. {n} brews stored on this device. A sheet still protects you if the phone is lost.",
          durGrantedT: "This browser agreed to keep your brews",
          durGrantedB:
            "Storage is marked persistent, so it will not be cleared to free space. {n} brews on this device. Clearing browsing data by hand still erases them.",
          durBestEffortT: "Your brews are on this device only",
          durBestEffortB:
            "The browser may clear them when space runs low, and clearing browsing data erases them. {n} brews at stake. Install to the home screen, or save them to Google Drive.",
          insNeedMore: "Only {n} brews logged. Insights need about 6 to say anything honest.",
          insNothingYet: "Nothing stands out in your data yet. That is a real answer, not a bug.",
          insSpend: "You spent {v} on coffee in {m}",
          insSpendAvg: "That averages {v} a month",
          insPerCup: "A cup costs you {v} on average",
          insCostUp: "Your higher priced coffees do rate better. The money is buying something.",
          insCostDown: "Your cheaper coffees rate BETTER than your expensive ones. Worth a look.",
          insCostFlat:
            "Price and rating are unrelated across your last {n} brews. You could buy cheaper and not notice.",
          insValue: "Best value in your rotation: {c}",
          insWAcidUp: "Across {n} brews you rate Mg-forward, higher acidity waters better",
          insWAcidDown: "Across {n} brews you rate lower acidity waters better",
          insWBodyUp: "Across {n} brews you rate Ca-forward, fuller bodied waters better",
          insWBodyDown: "Across {n} brews you rate lighter, lower body waters better",
          insWBest: "You rate {w} water highest ({a} vs {b})",
          insTimeUp: "Longer brews rate better across {n} logs",
          insTimeDown: "Shorter brews rate better across {n} logs",
          insRatioUp: "Longer ratios rate better across {n} logs",
          insRatioDown: "Tighter ratios rate better across {n} logs",
          invBagSize: "Bag size",
          invPrice: "Price per bag",
          invFreezeDate: "Freeze date (or vacuum sealed)",
          hwGot: "Got it",
          hwFine:
            "The app works fully without it. You type dose, yield and time, and still get history, rotation and insights.",
          yoursGroup: "Yours",
          shareBtn: "Share my custom roasters",
          shareNone: "You have not added any custom roasters or processes yet.",
          shareCopied:
            "Copied. Paste it wherever you like, or send it to us if you want them in the built in list.",
          shareManual: "Copy this:",
          ratioOk: "in the usual band",
          ratioTight: "tighter than the usual {a}-{b}",
          ratioLong: "longer than the usual {a}-{b}",
          espWarn:
            "Note: {g} uses filter burrs and cannot grind fine enough for espresso. It is fine for pour over.",
          csTooFine:
            "{g} cannot grind this fine. Its finest is about {v} um. This brewer needs less than that, so pick a different grinder or method.",
          csTooCoarse: "{g} cannot grind this coarse. Its coarsest is about {v} um.",
          instT: "Install BrewPilot and stop signing in again",
          instB:
            "A browser tab gets discarded, so you sign in to Google again every so often. On iPhone a tab also loses your brews after 7 days unused. Installed, it stays open, stays signed in, and works offline. Same app, one tap.",
          instGo: "Install",
          ios1: "Tap the Share button in Safari",
          ios2: "Scroll down and tap Add to Home Screen",
          insLockT: "Log a few brews and this fills up",
          insLockB:
            "Insights compare your brews against each other: timing vs rating, water vs taste, what a cup actually costs you. That needs about six logs before it can say anything honest. No setup, no sheet, nothing to connect.",
          insLockGo: "Log a brew",
          csT: "Starting point",
          csHint: "Then dial by taste.",
          csTuned: "tuned to your {n} shots",
          editBtn: "Edit",
          labelBtn: "Label",
          layoutSplit: "Split",
          layoutStacked: "Stacked",
          logoAdd: "Add roaster logo",
          logoInvert: "Invert",
          logoChange: "Change logo",
          logoRemove: "Remove logo",
          logoFail: "Could not read that image.",
          logoTooBig: "That logo is too large to store. Try a smaller image.",
          logoHint:
            "Saved on this device for every bag from this roaster. Converted to pure black for thermal printing.",
          rotSuggestBtn: "suggest",
          rotNoBags: "No bags in your inventory yet.",
          rotEmptyHint: "none yet - log a brew, or mark a bag as in use",
          rotPicked: "{c} - {why}. Add it to your rotation?",
          invVarietal: "Varietal",
          invRegion: "Origin",
          labelTitle: "Label 50x30",
          labelHint:
            "Long-press the image to save it, then open NIIMBOT and import it as an image.",
          labelSave: "Download PNG",
          savedFrozen: "Frozen",
          savedResting: "Resting out to degas",
          bagOutBtn: "Take out of freezer",
          bagRotateBtn: "Start using it",
          bagFreezeBackBtn: "Back to freezer",
          chipInUse: "in use",
          bagOutHint: "out to degas",
          editBag: "Edit this bag",
          editShot: "Edit last entry",
          editLastBtn: "Edit last entry",
          editSave: "Save changes",
          editSaving: "Saving...",
          editFail: "Could not save. Try again.",
          editNeedSheet: "Connect your Google Sheet first.",
          editNoRow: "This bag has no sheet row yet.",
          editNoShot: "Nothing logged yet.",
          grindTab: "GRIND",
          gRatioLbl: "Ratio (1: dose)",
          grindHelper: "Grind helper",
          ghMethod: "Method",
          ghGrinder: "Grinder",
          ghRatio: "Soup ratio",
          ghBrewerL: "Brewer",
          ghRoastL: "Roast",
          ghProcL: "Process",
          ghOrigin: "Origin (opt)",
          ghVarL: "Varietal (opt)",
          ghHint: "Roast and process do the work; origin and varietal are a small density nudge.",
          ghSuggest: "Suggested grind",
          scoreBtn: "Just score this bag",
          restBtn: "Rest it (out to degas)",
          scoreBag: "Score this bag",
          scoreTap: "tap a rating",
          scoreDone: "Scored {c} {n}/10",
          scoreNeedCoffee: "Enter the coffee name first",
          scoreCancel: "Cancel",
          csCoarser: "coarser",
          csFiner: "finer",
          csNoAdj: "no change",
          csPick: "Pick a brewer to see a starting point.",
          csOn: "on",
          csClicks: "clicks",
          csAbs: "absolute",
          roastLight: "light roast",
          roastMed: "medium roast",
          roastDark: "dark roast",
          csWhy: "Lighter roasts start finer, darker start coarser.",
          duraT: "Your brews are only in this browser",
          duraB:
            "Nothing is backed up. Clearing your browser data, or leaving the site unused for about a week on iPhone, can erase it. Save your brews to your own Google Drive to keep them for good.",
          duraGo: "Save to Google Drive",
          duraExp: "Export backup",
          duraN: "brews stored locally, not backed up",
          duraSafeT: "Connected. Your history is saved.",
          duraSafeB: "Every brew goes to your Google Sheet. Insights read your full history.",
          insNeedSheet:
            "Insights get much better with a sheet. Locally I can only look at your recent brews; the sheet gives the full history, water and timing correlations.",
          wizSetupTitle: "Set up BrewPilot",
          wizSetupIntro:
            "Pick what you do. Everything works straight away with nothing connected. When you want your history kept safe and synced across devices, save it to your own Google Drive in one tap.",
          wizWhat: "What do you want to do?",
          wizMethods: "What do you brew?",
          wizHw: "What gear do you have?",
          wizGrinders: "Which grinders do you own?",
          wizDone: "Done, start using it",
          roleBrew: "Brew and log",
          roleInv: "Just inventory",
          hwNone: "Scale + timer",
          hwScale: "BLE scale",
          hwGag: "Gaggiuino",
          mEsp: "Espresso",
          mSoup: "Soup",
          mFil: "Filter",
          noSheetYet: "No sheet connected. Advice still works; nothing is saved.",
          homeInv: "Your inventory",
          homeLoading: "Loading your bags...",
          viewSheet: "View my sheet log",
          homeLogged: "logged",
          homeNone: "Nothing logged yet",
          homeStart: "Set up to begin",
          home: "HOME",
          log: "LOG",
          beans: "BEANS",
          insights: "INSIGHTS",
          readyToLog: "Ready to log",
          companion: "your coffee companion",
          lastRating: "Last rating",
          noShots: "No shots yet",
          logToBegin: "log one to begin",
          recentShots: "recent shots",
          rating: "rating",
          grindConverter: "Grinder converter",
          grindHelper: "Grind helper",
          ghMethod: "Method",
          ghGrinder: "Grinder",
          ghBrewer: "Brewer",
          ghRatio: "Ratio",
          ghRoast: "Roast",
          ghProcess: "Process",
          ghOrigin: "Origin",
          ghVarietal: "Varietal",
          ghHint: "Roast and process do the work; origin and varietal only nudge by density.",
          from: "From",
          to: "To",
          setting: "Setting",
          convHint: "Same burr gap, on each grinder's dial.",
          role: "Role",
          roleFull: "Full",
          roleLogMgr: "Log & manage",
          setupSheet: "Set up your Google Sheet",
          wizIntro:
            "Required for durable data. Without it your brews live only in this browser and can be erased. Do this once; it takes about five minutes.",
          close: "Close",
        },
        es: {
          wizDriveT: "Un toque, y la hoja es tuya",
          wizDriveB:
            "BrewPilot crea una hoja de cálculo en tu propio Drive y escribe ahí tus cafés. Nada que copiar, ningún script que implementar, ninguna URL que pegar. Ábrela cuando quieras; es una hoja normal que te pertenece.",
          wizDriveGo: "Guardar mis cafés en Google Drive",
          csConical:
            "Los clics son aproximados: los fabricantes indican recorrido de la fresa, no tamaño de molienda.",
          wShot: "shot",
          wBrew: "café",
          logEntry: "Registrar un {w}",
          logModeBefore: "Voy a preparar",
          logModeAfter: "Ya lo preparé",
          logStartBtn: "Empezar este café",
          logSaveBtn2: "Guardar este café",
          rateNone: "Toca para calificar",
          rate1: "Intomable",
          rate2: "Malo",
          rate3: "Pobre",
          rate4: "Regular",
          rate5: "Aceptable",
          rate6: "Bien",
          rate7: "Bueno",
          rate8: "Muy bueno",
          rate9: "Excelente",
          rate10: "El mejor",
          fRegion: "Región",
          fRegionPh: "Ruanda, Huye",
          durSheetT: "Tus cafés están respaldados",
          durSheetB: "{n} cafés están en tu Hoja de Google. Borrar este navegador no los pierde.",
          durIOSTabT: "iOS va a borrar tus cafés",
          durIOSTabB:
            "Safari borra los datos de un sitio después de 7 días sin abrirlo. Es política de iOS y ningún ajuste de esta app lo evita. Añade BrewPilot a tu pantalla de inicio, o guarda tus cafés en Google Drive. {n} cafés en riesgo.",
          durInstalledT: "Instalada, así que tus cafés se quedan",
          durInstalledB:
            "Las apps en pantalla de inicio no sufren el borrado de 7 días. {n} cafés guardados en este dispositivo. Una hoja te protege además si pierdes el teléfono.",
          durGrantedT: "Este navegador aceptó guardar tus cafés",
          durGrantedB:
            "El almacenamiento está marcado como persistente, no se borrará para liberar espacio. {n} cafés en este dispositivo. Borrar los datos a mano sí los elimina.",
          durBestEffortT: "Tus cafés están solo en este dispositivo",
          durBestEffortB:
            "El navegador puede borrarlos cuando falte espacio, y borrar los datos del navegador los elimina. {n} cafés en riesgo. Instala en la pantalla de inicio, o guárdalos en Google Drive.",
          gConnect: "Guardar mis cafés en Google Drive",
          gConnectSub:
            "Un toque. BrewPilot crea una hoja en tu Drive y escribe ahí. Sin copiar, sin scripts, sin pegar URLs.",
          gConnected: "Guardando en tu Google Drive",
          gConnectedSub:
            "Tus cafés van a BrewPilot Log en tu Drive. Ábrela cuando quieras, es una hoja normal que te pertenece.",
          gOpenSheet: "Abrir mi hoja",
          gDisconnect: "Desconectar",
          gNotSetUp: "El acceso con Google aún no está configurado en esta versión.",
          gAuthFailed: "El acceso con Google no se completó. No se guardó nada en Drive.",
          gSaveFailed:
            "No se pudo guardar en Drive. Tu café sigue en este dispositivo y se sincronizará la próxima vez.",
          gSaveFirst: "Primero guarda tus cafés en Google Drive, en Ajustes.",
          welTitleG: "Bienvenido a la beta de BrewPilot",
          welBodyG:
            "Registra un café y obtienes análisis de inmediato, sin configurar nada. Para conservar tu historial y sincronizarlo entre dispositivos, guárdalo en tu propio Google Drive: un toque, y la hoja es tuya.",
          welFootG: "¿Ahora no? Todo funciona sin conexión y se queda en este dispositivo.",
          insSpend: "Gastaste {v} en café en {m}",
          insSpendAvg: "Eso promedia {v} al mes",
          insPerCup: "Una taza te cuesta {v} en promedio",
          insCostUp:
            "Tus cafés más caros sí salen mejor calificados. El dinero está comprando algo.",
          insCostDown: "Tus cafés más baratos salen MEJOR que los caros. Vale la pena revisarlo.",
          insCostFlat:
            "El precio y la nota no se relacionan en tus últimos {n} cafés. Podrías comprar más barato y no notarlo.",
          insValue: "Mejor valor de tu rotación: {c}",
          insWAcidUp: "En {n} cafés calificas mejor las aguas con más Mg y más acidez",
          insWAcidDown: "En {n} cafés calificas mejor las aguas de menos acidez",
          insWBodyUp: "En {n} cafés calificas mejor las aguas con más Ca y más cuerpo",
          insWBodyDown: "En {n} cafés calificas mejor las aguas más ligeras",
          insWBest: "Calificas más alto el agua {w} ({a} vs {b})",
          insTimeUp: "Los cafés más largos salen mejor calificados en {n} registros",
          insTimeDown: "Los cafés más cortos salen mejor calificados en {n} registros",
          insRatioUp: "Las proporciones más largas salen mejor en {n} registros",
          insRatioDown: "Las proporciones más cortas salen mejor en {n} registros",
          insNeedMore:
            "Solo {n} cafés registrados. El análisis necesita unos 6 para decir algo honesto.",
          insNothingYet:
            "Todavía no destaca nada en tus datos. Eso es una respuesta real, no un error.",
          invBagSize: "Tamaño de bolsa",
          invPrice: "Precio por bolsa",
          invFreezeDate: "Fecha de congelado (o puesta al vacío)",
          instBA:
            "Una pestaña del navegador se descarta, así que vuelves a iniciar sesión cada tanto. Instalada, BrewPilot mantiene la sesión, se abre como una app real y funciona sin conexión. Un toque.",
          hwGot: "Entendido",
          hwFine:
            "La app funciona completa sin eso. Escribes dosis, salida y tiempo, y sigues teniendo historial, rotación y análisis.",
          yoursGroup: "Tuyos",
          shareBtn: "Compartir mis tostadores",
          shareNone: "Todavía no has agregado tostadores ni procesos propios.",
          shareCopied:
            "Copiado. Pégalo donde quieras, o mándanoslo si quieres que entren en la lista de fábrica.",
          shareManual: "Copia esto:",
          ratioOk: "dentro del rango habitual",
          ratioTight: "más corto que el rango habitual {a}-{b}",
          ratioLong: "más largo que el rango habitual {a}-{b}",
          espWarn:
            "Nota: el {g} usa fresas de filtrado y no muele lo bastante fino para espresso. Para vertido va bien.",
          csTooFine:
            "El {g} no muele tan fino. Su mínimo es como {v} um. Este brewer necesita menos, así que elige otro molino u otro método.",
          csTooCoarse: "El {g} no muele tan grueso. Su máximo es como {v} um.",
          instT: "Instala BrewPilot y deja de iniciar sesión",
          instB:
            "Una pestaña del navegador se descarta, así que vuelves a iniciar sesión en Google cada tanto. En iPhone además pierde tus cafés a los 7 días sin usar. Instalada, se mantiene abierta, con la sesión iniciada, y funciona sin conexión. La misma app, un toque.",
          instGo: "Instalar",
          ios1: "Toca el boton Compartir en Safari",
          ios2: "Baja y toca Añadir a pantalla de inicio",
          insLockT: "Registra unos cafés y esto se llena",
          insLockB:
            "El análisis compara tus cafés entre sí: tiempo vs nota, agua vs sabor, cuánto te cuesta una taza de verdad. Necesita unos seis registros para decir algo honesto. Sin configurar nada, sin hoja, sin conectar nada.",
          insLockGo: "Registrar un café",
          csT: "Punto de partida",
          csHint: "Luego ajusta por sabor.",
          csTuned: "ajustado a tus {n} cafes",
          editBtn: "Editar",
          labelBtn: "Etiqueta",
          layoutSplit: "Dividido",
          layoutStacked: "Apilado",
          logoAdd: "Agregar logo del tostador",
          logoInvert: "Invertir",
          logoChange: "Cambiar logo",
          logoRemove: "Quitar logo",
          logoFail: "No se pudo leer esa imagen.",
          logoTooBig: "Ese logo es muy grande para guardarse. Usa una imagen más chica.",
          logoHint:
            "Se guarda en este dispositivo y se usa en todas las bolsas de ese tostador. Se convierte a negro puro para impresión térmica.",
          rotSuggestBtn: "sugerir",
          rotNoBags: "Aún no tienes bolsas en el inventario.",
          rotEmptyHint: "aún ninguno - registra una preparación, o marca una bolsa como en uso",
          rotPicked: "{c} - {why}. ¿Agregarlo a tu rotación?",
          invVarietal: "Variedad",
          invRegion: "Origen",
          labelTitle: "Etiqueta 50x30",
          labelHint:
            "Mantén presionada la imagen para guardarla, luego abre NIIMBOT e impórtala como imagen.",
          labelSave: "Descargar PNG",
          savedFrozen: "Congelado",
          savedResting: "Reposando afuera",
          bagOutBtn: "Sacar del congelador",
          bagRotateBtn: "Empezar a usarla",
          bagFreezeBackBtn: "Regresar al congelador",
          chipInUse: "en uso",
          bagOutHint: "afuera desgasificando",
          editBag: "Editar esta bolsa",
          editShot: "Editar último registro",
          editLastBtn: "Editar último registro",
          editSave: "Guardar cambios",
          editSaving: "Guardando...",
          editFail: "No se pudo guardar. Intenta de nuevo.",
          editNeedSheet: "Conecta tu Hoja de Google primero.",
          editNoRow: "Esta bolsa aún no tiene fila en la hoja.",
          editNoShot: "Aún no hay registros.",
          grindTab: "MOLIENDA",
          gRatioLbl: "Proporción (1: dosis)",
          grindHelper: "Ayuda de molienda",
          ghMethod: "Método",
          ghGrinder: "Molino",
          ghRatio: "Ratio soup",
          ghBrewerL: "Brewer",
          ghRoastL: "Tueste",
          ghProcL: "Proceso",
          ghOrigin: "Origen (opc)",
          ghVarL: "Variedad (opc)",
          ghHint:
            "El tueste y el proceso mandan; origen y variedad son un ajuste menor por densidad.",
          ghSuggest: "Molienda sugerida",
          scoreBtn: "Solo calificar esta bolsa",
          restBtn: "Reposar (fuera del congelador)",
          scoreBag: "Calificar esta bolsa",
          scoreTap: "toca una nota",
          scoreDone: "Calificado {c} {n}/10",
          scoreNeedCoffee: "Escribe el nombre del cafe primero",
          scoreCancel: "Cancelar",
          csCoarser: "más grueso",
          csFiner: "más fino",
          csNoAdj: "sin cambio",
          csPick: "Elige un brewer para ver un punto de partida.",
          csOn: "en",
          csClicks: "clics",
          csAbs: "absoluto",
          roastLight: "tueste claro",
          roastMed: "tueste medio",
          roastDark: "tueste oscuro",
          csWhy: "Los tuestes claros empiezan más fino; los oscuros, más grueso.",
          duraT: "Tus cafés solo están en este navegador",
          duraB:
            "No hay respaldo. Si borras los datos del navegador, o no entras por una semana en iPhone, se puede borrar. Guarda tus cafés en tu propio Google Drive para conservarlos.",
          duraGo: "Guardar en Google Drive",
          duraExp: "Exportar respaldo",
          duraN: "cafés guardados solo aquí, sin respaldo",
          duraSafeT: "Conectado. Tu historial esta guardado.",
          duraSafeB: "Cada café va a tu Hoja de Google. El análisis lee todo tu historial.",
          insNeedSheet:
            "El análisis mejora mucho con una hoja. Aqui solo veo tus cafés recientes; la hoja da el historial completo y las correlaciones de agua y tiempo.",
          wizSetupTitle: "Configura BrewPilot",
          wizSetupIntro:
            "Elige qué haces. Todo funciona de inmediato sin conectar nada. Cuando quieras conservar tu historial y sincronizarlo entre dispositivos, guárdalo en tu propio Google Drive con un toque.",
          wizWhat: "¿Que quieres hacer?",
          wizMethods: "¿Qué preparas?",
          wizHw: "¿Qué equipo tienes?",
          wizGrinders: "¿Qué molinos tienes?",
          wizDone: "Listo, empezar",
          roleBrew: "Preparar y registrar",
          roleInv: "Solo inventario",
          hwNone: "Báscula + cronometro",
          hwScale: "Báscula BLE",
          hwGag: "Gaggiuino",
          mEsp: "Espresso",
          mSoup: "Soup",
          mFil: "Filtrado",
          noSheetYet: "Sin hoja conectada. Los consejos funcionan; no se guarda nada.",
          homeInv: "Tu inventario",
          homeLoading: "Cargando tus bolsas...",
          viewSheet: "Ver mi registro en la hoja",
          homeLogged: "registrados",
          homeNone: "Aun no hay registros",
          homeStart: "Configura para empezar",
          home: "INICIO",
          log: "REGISTRO",
          beans: "CAFES",
          insights: "ANALISIS",
          readyToLog: "Listo para registrar",
          companion: "tu compañero de café",
          lastRating: "Ultima nota",
          noShots: "Aun no hay shots",
          logToBegin: "registra uno para empezar",
          recentShots: "shots recientes",
          rating: "nota",
          grindConverter: "Conversor de molienda",
          grindHelper: "Ayuda de molienda",
          ghMethod: "Metodo",
          ghGrinder: "Molino",
          ghBrewer: "Brewer",
          ghRatio: "Proporcion",
          ghRoast: "Tueste",
          ghProcess: "Proceso",
          ghOrigin: "Origen",
          ghVarietal: "Variedad",
          ghHint:
            "El tueste y el proceso hacen el trabajo; origen y variedad solo ajustan por densidad.",
          from: "De",
          to: "A",
          setting: "Ajuste",
          convHint: "Misma separacion de fresas, en el dial de cada molino.",
          role: "Perfil",
          roleFull: "Completo",
          roleLogMgr: "Solo registro",
          setupSheet: "Configura tu Hoja de Google",
          wizIntro:
            "Necesario para no perder tus datos. Sin esto, tus cafés solo viven en este navegador y se pueden borrar. Hazlo una vez; toma unos cinco minutos.",
          close: "Cerrar",
        },
      };
      var LANG = "es";
      try {
        LANG = localStorage.getItem("lang") || "es";
      } catch (e) {}
      function t(k) {
        return (I18N[LANG] && I18N[LANG][k]) || I18N.en[k] || k;
      }
      function applyLang() {
        try {
          loadInventory();
        } catch (e) {}
        try {
          renderRotModes();
        } catch (e) {}
        if (typeof uiSchedule === "function") uiSchedule();
        document.querySelectorAll("[data-i18n]").forEach(function (el) {
          el.textContent = t(el.getAttribute("data-i18n"));
        });
        document.querySelectorAll("[data-i18n-ph]").forEach(function (el) {
          el.setAttribute("placeholder", t(el.getAttribute("data-i18n-ph")));
        });
        var lb = document.getElementById("langBtn");
        if (lb) lb.textContent = LANG === "es" ? "EN" : "ES";
        document.documentElement.lang = LANG;
        try {
          applyNoun();
        } catch (e) {}
        try {
          renderTier();
        } catch (e) {}
        try {
          renderChips();
        } catch (e) {}
        try {
          convInit();
        } catch (e) {}
        try {
          renderRoleChips();
        } catch (e) {}
      }
      function setLang(l) {
        try {
          document.documentElement.lang = l === "es" ? "es" : "en";
        } catch (e) {}
        LANG = l;
        try {
          localStorage.setItem("lang", l);
        } catch (e) {}
        applyLang();
      }
      var ROLE = "full";
      try {
        ROLE = localStorage.getItem("role") || "full";
      } catch (e) {}
      function applyRole() {
        document.body.classList.toggle("role-logmgr", ROLE === "logmgr");
      }
      function setRole(r) {
        ROLE = r;
        try {
          localStorage.setItem("role", r);
        } catch (e) {}
        applyRole();
        renderRoleChips();
        try {
          renderTier();
        } catch (e) {}
      }
      function renderRoleChips() {
        var box = document.getElementById("rolechips");
        if (!box) return;
        box.innerHTML = "";
        [
          ["full", "roleFull"],
          ["logmgr", "roleLogMgr"],
        ].forEach(function (m) {
          var c = document.createElement("div");
          c.textContent = t(m[1]);
          c.className = "chip" + (ROLE === m[0] ? " on" : "");
          c.onclick = function () {
            setRole(m[0]);
          };
          box.appendChild(c);
        });
      }
      function ghDensity(origin, varietal) {
        var isEs = typeof LANG !== "undefined" && LANG === "es";
        var s = ((origin || "") + " " + (varietal || "")).toLowerCase();
        if (
          /ethiopia|kenya|colombia|guatemala|gesha|geisha|sl28|sl34|bourbon|pacamara|sudan rume|chiroso|ombligon/.test(
            s,
          )
        )
          return {
            f: 0.97,
            note: isEs ? "grano denso / de altura: ~3% mas fino" : "dense / high-grown: ~3% finer",
          };
        if (/robusta|conilon/.test(s))
          return {
            f: 1.03,
            note: isEs ? "grano mas blando: ~3% mas grueso" : "softer bean: ~3% coarser",
          };
        return { f: 1.0, note: "" };
      }
      function grindHelperInit() {
        var add = function (sel, items, selVal) {
          var e = document.getElementById(sel);
          if (!e || e.options.length) return;
          items.forEach(function (it) {
            var v = it && it.v !== undefined ? it.v : it;
            var lab = it && it.n !== undefined ? it.n : it;
            var o = document.createElement("option");
            o.value = v;
            o.textContent = lab;
            if (selVal != null && v === selVal) o.selected = true;
            e.appendChild(o);
          });
        };
        (function () {
          var e = document.getElementById("ghGrinder");
          if (e) {
            var pv = e.value;
            e.innerHTML = "";
            ownedGrinders().forEach(function (id) {
              var g = GRINDERS[id];
              if (!g) return;
              var o = document.createElement("option");
              o.value = id;
              o.textContent = g.n;
              e.appendChild(o);
            });
            if (pv && GRINDERS[pv]) e.value = pv;
          }
        })();
        add("ghBrewer", [
          "V60",
          "V60 Switch",
          "V60 Neo",
          "Orea",
          "Origami",
          "Chemex",
          "Kalita",
          "AeroPress",
          "Other",
        ]);
        add(
          "ghRoast",
          ["Ultra Light", "Extra Light", "Light", "Light Medium", "Medium", "Medium Dark", "Dark"],
          "Light",
        );
        add("ghProcess", [
          "Washed",
          "Natural",
          "Honey",
          "Anaerobic",
          "Anaerobic Natural",
          "Carbonic Maceration",
          "Lactic",
          "Extended Fermentation",
          "Thermal Shock",
        ]);
        grindHelperRender();
      }
      function grindHelperRender() {
        var g = function (id) {
          var e = document.getElementById(id);
          return e ? e.value : "";
        };
        var method = g("ghMethod") || "soup";
        var brc = document.getElementById("ghBrewerCell"),
          rac = document.getElementById("ghRatioCell");
        if (brc) brc.style.display = method === "filter" ? "" : "none";
        if (rac) rac.style.display = method === "soup" ? "" : "none";
        var gid = g("ghGrinder") || ownedGrinders()[0] || "ZP6";
        var roast = g("ghRoast") || "Light",
          process = g("ghProcess") || "Washed";
        var key =
          method === "espresso"
            ? "Espresso"
            : method === "soup"
              ? "Soup " + (g("ghRatio") || "1:3-4")
              : g("ghBrewer") || "V60";
        var um = typeof BREWER_UM === "object" && BREWER_UM[key] ? BREWER_UM[key] : 750;
        var rf = typeof ROAST_F === "object" && ROAST_F[roast] ? ROAST_F[roast] : 1;
        var pf = 1;
        try {
          pf = processTier(process) || 1;
        } catch (e) {}
        var dn = ghDensity(g("ghOrigin"), g("ghVarietal"));
        um = Math.round(um * rf * pf * dn.f);
        var out = document.getElementById("ghOut");
        if (!out) return;
        var gg = GRINDERS[gid];
        var setStr;
        if (!gg || gg.um === 0) {
          setStr = um + "um";
        } else {
          var clicks = umToClicks(um, gid);
          if (clicks == null) {
            setStr = "--";
          } else {
            clicks = Math.max(0, Math.round(clicks));
            setStr = gg.dialPer
              ? (clicks / gg.dialPer).toFixed(1) + " (" + clicks + " clicks)"
              : clicks + " clicks";
          }
        }
        var isEs = typeof LANG !== "undefined" && LANG === "es";
        out.innerHTML =
          "<b style='font-size:15px'>" +
          setStr +
          "</b> <span style='color:var(--dim);font-size:12px'>(" +
          um +
          "um · " +
          (gg ? gg.n : gid) +
          ")</span>" +
          (dn.note
            ? "<div style='color:var(--pressure);font-size:11px;margin-top:3px'>" +
              dn.note +
              "</div>"
            : "");
      }
      function convInit() {
        var f = document.getElementById("convFrom"),
          tt = document.getElementById("convTo");
        if (!f || !tt) return;
        var keys = Object.keys(GRINDERS),
          cur = [f.value, tt.value];
        f.innerHTML = "";
        tt.innerHTML = "";
        keys.forEach(function (id) {
          var o = document.createElement("option");
          o.value = id;
          o.textContent = GRINDERS[id].n;
          f.appendChild(o);
          tt.appendChild(o.cloneNode(true));
        });
        f.value = cur[0] || keys[0];
        tt.value = cur[1] || keys[1];
        convCompute();
      }
      function convParse(raw, gid) {
        var g = GRINDERS[gid];
        var t = ("" + raw).trim();
        if (!t) return NaN;
        if (g && g.dialPer && t.indexOf(".") >= 0) {
          var p = t.split(".");
          var n = parseInt(p[0], 10),
            c = parseInt(p[1], 10);
          if (isNaN(n) || isNaN(c)) return NaN;
          return n * g.dialPer + c;
        }
        return parseFloat(t);
      }
      function convFmt(val, gid) {
        var g = GRINDERS[gid];
        if (!g) return String(val);
        if (g.um === 0) return Math.round(val) + " um";
        if (g.dialPer) {
          var d = dialTxt(gid, val);
          return d + " (" + Math.round(val) + " clk)";
        }
        return Math.round(val * 10) / 10 + " clk";
      }
      function convCompute() {
        var f = document.getElementById("convFrom"),
          tt = document.getElementById("convTo"),
          out = document.getElementById("convOut");
        if (!out) return;
        var v = convParse(document.getElementById("convVal").value, f.value);
        if (isNaN(v)) {
          out.textContent = "";
          return;
        }
        var r = convertGrind(v, f.value, tt.value),
          tg = GRINDERS[tt.value];
        if (r == null) {
          out.textContent = "-";
          return;
        }
        var toUm = tg && tg.um === 0 ? r : clicksToUm(r, tt.value);
        if (r < 0 || (tg && tg.min && toUm < tg.min)) {
          out.textContent =
            convFmt(v, f.value) +
            " (" +
            GRINDERS[f.value].n +
            ") is finer than the " +
            tg.n +
            " can grind";
          return;
        }
        if (tg && tg.max && toUm > tg.max) {
          out.textContent =
            convFmt(v, f.value) +
            " (" +
            GRINDERS[f.value].n +
            ") is coarser than the " +
            tg.n +
            " can grind";
          return;
        }
        out.textContent =
          convFmt(v, f.value) +
          " (" +
          GRINDERS[f.value].n +
          ")  →  " +
          convFmt(r, tt.value) +
          "  (" +
          tg.n +
          ")";
      }
      /* wizVerify REMOVED: its only caller was the Verify-and-connect button on the
   /exec paste step. goConnectSheet() is the whole flow now. */
      applyRole();
      renderRoleChips();
      convInit();
      try {
        grindHelperInit();
      } catch (e) {}
      setTimeout(function () {
        if (typeof iLoad === "function") {
          iLoad()
            .then(function () {
              try {
                homeRender();
              } catch (e) {}
              try {
                renderChips();
              } catch (e) {}
              try {
                loadInventory();
              } catch (e) {}
              try {
                gMigrateHeaders();
              } catch (e) {}
            })
            .catch(function () {});
        }
      }, 0);
      /* ---------------------------------------------------------------
   UI scheduler. No polling: the app's own code rewrites innerHTML at
   unpredictable times, so we watch for those writes instead of guessing.
   The observer is disconnected while we render, otherwise our own writes
   would retrigger it forever.
   --------------------------------------------------------------- */
      var UI_OBS = null,
        UI_T = null,
        UI_BUSY = false;
      function uiRender() {
        if (UI_BUSY) return;
        UI_BUSY = true;
        if (UI_OBS) UI_OBS.disconnect();
        try {
          trWalk();
        } catch (e) {}
        try {
          rotTips();
        } catch (e) {}
        try {
          renderTier();
        } catch (e) {}
        try {
          insGate();
        } catch (e) {}
        try {
          duraRender();
        } catch (e) {}
        try {
          renderColdStart();
        } catch (e) {}
        try {
          csInline();
        } catch (e) {}
        try {
          renderHero();
        } catch (e) {}
        try {
          homeRender();
        } catch (e) {}
        try {
          instRender();
        } catch (e) {}
        try {
          wireHelp();
        } catch (e) {}
        try {
          invSelectsInit();
        } catch (e) {}
        try {
          invFreezeDateInit();
        } catch (e) {}
        try {
          invCcyInit();
        } catch (e) {}
        try {
          renderBagChips();
        } catch (e) {}
        try {
          invPerG();
        } catch (e) {}
        try {
          filterSelectsInit();
        } catch (e) {}
        try {
          renderEspExtras();
        } catch (e) {}
        try {
          renderWaterNotes();
        } catch (e) {}
        try {
          gRatioLive();
        } catch (e) {}
        try {
          protectProperNouns();
        } catch (e) {}
        try {
          syncAllYours();
        } catch (e) {}
        try {
          placeShareBtn();
        } catch (e) {}
        try {
          sheetCtas();
        } catch (e) {}
        try {
          retitleCtas();
        } catch (e) {}
        try {
          gInit();
        } catch (e) {}
        try {
          renderGoogleCard();
        } catch (e) {}
        try {
          renderBuild();
        } catch (e) {}
        try {
          renderRateChips();
        } catch (e) {}
        try {
          renderLogEntry();
        } catch (e) {}
        /* The method picker and the form switch must run at BOOT, not only when
     something calls renderLogMode(). They were wired with an unguarded
     s.replace() whose pattern had a space the real code did not, so the boot call
     silently never landed: #logMethodRow rendered EMPTY until you touched it, and
     both forms were laid out by whatever the markup happened to say.
     Guarded now - which is the whole reason must_replace exists. */
        try {
          renderLogMethod();
        } catch (e) {}
        try {
          renderLogForm();
        } catch (e) {}
        try {
          renderLogMode();
        } catch (e) {}
        try {
          renderInstallCard();
        } catch (e) {}
        try {
          requestPersistence();
        } catch (e) {}
        try {
          renderDurability();
        } catch (e) {}
        try {
          renderClientInsights();
        } catch (e) {}
        if (UI_OBS)
          UI_OBS.observe(document.body, { childList: true, subtree: true, characterData: true });
        UI_BUSY = false;
      }
      function uiSchedule() {
        if (UI_T) return;
        UI_T = setTimeout(function () {
          UI_T = null;
          uiRender();
        }, 120);
      }
      function uiStart() {
        UI_OBS = new MutationObserver(function (muts) {
          for (var i = 0; i < muts.length; i++) {
            var t = muts[i].target;
            if (
              t &&
              t.id &&
              (t.id === "heroSpark" ||
                t.id === "duraCount" ||
                t.id === "rotLegend" ||
                t.id === "insText")
            )
              continue;
            return uiSchedule();
          }
        });
        UI_OBS.observe(document.body, { childList: true, subtree: true, characterData: true });
        uiRender();
      }

      /* ---- Log tab: one method, one form, one button ----
   Before this, the Log tab showed the gaggia form AND the filter form at the same
   time, each complete with its own coffee/roaster/roast/dose/time fields and its
   own pair of buttons. Two forms, three sets of buttons, one screen.
   #type already knew which method you meant. It was just buried inside the gaggia
   form, and a selector cannot hide its own container, so it never switched.
   Now: chips at the top set #type, #type picks the form, and LOGMODE picks what
   the single green button does. */
      function logAction(kind) {
        /* the button IS the mode. before -> plan it, after -> record it. */
        if (LOGMODE === "before") {
          try {
            return startBrew(kind);
          } catch (e) {}
          return;
        }
        /* The identity gate runs first and can rewrite #coffee, so the save has to
     happen after it resolves, not beside it. */
        bpCoffeeGate()
          .then(function (ok) {
            if (!ok) return;
            if (kind === "filter") {
              try {
                return logFilter();
              } catch (e) {}
              return;
            }
            try {
              return logshot();
            } catch (e) {}
          })
          .catch(function () {
            if (kind === "filter") {
              try {
                return logFilter();
              } catch (e) {}
              return;
            }
            try {
              return logshot();
            } catch (e) {}
          });
      }
      function logMethods() {
        /* All three, always. This used to list only the methods enabled in the wizard,
     so Oscar - who had not ticked espresso - had no way to log one and no way to
     get an espresso starting point: "give me a way to chose espresso somewhere as
     well". What you usually brew is a good default; it is a bad cage. The wizard
     flags still drive defaults elsewhere, they just no longer forbid a method. */
        return [
          ["espresso", "mEsp"],
          ["soup", "mSoup"],
          ["filter", "mFil"],
        ];
      }
      function logMethod() {
        var ms = logMethods().map(function (m) {
          return m[0];
        });
        var t = document.getElementById("type");
        var v = t ? t.value : "";
        if (ms.indexOf(v) >= 0) return v;
        /* Nothing valid chosen yet, so restore the last choice. setLogMethod() has
     always WRITTEN localStorage.logMethod and nothing ever read it back, so every
     reload silently reverted to the first enabled method - a write with no reader
     is the same dead-feature shape as everything else in this app's history.
     Sync #type too: it is the value store logshot() saves to the sheet, so a
     chip that disagrees with it would log the wrong method. */
        var saved = "";
        try {
          saved = localStorage.getItem("logMethod") || "";
        } catch (e) {}
        if (ms.indexOf(saved) >= 0) {
          if (t && t.value !== saved) t.value = saved;
          return saved;
        }
        return ms[0];
      }
      function setLogMethod(v) {
        var t = document.getElementById("type");
        if (t) {
          t.value = v;
          try {
            t.dispatchEvent(new Event("change", { bubbles: true }));
          } catch (e) {}
        }
        try {
          localStorage.setItem("logMethod", v);
        } catch (e) {}
        renderLogMethod();
        renderLogForm();
        renderLogMode();
        /* the target depends on the method, so recompute it now. Without this the banner
     kept the PREVIOUS method's number until something else re-rendered - switch
     espresso(Thermal)->soup and soup showed espresso's stuck value. */
        try {
          csInline();
        } catch (e) {}
        try {
          renderColdStart();
        } catch (e) {}
      }
      function renderLogMethod() {
        var row = document.getElementById("logMethodRow");
        if (!row) return;
        var sel = logMethod(),
          ms = logMethods();
        /* one method: no picker to show, but the form switch still has to run */
        row.style.display = ms.length < 2 ? "none" : "";
        var want = ms
          .map(function (m) {
            return m[0] + ":" + t(m[1]) + ":" + (m[0] === sel ? "1" : "0");
          })
          .join("|");
        if (row.getAttribute("data-built") === want) return;
        row.setAttribute("data-built", want);
        row.innerHTML = "";
        ms.forEach(function (m) {
          var b = document.createElement("button");
          b.type = "button";
          b.textContent = t(m[1]);
          b.className = m[0] === sel ? "on" : "off";
          b.setAttribute("data-method", m[0]);
          b.onclick = function () {
            setLogMethod(m[0]);
          };
          row.appendChild(b);
        });
        var ts = document.getElementById("type");
        if (ts) ts.style.display = "none"; /* value store only; the chips are the interface */
      }
      /* The grinder chips are shared by both forms, so they cannot live inside one. */

      /* A link to the actual sheet. Oscar: "add a button to see my google sheet log".
   gSheetUrl() already existed; nothing on the logging screen ever offered it. */
      function renderSheetLink() {}
      function renderLogForm() {
        var m = logMethod();
        document.querySelectorAll(".mmethod").forEach(function (el) {
          var mg = el.getAttribute("data-mgag") === "1",
            mf = el.getAttribute("data-mfilter") === "1",
            ms = el.getAttribute("data-msoup") === "1";
          var vis;
          if (ms) {
            vis = m === "soup";
          } else if (mf) {
            vis = m === "filter";
          } else if (mg) {
            vis = m !== "filter";
          } else {
            vis = true;
          }
          el.style.display = vis ? "" : "none";
        });
        try {
          renderSheetLink();
        } catch (e) {}
        try {
          renderCoffeeList();
        } catch (e) {}
        try {
          updateCoffeeHint();
        } catch (e) {}
        if (m === "soup") {
          try {
            renderSoupRatioChips();
          } catch (e) {}
        }
        if (m === "filter") {
          try {
            renderBrewerChips();
          } catch (e) {}
          try {
            renderRecipeChips();
          } catch (e) {}
          try {
            renderTempChips();
          } catch (e) {}
          try {
            renderFilterExtras();
          } catch (e) {}
        }
      }
      function renderSoupRatioChips() {
        var box = document.getElementById("soupRatioChips");
        if (!box) return;
        box.innerHTML = "";
        var cur = localStorage.getItem("soupRatio") || "1:3-4";
        [
          ["1:3-4", "concentrated"],
          ["1:5-8", "medium"],
          ["1:10", "H&S long"],
        ].forEach(function (b) {
          var on = cur === b[0];
          var c = document.createElement("div");
          c.textContent = b[0];
          c.title = b[1];
          c.style.cssText =
            "padding:8px 12px;border-radius:18px;font-size:13px;cursor:pointer;border:1px solid " +
            (on ? "var(--sel-line)" : "var(--line)") +
            ";background:" +
            (on ? "var(--sel-bg)" : "var(--panel)") +
            ";color:" +
            (on ? "var(--sel-text)" : "var(--text)");
          c.onclick = function () {
            localStorage.setItem("soupRatio", b[0]);
            renderSoupRatioChips();
            try {
              csInline();
            } catch (e) {}
            try {
              renderColdStart();
            } catch (e) {}
            try {
              uiSchedule();
            } catch (e) {}
          };
          box.appendChild(c);
        });
      }

      /* wizard: render its chips when it opens, and only then */
      (function () {
        var m = document.getElementById("wizMask");
        if (!m) return;
        new MutationObserver(function () {
          if (m.classList.contains("on")) {
            try {
              wizRender();
            } catch (e) {}
            uiSchedule();
          }
        }).observe(m, { attributes: true, attributeFilter: ["class"] });
      })();

      /* cold start depends on roast / grinder / brewer: listen instead of poll */
      document.addEventListener("change", function (e) {
        if (!e.target || !e.target.id) return;
        /* process/fprocess were missing here, so changing the process dropdown never
     re-rendered the advisor - "PROCESS CHANGES NOTHING". roast worked only because
     froast/roast were listed. Also covers the filter-form twins so every field
     that feeds csFor triggers a refresh. */
        if (
          ["froast", "roast", "fprocess", "process", "grinder", "convFrom", "convTo"].indexOf(
            e.target.id,
          ) >= 0
        )
          uiSchedule();
      });
      document.addEventListener(
        "click",
        function (e) {
          var el = e.target;
          if (
            el &&
            el.closest &&
            (el.closest("#brewerchips") || el.closest("#rotmodechips") || el.closest("#grchips"))
          )
            uiSchedule();
        },
        true,
      );

      /* state changes that must repaint */
      [
        "setLang",
        "setRole",
        "setTheme",
        "goConnectSheet",
        "logshot",
        "logFilter",
        "freezeCoffee",
        "toggleInv",
        "toggleInsights",
        "toggleSettings",
        "showTab",
      ].forEach(function (fn) {
        if (typeof window[fn] !== "function") return;
        var orig = window[fn];
        window[fn] = function () {
          var r = orig.apply(this, arguments);
          uiSchedule();
          return r;
        };
      });

      /* ---- update safety ----
   Every release runs this before anything reads storage. It snapshots all keys
   first, so a bad migration can be undone, and it never deletes keys it does not
   recognise. Renamed grinder ids get aliased instead of dropped. */
      var SCHEMA = 2;
      var GRINDER_ALIASES = {
        Sculptor078s: "Sculptor078S",
        TimemoreSculptor078S: "Sculptor078S",
        S3: "TimemoreS3",
      };
      function snapshotStorage() {
        var all = {};
        try {
          for (var i = 0; i < localStorage.length; i++) {
            var k = localStorage.key(i);
            if (k.indexOf("backup_") === 0) continue;
            all[k] = localStorage.getItem(k);
          }
        } catch (e) {}
        return all;
      }
      function migrate() {
        var v = 0;
        try {
          v = parseInt(localStorage.getItem("schema") || "0", 10) || 0;
        } catch (e) {
          return;
        }
        if (v === SCHEMA) return;
        var snap = snapshotStorage();
        try {
          localStorage.setItem(
            "backup_v" + v,
            JSON.stringify({ at: new Date().toISOString(), data: snap }),
          );
        } catch (e) {}
        try {
          // v0/v1 -> v2: grinder ids may have been renamed. Map, never drop.
          var raw = localStorage.getItem("myGrinders");
          if (raw) {
            var list = JSON.parse(raw),
              out = [],
              changed = false;
            list.forEach(function (id) {
              var n = GRINDER_ALIASES[id] || id;
              if (n !== id) changed = true;
              if (out.indexOf(n) < 0) out.push(n);
            });
            if (changed) localStorage.setItem("myGrinders", JSON.stringify(out));
          }
          var lg = localStorage.getItem("grinder");
          if (lg && GRINDER_ALIASES[lg]) localStorage.setItem("grinder", GRINDER_ALIASES[lg]);
        } catch (e) {
          /* leave storage untouched on any error */
        }
        try {
          localStorage.setItem("schema", String(SCHEMA));
        } catch (e) {}
      }
      function restoreBackup(v) {
        try {
          var b = JSON.parse(localStorage.getItem("backup_v" + v) || "null");
          if (!b) return false;
          Object.keys(b.data).forEach(function (k) {
            localStorage.setItem(k, b.data[k]);
          });
          return true;
        } catch (e) {
          return false;
        }
      }
      migrate();
      var UIDICT = {
        Coffee: "Cafe",
        Roaster: "Tostador",
        Roast: "Tueste",
        "Roast date": "Fecha de tueste",
        Water: "Agua",
        "Water (g)": "Agua (g)",
        Brewer: "Brewer",
        Agitation: "Agitación",
        "Filter paper": "Filtro de papel",
        "Dose (g)": "Dosis (g)",
        "Rating (1-10)": "Nota (1-10)",
        "Kettle temp (C)": "Temp del agua (C)",
        "Total time (m:ss)": "Tiempo total (m:ss)",
        "Bloom time (s, optional)": "Preinfusión (s, opcional)",
        "Portion size": "Cuanto sacas por vez (porcion)",
        "How many": "Cuantas",
        "How did it taste?": "¿Como sabe?",
        "Recipe (tap to prefill)": "Receta (toca para rellenar)",
        "Rotation style": "Estilo de rotación",
        "Your inventory": "Tu inventario",
        Settings: "Ajustes",
        Insights: "Análisis",
        Off: "Apagar",
        "Warm up": "Calentar",
        Other: "Otro",
        "Freeze it": "Congelar",
        "Freeze coffee": "Agregar café (congelar o reposar)",
        "Refresh now": "Actualizar",
        "Save to Google Drive": "Guardar en Google Drive",
        "Connect my sheet": "Conectar mi hoja",
        "Save my brews to Google Drive": "Guardar mis cafés en Google Drive",
        "Save to log": "Guardar registro",
        "Save filter brew": "Guardar filtrado",
        "Start (plan now)": "Iniciar (planear)",
        "Start brew (plan now)": "Iniciar preparación (planear)",
        "Same coffee as last shot": "Mismo café que el último",
        "Same coffee / from rotation": "Mismo café / de la rotación",
        "Log the last shot": "Registrar el último shot",
        "Finished this bag - suggest next": "Bolsa terminada - sugerir siguiente",
        "What do you brew?": "¿Qué preparas?",
        "What hardware do you have?": "¿Qué equipo tienes?",
        "Which grinders do you own? (shown when logging)":
          "¿Qué molinos tienes? (se muestran al registrar)",
        "Google Sheet (enables inventory, history, trends)":
          "Hoja de Google (activa inventario, historial, tendencias)",
        "Coffee inventory & rotation": "Inventario y rotación de café",
        "Coffee inventory &amp; rotation": "Inventario y rotación de café",
        "Current rotation (tap to fill):": "Rotación actual (toca para rellenar):",
        "Grind setting used:": "Molienda usada:",
        "Grinder (tap to switch, converts setting):":
          "Molino (toca para cambiar, convierte el ajuste):",
        "New-bean cold start (per brewer, on your grinder)":
          "Punto de partida (por brewer, en tu molino)",
        "How often should insights arrive?": "¿Cada cuánto quieres el análisis?",
        "Welcome to the BrewPilot beta": "Bienvenido a la beta de BrewPilot",
        "your coffee companion": "tu copiloto del café",
        "+ Log a filter / non-Gaggia brew": "+ Registrar un filtrado / no-Gaggia",
        "+ paper / agitation (optional)": "+ papel / agitación (opcional)",
        espresso: "espresso",
        soup: "soup",
        filter: "filtrado",
        "loading...": "cargando...",
        "varietal...": "variedad...",
        "process...": "proceso...",
        "roast level...": "nivel de tueste...",
        "roaster...": "tostador...",
        "type (auto)": "tipo (auto)",
        grinder: "molino",
        "coffee name": "nombre del café",
        "dose g": "dosis g",
        "grind # / um": "molienda # / um",
        "paste your /exec URL": "pega tu URL /exec",
        "type roaster name": "escribe el tostador",
        "type process": "escribe el proceso",
        "e.g. Panama Gesha": "ej. Panama Gesha",
        "device key (from your BrewPilot)": "clave del dispositivo (de tu BrewPilot)",
        "Logged to your sheet": "Guardado en tu hoja",
        "Filter brew logged": "Filtrado registrado",
        "Could not load insights.": "No se pudo cargar el análisis.",
        "Could not refresh.": "No se pudo actualizar.",
        "Crunching your brews...": "Analizando tus preparaciones...",
        "No insights yet. Log a few brews and rate them, then Refresh now.":
          "Aun no hay análisis. Registra y califica algunas preparaciones, luego Actualizar.",
        "Save to Google Drive first": "Conecta una hoja primero",
        "Connect your Google Sheet in Settings first.":
          "Conecta tu Hoja de Google en Ajustes primero.",
        "Connect a Google Sheet first (Settings) to save inventory.":
          "Conecta una Hoja de Google (Ajustes) para guardar el inventario.",
        "Brew planned. Come back and tap Finish when it is done.":
          "Preparación planeada. Vuelve y toca Terminar cuando acabe.",
        "Add at least the coffee name to start a brew":
          "Añade al menos el nombre del café para empezar",
        "Coffee name?": "¿Nombre del café?",
        "Discard the planned brew?": "Descartar la preparación planeada?",
        "Marked finished. Check Telegram for what to thaw next.":
          "Marcado como terminado. Revisa Telegram para saber que descongelar.",
        "No device yet": "Aún sin dispositivo",
        "Machine control is available on the BrewPilot device":
          "El control de la máquina está en el dispositivo BrewPilot",
        "Machine control needs the BrewPilot device + a Gaggiuino.":
          "El control de la máquina requiere el dispositivo BrewPilot y un Gaggiuino.",
        "Use oldest": "Usar el más viejo",
        "Keep it interesting": "Manten la variedad",
        "Peak flavor": "Sabor óptimo",
        Balanced: "Equilibrado",
        "Bag size": "Tamaño de la bolsa que compraste",
        "Price per bag": "Precio por bolsa",
        "Freeze date": "Fecha de congelado",
        "Share my custom roasters": "Compartir mis tostadores",
        "Yield (g)": "Salida (g)",
        "Time (m:ss or s)": "Tiempo (m:ss o s)",
        "Preinfusion (s)": "Preinfusión (s)",
        "Temp (C)": "Temp (C)",
        Basket: "Canasta",
        Prep: "Preparación",
        "Paper in basket": "Papel en canasta",
        "+ basket / prep / paper (optional)": "+ canasta / preparación / papel (opcional)",
        Varietal: "Variedad",
        Process: "Proceso",
        "New-bean cold start (per brewer, on your grinder)":
          "Punto de partida (por brewer, en tu molino)",
        "Grind # (ZP6)": "Molienda # (ZP6)",
        "Filter brew": "Filtrado",
        Espresso: "Espresso",
        Finish: "Terminar",
        Discard: "Descartar",
        "in progress": "en curso",
        planned: "planeado",
        Insights: "Análisis",
        Refresh: "Actualizar",
        Daily: "Diario",
        Weekly: "Semanal",
        "Every 3 days": "Cada 3 días",
        Sealed: "Sellado",
        Open: "Abierto",
        Freezer: "Congelador",
        Finished: "Terminado",
        Thaw: "Descongelar",
        portions: "porciones",
        portion: "porcion",
        "This webapp gives you the full logging, rotation and insights experience. To save your data, connect your own free Google Sheet (2 min). Your data stays in your account.":
          "Esta webapp te da el registro, la rotación y el análisis completos. Para guardar tus datos, conecta tu propia Hoja de Google gratis (2 min). Tus datos quedan en tu cuenta.",
        "No sheet yet? You can still explore - dial-in advice works offline.":
          "¿Sin hoja aún? Puedes explorar - los consejos de ajuste funcionan sin conexión.",
        "You type dose, yield, time - and get history, trends and rotation. You do the logging.":
          "Tu escribes dosis, salida, tiempo - y obtienes historial, tendencias y rotación. Tu haces el registro.",
        "flow curve + yield captured live (no typing), flow-vs-rating insights a webapp can't compute.":
          "curva de flujo + salida capturadas en vivo (sin escribir), análisis flujo-vs-nota que una webapp no puede calcular.",
        "The more the device sees, the less you do - and the better it coaches.":
          "Cuánto más ve el dispositivo, menos haces tú - y mejor te aconseja.",
        "Beta: unlocking is on the honor system - device-key validation comes later.":
          "Beta: el desbloqueo es por confianza - la validación por clave llega después.",
        "Your live dial-in advice works without it.":
          "Tus consejos de ajuste en vivo funcionan sin ella.",
        "Log the last brew": "Registrar la ultima preparación",
        "none yet - log a brew": "aun ninguno - registra una preparación",
        "none yet - log a shot": "aun ninguno - registra un shot",
        "type your grind # (or um for Motto80) once, then chips appear":
          "escribe tu molienda # (o um para Motto80) una vez, y apareceran los botones",
        "Add a BLE scale ->": "Añade una báscula BLE ->",
        "Add a Gaggiuino ->": "Añade un Gaggiuino ->",
        "Your setup: Tier 0 - Manual": "Tu configuración: Nivel 0 - Manual",
        "Your setup: Tier 1 - BLE scale": "Tu configuración: Nivel 1 - Báscula BLE",
        "Your setup: Tier 2 - Gaggiuino": "Tu configuración: Nivel 2 - Gaggiuino",
      };
      function _rev(m) {
        var r = {};
        for (var k in m) {
          if (!(m[k] in r)) r[m[k]] = k;
        }
        return r;
      }
      var UIREV = _rev(UIDICT);
      function trWalk() {
        var m = LANG === "es" ? UIDICT : UIREV;
        var w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false),
          n,
          nodes = [];
        while ((n = w.nextNode())) nodes.push(n);
        nodes.forEach(function (tn) {
          /* never translate inside a translate="no" subtree: brand names, proper nouns.
      "Brew" is both a verb we translate and half of the product name. */
          var pe = tn.parentElement;
          while (pe) {
            if (pe.getAttribute && pe.getAttribute("translate") === "no") return;
            pe = pe.parentElement;
          }
          var raw = tn.nodeValue,
            v = raw.replace(/\s+/g, " ").trim();
          if (v && m[v] !== undefined && m[v] !== v) {
            var l = raw.match(/^\s*/)[0],
              tr = raw.match(/\s*$/)[0];
            tn.nodeValue = l + m[v] + tr;
          }
        });
        document.querySelectorAll("[placeholder]").forEach(function (el) {
          var v = (el.getAttribute("placeholder") || "").trim();
          if (v && m[v] !== undefined && m[v] !== v) el.setAttribute("placeholder", m[v]);
        });
      }

      /* rotation tooltips: title on each mode chip + a legend under them */
      var ROT_HELP = {
        fifo: {
          en: "Brew your oldest bag first, less waste.",
          es: "Prepara primero tu bolsa más vieja, menos desperdicio.",
        },
        variety: {
          en: "Pick a different bean than what is already open.",
          es: "Elige un grano distinto al que ya esta abierto.",
        },
        freshness: {
          en: "Pick beans in their peak rest window.",
          es: "Elige granos en su ventana optima de reposo.",
        },
        balanced: {
          en: "A mix of age, variety and freshness.",
          es: "Una mezcla de edad, variedad y frescura.",
        },
      };
      function rotTips() {
        var box = document.getElementById("rotmodechips");
        if (!box) return;
        if (box.children.length === 0 && typeof renderRotModes === "function") {
          try {
            renderRotModes();
          } catch (e) {}
        }
        var order = ["fifo", "variety", "freshness", "balanced"];
        Array.prototype.forEach.call(box.children, function (c, i) {
          var k = order[i];
          if (k && ROT_HELP[k]) c.title = "";
        });
      }

      /* settings-first onboarding: new users land on setup, not a log form */
      (function () {
        var done = false;
        try {
          done = !!localStorage.getItem("onboarded");
        } catch (e) {}
        if (typeof saveSetup === "function") {
          var _ss = saveSetup;
          saveSetup = function () {
            var r = _ss.apply(this, arguments);
            try {
              localStorage.setItem("onboarded", "1");
            } catch (e) {}
            return r;
          };
        }
        if (!done) {
          setTimeout(function () {
            /* A handoff outranks onboarding. By the time this timer fires,
     bpHandoff has already put the shot metrics into the log form and switched
     to that tab, so pulling the person to settings leaves the data sitting on
     a screen nobody is looking at. Onboarding is a guess that someone is new;
     a handoff is an explicit instruction to log THIS shot. The flag is left
     unset on purpose, so the next plain load still offers onboarding. */
            if (typeof BPSHOT !== "undefined" && BPSHOT) return;
            try {
              showTab("insights");
            } catch (e) {}
            try {
              openPanel("setPanel", toggleSettings);
            } catch (e) {}
            var w = document.getElementById("welcome");
            if (w) {
              var h = document.createElement("div");
              h.className = "mut";
              h.style.cssText = "text-align:left;margin:6px 0";
              h.textContent =
                LANG === "es"
                  ? "Empieza aqui: elige lo que preparas y tu equipo. Solo quieres inventario? Tambien funciona."
                  : "Start here: pick what you brew and your gear. Just want inventory? That works too.";
            }
          }, 400);
        }
      })();

      applyLang();

      /* SHEET_TEMPLATE_URL REMOVED with /exec. The copy-a-template step belonged to the
   legacy flow; the app creates its own sheet through drive.file now. Leaving the
   link would invite people onto a path that no longer has a backend.
   NOTE: update.ps1 hard-required this string and would STOP the publish without
   it. That check is removed in the same pass. */
      /* wizTemplateLink deleted outright with the wizard rewrite. It was already an
   empty stub after the /exec cut; now even its caller is gone. */

      /* WIZ_SHOTS / wizShots REMOVED with the wizard rewrite. They lazy-loaded
   setup1-copy.png ... setup5-url.png, screenshots of copying a template and
   deploying an Apps Script web app. Those steps are gone, so shot1..shot5 no
   longer exist and getElementById('shot1') would have been a dead lookup -
   audit.py check 1 would have failed the build. */

      /* wizard step 1: role + methods + hardware + grinders, reusing the real app state */
      function wizRender() {
        var rb = document.getElementById("wizRole");
        if (!rb) return;
        rb.innerHTML = "";
        [
          ["full", "roleBrew"],
          ["logmgr", "roleInv"],
        ].forEach(function (m) {
          var c = document.createElement("div");
          c.textContent = t(m[1]);
          c.className = "chip" + (ROLE === m[0] ? " on" : "");
          c.onclick = function () {
            setRole(m[0]);
            wizRender();
          };
          rb.appendChild(c);
        });
        var mw = document.getElementById("wizMethodWrap");
        if (mw) mw.style.display = ROLE === "logmgr" ? "none" : "";
        var mb = document.getElementById("wizMethods");
        if (mb) {
          mb.innerHTML = "";
          [
            [
              "esp",
              "mEsp",
              function () {
                return M_ESP;
              },
              function (v) {
                M_ESP = v;
              },
            ],
            [
              "soup",
              "mSoup",
              function () {
                return M_SOUP;
              },
              function (v) {
                M_SOUP = v;
              },
            ],
            [
              "fil",
              "mFil",
              function () {
                return M_FIL;
              },
              function (v) {
                M_FIL = v;
              },
            ],
          ].forEach(function (m) {
            var c = document.createElement("div");
            c.textContent = t(m[1]);
            c.className = "chip" + (m[2]() ? " hi on" : "");
            c.onclick = function () {
              m[3](!m[2]());
              localStorage.setItem(
                "waMethods",
                JSON.stringify({ esp: M_ESP, soup: M_SOUP, fil: M_FIL }),
              );
              try {
                applyNoun();
              } catch (e) {}
              try {
                renderTier();
              } catch (e) {}
              wizRender();
              homeRender();
            };
            mb.appendChild(c);
          });
        }
        var hb = document.getElementById("wizHw");
        if (hb) {
          hb.innerHTML = "";
          [
            ["none", "hwNone"],
            ["scale", "hwScale"],
            ["gaggiuino", "hwGag"],
          ].forEach(function (h) {
            var c = document.createElement("div");
            c.textContent = t(h[1]);
            c.className = "chip" + (M_HW === h[0] ? " on" : "");
            c.onclick = function () {
              if (h[0] === "scale" || h[0] === "gaggiuino") {
                try {
                  hwModal(h[0]);
                } catch (e) {}
              }
              M_HW = h[0];
              M_SCALE = h[0] === "scale";
              M_GAG = h[0] === "gaggiuino";
              localStorage.setItem("waHw", h[0]);
              try {
                applyHwLocks();
              } catch (e) {}
              try {
                renderTier();
              } catch (e) {}
              wizRender();
              homeRender();
            };
            hb.appendChild(c);
          });
        }
        var espNote = document.getElementById("wizEspNote");
        if (espNote) {
          var owned0 = [];
          try {
            owned0 = JSON.parse(localStorage.getItem("myGrinders") || "[]");
          } catch (e) {}
          var bad = owned0.filter(function (id) {
            return GRINDERS[id] && GRINDERS[id].esp === false;
          });
          if ((M_ESP || M_SOUP) && bad.length) {
            espNote.style.display = "";
            espNote.textContent = t("espWarn").replace(
              "{g}",
              bad
                .map(function (id) {
                  return GRINDERS[id].n;
                })
                .join(", "),
            );
          } else espNote.style.display = "none";
        }
        var gb = document.getElementById("wizGrinders");
        if (gb && typeof GRINDERS === "object") {
          gb.innerHTML = "";
          var owned = [];
          try {
            owned = JSON.parse(localStorage.getItem("myGrinders") || "[]");
          } catch (e) {}
          Object.keys(GRINDERS).forEach(function (id) {
            var c = document.createElement("div");
            c.textContent = GRINDERS[id].n;
            var on = owned.indexOf(id) >= 0;
            c.className = "chip xs" + (on ? " hi on" : "");
            c.onclick = function () {
              var i = owned.indexOf(id);
              if (i >= 0) owned.splice(i, 1);
              else owned.push(id);
              localStorage.setItem("myGrinders", JSON.stringify(owned));
              try {
                renderMyGrinders();
              } catch (e) {}
              try {
                renderGrinderChips();
              } catch (e) {}
              wizRender();
            };
            gb.appendChild(c);
          });
        }
      }

      /* localized tier card (replaces the concat version so it cannot fight the translator) */
      var TIERTXT = {
        en: [
          [
            "Tier 0 - Manual",
            "You type dose, yield, time. You get history, trends and rotation.",
            "Add a BLE scale",
            "Weight, yield and flow captured live, no typing.",
          ],
          [
            "Tier 1 - BLE scale",
            "Your scale captures weight, yield and live flow. No typing.",
            "Add a Gaggiuino",
            "Every shot auto-logs pressure, flow and temp; the device coaches mid-pull.",
          ],
          [
            "Tier 2 - Gaggiuino",
            "Every shot auto-logs pressure, flow and temp. Zero effort. Top of the ladder.",
            "",
            "",
          ],
        ],
        es: [
          [
            "Nivel 0 - Manual",
            "Tu escribes dosis, salida y tiempo. Obtienes historial, tendencias y rotación.",
            "Añade una báscula BLE",
            "Peso, salida y flujo capturados en vivo, sin escribir.",
          ],
          [
            "Nivel 1 - Báscula BLE",
            "Tu báscula captura peso, salida y flujo en vivo. Sin escribir.",
            "Añade un Gaggiuino",
            "Cada shot registra presión, flujo y temperatura solo; el dispositivo te guia.",
          ],
          [
            "Nivel 2 - Gaggiuino",
            "Cada shot registra presión, flujo y temperatura solo. Cero esfuerzo. Lo maximo.",
            "",
            "",
          ],
        ],
      };
      function renderTier() {
        var el = document.getElementById("tierCard");
        if (!el) return;
        if (typeof TIERTXT === "undefined" || typeof LANG === "undefined") return;
        var tier =
          typeof M_GAG !== "undefined" && M_GAG
            ? 2
            : typeof M_SCALE !== "undefined" && M_SCALE
              ? 1
              : 0;
        var set = TIERTXT[LANG] || TIERTXT.en;
        var d = set[tier] || set[0];
        if (!d) return;
        var h =
          "<div style='color:var(--hi-text);font-size:13px;font-weight:600'>" +
          (LANG === "es" ? "Tu configuración: " : "Your setup: ") +
          d[0] +
          "</div>";
        h += "<div style='color:var(--dim);font-size:12px;margin:4px 0 8px'>" + d[1] + "</div>";
        if (d[2]) {
          var topic = tier === 0 ? "scale" : "gaggiuino";
          h +=
            "<div class='tierUp' data-topic='" +
            topic +
            "' style='color:var(--sel-text);font-size:12px;font-weight:600;cursor:pointer'>" +
            d[2] +
            " -></div>";
          h += "<div style='color:var(--dim);font-size:12px'>" + d[3] + "</div>";
        }
        /* live nudges are device-only at every tier, so they get their own entry */
        if (tier < 2 || !(typeof M_HW !== "undefined" && M_HW === "device")) {
          h +=
            "<div class='tierUp' data-topic='nudges' style='color:var(--sel-text);font-size:12px;font-weight:600;cursor:pointer;margin-top:6px'>" +
            (LANG === "es" ? "Avisos en vivo mientras preparas" : "Live nudges while you brew") +
            " -></div>";
        }
        el.innerHTML = h;
        Array.prototype.forEach.call(el.querySelectorAll(".tierUp"), function (a) {
          a.onclick = function () {
            try {
              hwModal(a.getAttribute("data-topic"));
            } catch (e) {}
          };
        });
      }

      /* method-agnostic home: no espresso assumption, adapts to role + what you brew */
      function homeExtra() {
        var box = document.getElementById("homeExtra");
        if (!box) return;
        var isEs = typeof LANG !== "undefined" && LANG === "es";
        var inv = (typeof IINV !== "undefined" && IINV ? IINV : []).filter(function (r) {
          return String(r.status || "") !== "Finished" && String(r.coffee || "").trim();
        });
        var html = "";
        /* today: prefer bags at peak, then nearing, tie-broken by your own average */
        var best = null;
        inv.forEach(function (r) {
          var rs = null;
          try {
            rs = restStatus(r.roast || "Light", r.process || "", restDefaultMethod(), r.roast_date);
          } catch (e) {}
          var sc = 0;
          if (rs) {
            sc =
              rs.phase === "in peak"
                ? 3
                : rs.phase === "nearing peak"
                  ? 2
                  : rs.phase === "past peak"
                    ? 1
                    : 0;
          }
          var a = null;
          try {
            a = coffeeAvg(r.coffee);
          } catch (e) {}
          var tot = sc * 10 + (a && a.avg ? a.avg : 0);
          if (!best || tot > best.tot) best = { tot: tot, coffee: r.coffee, rs: rs, avg: a };
        });
        if (best) {
          var why = "";
          if (best.rs && best.rs.age != null) {
            if (best.rs.phase === "in peak") why = isEs ? "en su punto" : "at peak";
            else if (best.rs.phase === "nearing peak" || best.rs.phase === "resting")
              why = (isEs ? "pico en " : "peak in ") + dWeeks(best.rs.w.peakLo - best.rs.age, isEs);
            else why = isEs ? "pasado el pico" : "past peak";
          }
          if (best.avg && best.avg.n)
            why += (why ? " · " : "") + best.avg.avg + (isEs ? " prom" : " avg");
          html +=
            "<div class='tool'><div class='toolhd'>" +
            (isEs ? "Hoy" : "Today") +
            "</div><div style='font-size:15px;font-weight:600'>" +
            best.coffee +
            "</div><div style='color:var(--dim);font-size:12px;margin-top:2px'>" +
            why +
            "</div></div>";
        }
        /* rotation */
        var rot = typeof ROT !== "undefined" && ROT ? ROT : [];
        if (rot.length) {
          var items = rot
            .slice(0, 5)
            .map(function (e) {
              var a = null;
              try {
                a = coffeeAvg(e.coffee);
              } catch (err) {}
              return (
                "<div style='display:flex;justify-content:space-between;gap:8px;padding:4px 0;font-size:13px'><span>" +
                e.coffee +
                "</span><span style='color:var(--dim)'>" +
                (a && a.n ? a.avg : "") +
                "</span></div>"
              );
            })
            .join("");
          html +=
            "<div class='tool'><div class='toolhd'>" +
            (isEs ? "Rotación" : "Rotation") +
            "</div>" +
            items +
            "</div>";
        }
        /* inventory */
        if (inv.length) {
          var seen = {},
            frozen = 0,
            resting = 0,
            using = 0;
          inv.forEach(function (r) {
            seen[String(r.coffee).toLowerCase()] = 1;
            var st = String(r.status || "");
            if (st === "Resting") resting++;
            else if (st === "Open") using++;
            else frozen++;
          });
          var n = Object.keys(seen).length;
          html +=
            "<div class='tool'><div class='toolhd'>" +
            t("homeInv") +
            "</div><div style='font-size:13px'>" +
            n +
            " " +
            (isEs ? "cafés" : "coffees") +
            "</div><div style='color:var(--dim);font-size:12px;margin-top:3px'>" +
            frozen +
            " " +
            (isEs ? "congeladas" : "frozen") +
            " · " +
            resting +
            " " +
            (isEs ? "reposando" : "resting") +
            " · " +
            using +
            " " +
            (isEs ? "en uso" : "in use") +
            "</div></div>";
        }
        box.innerHTML = html;
      }
      function homeRender() {
        try {
          homeExtra();
        } catch (e) {}
        var phase = document.getElementById("heroPhase"),
          sub = document.getElementById("heroSub"),
          num = document.getElementById("heroNum");
        if (!phase) return;
        var noun = LNOUN();
        if (ROLE === "logmgr") {
          /* The bag count, finally. INV never existed, so this always showed '--' and
      "no sheet connected" even on Drive. loadInventory() already had the real
      list and threw the count away; it now caches it in INVN.
      '--' means UNKNOWN and 0 means EMPTY. Those are different, so an unloaded
      inventory does not claim zero. */
          phase.textContent = t("homeInv");
          if (typeof INVN === "number") {
            num.textContent = String(INVN);
            sub.textContent = INVN + " " + (LANG === "es" ? "cafés" : "coffees");
          } else {
            num.textContent = "--";
            sub.textContent = dataMode() === "google" ? t("homeLoading") : t("noSheetYet");
          }
          return;
        }
        var ratings = [];
        (typeof IROWS !== "undefined" ? IROWS : []).forEach(function (o) {
          var r = parseFloat(o.rating);
          if (!isNaN(r) && r > 0) ratings.push(r);
        });
        ratings.reverse();
        if (!ratings.length) {
          phase.textContent = t("homeNone");
          sub.textContent = LANG === "es" ? "registra tu primer " + noun : "log your first " + noun;
          num.textContent = "--";
          return;
        }
        phase.textContent = t("lastRating");
        sub.textContent = ratings.length + " " + t("homeLogged");
        num.textContent = ratings[0];
      }

      function LNOUN() {
        var f = !M_ESP && !M_SOUP && M_FIL;
        if (LANG === "es") return f ? "filtrado" : "shot";
        return f ? "brew" : "shot";
      }
      function noSheetMsg() {
        var es = LANG === "es";
        return (
          "<div style='text-align:left;font-size:12px;color:var(--dim);line-height:1.5'>" +
          (es
            ? "El inventario, el historial y las tendencias se guardan en tu Hoja de Google. Conecta una en <b>Ajustes</b> (o el asistente) para activarlo. Tus consejos de ajuste en vivo funcionan sin ella."
            : "Inventory, history and trends are saved to your Google Sheet. Connect one in <b>Settings</b> (or the setup wizard) to enable this. Your live dial-in advice works without it.") +
          "</div>"
        );
      }

      /* local buffer: every logged row is mirrored here so nothing is lost before a sheet exists */
      function localRows() {
        try {
          return JSON.parse(localStorage.getItem("localRows") || "[]");
        } catch (e) {
          return [];
        }
      }
      function localPush(row) {
        try {
          var a = localRows();
          a.push({ t: Date.now(), row: row });
          if (a.length > 4000) a = a.slice(-4000);
          localStorage.setItem("localRows", JSON.stringify(a));
        } catch (e) {}
      }
      function exportLocal() {
        var a = localRows();
        if (!a.length) {
          alert(LANG === "es" ? "Aun no hay nada que exportar." : "Nothing to export yet.");
          return;
        }
        var blob = new Blob(
          [JSON.stringify({ exported: new Date().toISOString(), rows: a }, null, 1)],
          { type: "application/json" },
        );
        var u = URL.createObjectURL(blob),
          d = document.createElement("a");
        d.href = u;
        d.download = "brewpilot-backup-" + new Date().toISOString().slice(0, 10) + ".json";
        document.body.appendChild(d);
        d.click();
        d.remove();
        setTimeout(function () {
          URL.revokeObjectURL(u);
        }, 400);
      }

      /* mirror logshot/logFilter into the buffer without touching their sheet path */
      /* REMOVED 2026-07-16 with the logFilter port.
   This wrapper predates both write-path ports. It mirrored a brew into localRows
   as {coffee, when} - an OBJECT, where iFromLocal's rows.map(x=>x.row) hands the
   value straight to iBuild, which does ICOLS.forEach((c,i)=>o[c]=r[i]) and gets
   undefined for all 23 columns off an object. It also read #coffee first, which is
   the ESPRESSO field, so a filter brew mirrored an empty name.
   Once logshot got localPush(cols) last session, every espresso brew wrote TWO
   rows: one real array[23] and one junk object. localRows().length feeds the
   durability banner's brew count, so that count has been reading 2x the truth.
   Measured: logshot -> localRows +2, both shapes present.
   Nothing reads .row.coffee or .when - grepped, zero hits - so the object rows
   have no consumer and this is a clean delete. logshot and logFilter both call
   localPush(cols) themselves now, which is the correct shape and exactly once. */

      /* the banner: honest either way, and it does not hide */
      function duraRender() {
        var el = document.getElementById("duraBanner");
        if (!el) return;
        var connected = false;
        try {
          connected = dataMode() !== "local";
        } catch (e) {}
        var n = localRows().length;
        /* visibility is decided by sheetCtas(), which enforces one prompt at a time.
    duraRender only fills in the text. */
        var hd = el.querySelector(".durahd b"),
          bd = el.querySelector(".durab"),
          cnt = document.getElementById("duraCount"),
          row = el.querySelector(".durarow");
        if (connected) {
          el.classList.add("durasafe");
          hd.textContent = t("duraSafeT");
          bd.textContent = t("duraSafeB");
          row.style.display = "none";
          cnt.textContent = "";
          return;
        }
        el.classList.remove("durasafe");
        row.style.display = "";
        hd.textContent = t("duraT");
        bd.textContent = t("duraB");
        cnt.textContent = n ? n + " " + t("duraN") : "";
      }

      /* insights: say plainly that the sheet makes them better */

      /* ---- insights are a sheet feature: honest lock, not a tease ---- */
      function insGate() {
        var p = document.getElementById("insPanel");
        if (!p) return; /* Insights are computed in the browser from localRows now, so a sheet is no
   longer required to have something to say. Any logged brew unlocks them.
   The sheet upsell moves to durability and sync: an honest pitch instead of
   a tollgate standing in front of the value. */

        var connected = false;
        try {
          connected = dataMode() !== "local";
        } catch (e) {}
        try {
          if (!connected && localRows().length > 0) connected = true;
        } catch (e) {}

        var lock = document.getElementById("insLock");
        var kids = Array.prototype.filter.call(p.children, function (c) {
          return c.id !== "insLock";
        });
        if (connected) {
          if (lock) lock.remove();
          kids.forEach(function (c) {
            c.style.display = "";
          });
          return;
        }
        kids.forEach(function (c) {
          c.style.display = "none";
        });
        if (!lock) {
          lock = document.createElement("div");
          lock.id = "insLock";
          lock.className = "inslock";
          p.appendChild(lock);
        }
        lock.innerHTML =
          "<div class='inslockT'>" +
          t("insLockT") +
          "</div><div class='inslockB'>" +
          t("insLockB") +
          "</div>";
        var btn = document.createElement("button");
        btn.className = "grn";
        btn.style.cssText = "width:100%;margin-top:12px";
        btn.textContent = t("insLockGo");
        btn.onclick = function () {
          document.getElementById("wizMask").classList.add("on");
        };
        lock.appendChild(btn);
      }

      /* ---- cold start: contextual, roast-aware, one brewer, where you actually grind ---- */
      var ROAST_F = {
        "Ultra Light": 0.9,
        "Extra Light": 0.94,
        Light: 1.0,
        "Light Medium": 1.04,
        Medium: 1.08,
        "Medium Dark": 1.13,
        Dark: 1.18,
      };
      var REST_TIER = {
        "Ultra Light": "ultra",
        "Extra Light": "ultra",
        Light: "light",
        "Light Medium": "light",
        Medium: "medium",
        "Medium Dark": "medium",
        Dark: "dark",
      };
      var REST_W = {
        espresso: {
          ultra: [14, 21, 28],
          light: [10, 18, 28],
          medium: [7, 12, 21],
          dark: [2, 3, 8],
        },
        filter: { ultra: [10, 21, 56], light: [7, 14, 42], medium: [5, 10, 28], dark: [3, 5, 10] },
      };
      function restWindow(roast, process, method) {
        var tier = REST_TIER[roast];
        if (!tier) return null;
        var fam = method === "espresso" ? "espresso" : "filter";
        var w = REST_W[fam][tier].slice();
        var pr = String(process || "");
        /* Hydrangea (published): shorter rest for process-forward coffees, longer for
     traditionally processed. That is the opposite of the old assumption. */
        var exp = /natural|anaerob|honey|carbonic|ferment|maceration|co-?ferment/i.test(pr);
        var trad = /washed|lavado|lavat/i.test(pr);
        var pn = exp ? -3 : trad ? 3 : 0;
        var st = Math.max(1, w[0] + pn),
          lo = Math.max(st, w[1] + pn),
          hi = Math.max(lo, w[2] + pn);
        return { start: st, peakLo: lo, peakHi: hi, tier: tier, family: fam, exp: exp, trad: trad };
      }
      function restDaysSince(dateStr) {
        var s = String(dateStr || "").slice(0, 10);
        if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
        var d = new Date(s + "T00:00:00");
        if (isNaN(d.getTime())) return null;
        return Math.floor((Date.now() - d.getTime()) / 86400000);
      }
      function restDefaultMethod() {
        try {
          if (typeof M_ESP !== "undefined" && M_ESP && !M_SOUP && !M_FIL) return "espresso";
        } catch (e) {}
        return "filter";
      }
      function restStatus(roast, process, method, roastDate) {
        var w = restWindow(roast, process, method);
        if (!w) return null;
        var age = restDaysSince(roastDate);
        var phase =
          age == null
            ? "unknown"
            : age < w.start
              ? "resting"
              : age < w.peakLo
                ? "nearing peak"
                : age <= w.peakHi
                  ? "in peak"
                  : "past peak";
        return { w: w, age: age, phase: phase };
      }
      function invSizeFree() {
        var e = document.getElementById("invsizeg");
        if (!e) return;
        var v = parseFloat(e.value);
        if (!isNaN(v) && v > 0) {
          INVSIZE = Math.round(v * 10) / 10 + "g";
          try {
            renderInvSizes();
          } catch (err) {}
        }
      }
      function dWeeks(d, isEs) {
        /* Windows now run to 8 weeks, and '45d' is hard to read at a glance. */
        d = Math.max(0, Math.round(d));
        if (d < 14) return d + "d";
        var w = Math.floor(d / 7),
          r = d % 7,
          u = isEs ? " sem" : "w";
        return r ? w + u + " " + r + "d" : w + u;
      }
      function dParse(v) {
        /* Rows written before the freeze-date field settled carry values like
     '2026-05-26 0:00'. replace(' ','T') makes that invalid ISO (one-digit hour)
     and Date.parse returns NaN, so legacy bags showed no freeze age at all.
     Take the date head and ignore whatever follows. */
        var s = String(v || "")
          .trim()
          .slice(0, 10);
        if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return NaN;
        var t = Date.parse(s + "T00:00:00");
        return isFinite(t) ? t : NaN;
      }
      function bagFreezeAge(b) {
        /* days since frozen + how old the bag was when it went in. FIFO helper. */
        var isEs = typeof LANG !== "undefined" && LANG === "es";
        var best = null,
          rd = null;
        (b.portions || []).forEach(function (p) {
          var f = dParse(p.freeze_date);
          if (isFinite(f) && (best === null || f < best)) {
            best = f;
            rd = dParse(p.roast_date);
          }
        });
        if (best === null) return "";
        var d = Math.floor((Date.now() - best) / 86400000);
        if (d < 0 || d > 3650) return "";
        var txt = (isEs ? "congelado hace " : "frozen ") + dWeeks(d, isEs) + (isEs ? "" : " ago");
        if (isFinite(rd)) {
          var at = Math.floor((best - rd) / 86400000);
          if (at >= 0 && at < 3650)
            txt += isEs
              ? " (a los " + dWeeks(at, isEs) + " de tostado)"
              : " (at " + dWeeks(at, isEs) + " old)";
        }
        return txt;
      }
      async function gEnsureHeader(tab, want) {
        /* Sheets created before a column was added still carry the old header, and
     both gInvList and gPatchRow key off that header - so a value for a missing
     column is dropped without any error. Missing names are appended at the end;
     nothing is renamed, reordered or removed, so existing data cannot shift. */
        try {
          var rows = await gRead(tab);
          if (!rows || !rows.length || !rows[0] || !rows[0].length) return false;
          var head = rows[0].slice(),
            have = {};
          head.forEach(function (h) {
            have[String(h).trim()] = 1;
          });
          var added = false;
          want.forEach(function (c) {
            if (!have[c]) {
              head.push(c);
              added = true;
            }
          });
          if (added) await gUpdate(tab, 1, head);
          return added;
        } catch (e) {
          return false;
        }
      }
      async function gMigrateHeaders() {
        if (dataMode() !== "google") return;
        var a = await gEnsureHeader(SHOT_TAB, COLNAMES);
        var b = await gEnsureHeader(INV_TAB, INV_COLNAMES);
        if (a || b) {
          try {
            await iLoad();
          } catch (e) {}
          try {
            loadInventory();
          } catch (e) {}
        }
      }
      async function gPatchRow(tab, row1, patch) {
        /* Replace ONLY the named columns on an existing row. Every other column is
     copied back verbatim, so nothing can shift and no row is ever rebuilt. */
        var rows = await gRead(tab);
        if (!rows.length) return false;
        var head = rows[0],
          cur = rows[row1 - 1] || [];
        var out = head.map(function (h, i) {
          return Object.prototype.hasOwnProperty.call(patch, String(h))
            ? patch[String(h)]
            : cur[i] !== undefined
              ? cur[i]
              : "";
        });
        await gUpdate(tab, row1, out);
        return true;
      }
      function editOverlay(title, fields, onSave) {
        var ov = document.createElement("div");
        ov.style.cssText =
          "position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;overflow:auto";
        var card = document.createElement("div");
        card.style.cssText =
          "background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;max-width:420px;width:100%;color:var(--text);max-height:88vh;overflow:auto";
        var h = document.createElement("div");
        h.textContent = title;
        h.style.cssText = "font-weight:600;margin-bottom:4px";
        card.appendChild(h);
        var inputs = {};
        fields.forEach(function (f) {
          var l = document.createElement("div");
          l.textContent = f.label;
          l.style.cssText = "color:var(--dim);font-size:11px;margin-top:9px";
          card.appendChild(l);
          if (f.options && f.options.length) {
            var isEs2 = typeof LANG !== "undefined" && LANG === "es";
            var sel = document.createElement("select");
            sel.className = "fin";
            sel.style.width = "100%";
            var cur = f.v == null ? "" : String(f.v).trim();
            var blank = document.createElement("option");
            blank.value = "";
            blank.textContent = isEs2 ? "elige..." : "choose...";
            sel.appendChild(blank);
            var opts = f.options.slice();
            if (cur && opts.indexOf(cur) < 0) opts.unshift(cur);
            opts.forEach(function (o) {
              var e = document.createElement("option");
              e.value = o;
              e.textContent = o;
              if (o === cur) e.selected = true;
              sel.appendChild(e);
            });
            var oth = document.createElement("option");
            oth.value = "__other__";
            oth.textContent = isEs2 ? "+ escribir otro..." : "+ type another...";
            sel.appendChild(oth);
            sel.onchange = function () {
              if (sel.value !== "__other__") return;
              var ti = document.createElement("input");
              ti.className = "fin";
              ti.style.width = "100%";
              ti.value = "";
              if (sel.parentNode) sel.parentNode.replaceChild(ti, sel);
              inputs[f.k] = ti;
              try {
                ti.focus();
              } catch (e) {}
            };
            card.appendChild(sel);
            inputs[f.k] = sel;
          } else {
            var i = document.createElement("input");
            i.className = "fin";
            i.style.width = "100%";
            if (f.type) i.type = f.type;
            if (f.step) i.setAttribute("step", f.step);
            i.value = f.v == null ? "" : String(f.v);
            card.appendChild(i);
            inputs[f.k] = i;
          }
        });
        var row = document.createElement("div");
        row.style.cssText = "display:flex;gap:8px;margin-top:14px";
        var sv = document.createElement("button");
        sv.textContent = t("editSave");
        sv.style.cssText =
          "flex:1;padding:11px;border-radius:10px;border:1px solid var(--sel-line);background:var(--sel-bg);color:var(--sel-text);font-weight:600;cursor:pointer";
        sv.onclick = async function () {
          var out = {};
          Object.keys(inputs).forEach(function (k) {
            out[k] = inputs[k].value;
          });
          sv.disabled = true;
          sv.textContent = t("editSaving");
          try {
            await onSave(out);
            if (ov.parentNode) ov.parentNode.removeChild(ov);
          } catch (e) {
            sv.disabled = false;
            sv.textContent = t("editSave");
            alert(t("editFail"));
          }
        };
        var cx = document.createElement("button");
        cx.textContent = t("scoreCancel");
        cx.style.cssText =
          "padding:11px 14px;border-radius:10px;border:1px solid var(--line);background:var(--panel);color:var(--dim);cursor:pointer";
        cx.onclick = function () {
          if (ov.parentNode) ov.parentNode.removeChild(ov);
        };
        row.appendChild(sv);
        row.appendChild(cx);
        card.appendChild(row);
        ov.appendChild(card);
        document.body.appendChild(ov);
      }
      async function gBagState(coffee, loc, status) {
        var rows = await gRead(INV_TAB);
        if (rows.length < 2) return false;
        var head = rows[0],
          idx = {};
        head.forEach(function (h, i) {
          idx[String(h)] = i;
        });
        var hit = false;
        for (var r = 1; r < rows.length; r++) {
          var row = rows[r];
          if (String(row[idx["coffee"]] || "").toLowerCase() !== String(coffee || "").toLowerCase())
            continue;
          if (String(row[idx["status"]] || "") === "Finished") continue;
          if (idx["location"] !== undefined) row[idx["location"]] = loc;
          if (idx["status"] !== undefined) row[idx["status"]] = status;
          await gUpdate(INV_TAB, r + 1, row);
          hit = true;
        }
        return hit;
      }
      function rotEnsure(name) {
        if (typeof ROT === "undefined" || !ROT) return false;
        var n = String(name || "").trim();
        if (!n) return false;
        if (
          ROT.some(function (x) {
            return String(x.coffee || "").toLowerCase() === n.toLowerCase();
          })
        )
          return false;
        ROT.push({ coffee: n });
        try {
          saveRot();
        } catch (e) {}
        try {
          renderChips();
        } catch (e) {}
        try {
          addCoffeeName(n);
        } catch (e) {}
        try {
          homeExtra();
        } catch (e) {}
        return true;
      }
      function bagSet(b, loc, status) {
        if (dataMode() !== "google") {
          alert(t("editNeedSheet"));
          return;
        }
        gBagState(b.coffee, loc, status).then(function () {
          if (status === "Open") {
            try {
              rotEnsure(b.coffee);
            } catch (e) {}
          }
          try {
            loadInventory();
          } catch (e) {}
        });
      }
      function labelDate(v, withYear) {
        var t = dParse(v);
        if (!isFinite(t)) return "";
        var d = new Date(t),
          p = function (n) {
            return (n < 10 ? "0" : "") + n;
          };
        return (
          p(d.getDate()) +
          "/" +
          p(d.getMonth() + 1) +
          (withYear ? "/" + String(d.getFullYear()).slice(2) : "")
        );
      }
      function logoKey(r) {
        return String(r || "")
          .trim()
          .toLowerCase();
      }
      function logoGet(r) {
        try {
          return JSON.parse(localStorage.getItem("roasterLogos") || "{}")[logoKey(r)] || "";
        } catch (e) {
          return "";
        }
      }
      function logoSet(r, url) {
        try {
          var m = JSON.parse(localStorage.getItem("roasterLogos") || "{}");
          if (url) m[logoKey(r)] = url;
          else delete m[logoKey(r)];
          localStorage.setItem("roasterLogos", JSON.stringify(m));
        } catch (e) {
          alert(t("logoTooBig"));
        }
      }
      function logoThreshold(img, maxW, forceInvert) {
        /* A thermal head is 1-bit. The hard part is deciding which pixels are ink.
     Averaging every opaque pixel fails on the common case, a logo on a solid
     white background, because the background dominates the mean and the whole
     image gets inverted. The background is estimated from the border ring
     instead; artwork is whatever differs from it. Fully transparent borders
     fall back to the mean of the opaque pixels. */
        var w = img.naturalWidth || img.width,
          h = img.naturalHeight || img.height;
        if (!w || !h) return "";
        var sc = Math.min(1, maxW / w),
          W = Math.max(1, Math.round(w * sc)),
          H = Math.max(1, Math.round(h * sc));
        var c = document.createElement("canvas");
        c.width = W;
        c.height = H;
        var x = c.getContext("2d");
        x.drawImage(img, 0, 0, W, H);
        var d = x.getImageData(0, 0, W, H),
          p = d.data;
        var lum = function (k) {
          return 0.299 * p[k] + 0.587 * p[k + 1] + 0.114 * p[k + 2];
        };
        var bs = 0,
          bn = 0,
          be = 0,
          os = 0,
          on = 0,
          yy,
          xx,
          k;
        for (yy = 0; yy < H; yy++) {
          for (xx = 0; xx < W; xx++) {
            k = (yy * W + xx) * 4;
            if (p[k + 3] > 40) {
              os += lum(k);
              on++;
            }
            if (yy < 2 || yy > H - 3 || xx < 2 || xx > W - 3) {
              be++;
              if (p[k + 3] > 40) {
                bs += lum(k);
                bn++;
              }
            }
          }
        }
        var darkInk, thr;
        if (be && bn / be > 0.2) {
          /* solid background: compare against it */
          var bg = bs / bn;
          darkInk = bg > 128;
          thr = darkInk ? Math.max(70, bg - 45) : Math.min(190, bg + 45);
        } else {
          /* transparent cut-out: judge the artwork */
          var mean = on ? os / on : 255;
          darkInk = !(mean > 170);
          thr = darkInk ? 165 : 128;
        }
        if (forceInvert) darkInk = !darkInk;
        for (k = 0; k < p.length; k += 4) {
          if (p[k + 3] < 40) {
            p[k + 3] = 0;
            continue;
          }
          var l = lum(k),
            ink = darkInk ? l < thr : l > thr;
          if (ink) {
            p[k] = 0;
            p[k + 1] = 0;
            p[k + 2] = 0;
            p[k + 3] = 255;
          } else {
            p[k + 3] = 0;
          }
        }
        x.putImageData(d, 0, 0);
        /* Whatever margin the source had is transparent now but still occupies the
     canvas, and drawImage would scale that empty border into the label box,
     making the artwork look tiny. Crop to the ink bounding box. */
        var mnx = W,
          mny = H,
          mxx = -1,
          mxy = -1;
        for (yy = 0; yy < H; yy++) {
          for (xx = 0; xx < W; xx++) {
            k = (yy * W + xx) * 4;
            if (p[k + 3] > 0) {
              if (xx < mnx) mnx = xx;
              if (xx > mxx) mxx = xx;
              if (yy < mny) mny = yy;
              if (yy > mxy) mxy = yy;
            }
          }
        }
        if (mxx < mnx || mxy < mny) return "";
        var cw = mxx - mnx + 1,
          ch = mxy - mny + 1;
        if (cw < W || ch < H) {
          var c2 = document.createElement("canvas");
          c2.width = cw;
          c2.height = ch;
          c2.getContext("2d").drawImage(c, mnx, mny, cw, ch, 0, 0, cw, ch);
          return c2.toDataURL("image/png");
        }
        return c.toDataURL("image/png");
      }
      function logoFlip(r) {
        /* The stored logo is already 1-bit, so flipping the mask is exact and needs
     no reprocessing of the original. */
        var url = logoGet(r);
        if (!url) return;
        var im = new Image();
        im.onload = function () {
          var c = document.createElement("canvas");
          c.width = im.width;
          c.height = im.height;
          var x = c.getContext("2d");
          x.drawImage(im, 0, 0);
          var d = x.getImageData(0, 0, c.width, c.height),
            p = d.data;
          for (var k = 0; k < p.length; k += 4) {
            if (p[k + 3] < 40) {
              p[k] = 0;
              p[k + 1] = 0;
              p[k + 2] = 0;
              p[k + 3] = 255;
            } else {
              p[k + 3] = 0;
            }
          }
          x.putImageData(d, 0, 0);
          logoSet(r, c.toDataURL("image/png"));
          try {
            LOGO_FLIP_CB && LOGO_FLIP_CB();
          } catch (e) {}
        };
        im.src = url;
      }
      var LOGO_FLIP_CB = null;
      function bagMeta(b) {
        /* Varietal and origin live on the bag now. Bags saved before that can still
     borrow them from the newest brew of the same coffee, so the log-to-bag
     direction works without migrating anything. */
        var v = String(b.varietal || "").trim(),
          r = String(b.region || "").trim();
        if (v && r) return { varietal: v, region: r };
        try {
          var key = String(b.coffee || "")
              .trim()
              .toLowerCase(),
            rows = typeof IROWS !== "undefined" ? IROWS : [];
          for (var i = rows.length - 1; i >= 0; i--) {
            var o = rows[i];
            if (
              String(o.coffee || "")
                .trim()
                .toLowerCase() !== key
            )
              continue;
            if (!v) v = String(o.varietal || "").trim();
            if (!r) r = String(o.region || "").trim();
            if (v && r) break;
          }
        } catch (e) {}
        return { varietal: v, region: r };
      }
      var LBL_PORTION = "";
      var LBL_DEF = {
        coffee: 1,
        process: 1,
        roastlvl: 0,
        varietal: 1,
        region: 1,
        roast: 1,
        freeze: 1,
        peak: 1,
        portion: 0,
      };
      function lblFields() {
        try {
          var m = JSON.parse(localStorage.getItem("labelFields") || "null");
          if (m && typeof m === "object") {
            var o = {};
            for (var k in LBL_DEF) o[k] = m[k] !== undefined ? (m[k] ? 1 : 0) : LBL_DEF[k];
            return o;
          }
        } catch (e) {}
        var d = {};
        for (var k2 in LBL_DEF) d[k2] = LBL_DEF[k2];
        return d;
      }
      function lblToggle(k) {
        var f = lblFields();
        f[k] = f[k] ? 0 : 1;
        try {
          localStorage.setItem("labelFields", JSON.stringify(f));
        } catch (e) {}
      }
      function lblLayout() {
        try {
          return localStorage.getItem("labelLayout") || "split";
        } catch (e) {
          return "split";
        }
      }
      function lblSetLayout(v) {
        try {
          localStorage.setItem("labelLayout", v);
        } catch (e) {}
      }
      function labelRows(b, p, meta, isEs) {
        var f = lblFields(),
          rows = [];
        if (f.roast) {
          var rd = labelDate(p.roast_date, true);
          if (rd) rows.push([isEs ? "Tueste" : "Roast", rd]);
        }
        if (f.freeze) {
          var fd = labelDate(p.freeze_date, true);
          if (fd) rows.push([isEs ? "Congelado" : "Freeze", fd]);
        }
        if (f.peak) {
          try {
            var w = restWindow(b.roast || "Light", b.process || "", restDefaultMethod()),
              t0 = dParse(p.roast_date);
            if (w && isFinite(t0))
              rows.push([
                isEs ? "Pico" : "Peak",
                labelDate(new Date(t0 + w.peakLo * 86400000).toISOString().slice(0, 10)) +
                  " - " +
                  labelDate(new Date(t0 + w.peakHi * 86400000).toISOString().slice(0, 10)),
              ]);
          } catch (e) {}
        }
        if (f.portion) {
          var pv =
            typeof LBL_PORTION === "string" && LBL_PORTION !== ""
              ? LBL_PORTION
              : String(p.portion_g || "");
          if (pv) rows.push([isEs ? "Porción" : "Portion", pv]);
        }
        return rows;
      }
      function lblScale() {
        var v = parseFloat(localStorage.getItem("labelScale") || "1");
        return isFinite(v) && v > 0.5 && v < 2 ? v : 1;
      }
      function lblSetScale(v) {
        try {
          localStorage.setItem("labelScale", String(v));
        } catch (e) {}
      }
      function labelDraw(b, logoImg) {
        /* 50x30 mm at 5:3. Pure black on white, no grey: thermal heads are 1-bit.
     Every size runs through S so one control scales the whole label. */
        var W = 1200,
          H = 720,
          c = document.createElement("canvas");
        c.width = W;
        c.height = H;
        var x = c.getContext("2d");
        x.fillStyle = "#ffffff";
        x.fillRect(0, 0, W, H);
        x.fillStyle = "#000000";
        var p = (b.portions && b.portions[0]) || {},
          meta = bagMeta(b);
        var isEs = typeof LANG !== "undefined" && LANG === "es",
          pad = 60,
          f = lblFields(),
          S = lblScale();
        var F = function (px, bold, serif) {
          return (
            (bold ? "bold " : "") +
            Math.round(px * S) +
            "px " +
            (serif ? "Georgia, Times New Roman, serif" : "-apple-system, system-ui, sans-serif")
          );
        };
        var G = function (px) {
          return Math.round(px * S);
        };
        var wrap = function (s, maxw) {
          var words = String(s || "").split(/\s+/),
            line = "",
            out = [];
          words.forEach(function (w) {
            var tt = line ? line + " " + w : w;
            if (x.measureText(tt).width > maxw && line) {
              out.push(line);
              line = w;
            } else {
              line = tt;
            }
          });
          if (line) out.push(line);
          return out;
        };
        var drawLogo = function (bx, by, bw, bh) {
          if (logoImg) {
            var sc = Math.min(bw / logoImg.width, bh / logoImg.height),
              dw = logoImg.width * sc,
              dh = logoImg.height * sc;
            x.drawImage(logoImg, bx + (bw - dw) / 2, by + (bh - dh) / 2, dw, dh);
            return true;
          }
          if (b.roaster) {
            x.textAlign = "center";
            x.font = F(50, true, true);
            x.fillText(String(b.roaster).toUpperCase(), bx + bw / 2, by + bh / 2 + 14);
            x.textAlign = "left";
            return true;
          }
          return false;
        };
        var rows = labelRows(b, p, meta, isEs);
        if (lblLayout() === "stacked") {
          x.textAlign = "center";
          x.font = F(66, true);
          var ty = pad + G(56);
          if (f.coffee)
            wrap(b.coffee, W - pad * 2)
              .slice(0, 1)
              .forEach(function (l) {
                x.fillText(l, W / 2, ty);
                ty += G(72);
              });
          x.textAlign = "left";
          var ly = ty + G(24);
          x.font = F(42);
          var left = [];
          if (f.region && meta.region) left.push([isEs ? "Origen" : "Origin", meta.region]);
          if (f.varietal && meta.varietal)
            left.push([isEs ? "Variedad" : "Varietal", meta.varietal]);
          if (f.process && b.process) left.push([isEs ? "Proceso" : "Process", b.process]);
          if (f.roastlvl && b.roast) left.push([isEs ? "Tueste" : "Roast", b.roast]);
          left = left.concat(rows);
          left.slice(0, 6).forEach(function (r) {
            x.fillText(r[0] + ": " + r[1], pad, ly);
            ly += G(50);
          });
          drawLogo(W - pad - 340, ty + G(16), 340, Math.max(150, H - pad - 14 - (ty + G(16))));
        } else {
          x.textAlign = "right";
          var rx = W - pad,
            ry = pad + G(56);
          x.font = F(66, true);
          if (f.coffee)
            wrap(b.coffee, 660)
              .slice(0, 2)
              .forEach(function (l) {
                x.fillText(l, rx, ry);
                ry += G(74);
              });
          if (f.process && b.process) {
            x.font = F(52);
            x.fillText(b.process, rx, ry);
            ry += G(60);
          }
          if (f.roastlvl && b.roast) {
            x.font = F(46);
            x.fillText(b.roast, rx, ry);
            ry += G(54);
          }
          if (f.varietal && meta.varietal) {
            x.font = F(46);
            x.fillText(meta.varietal, rx, ry);
            ry += G(54);
          }
          x.textAlign = "left";
          var lb = f.region && meta.region ? H - pad - G(48) - 26 : H - pad - 14;
          drawLogo(pad, 104, 430, Math.max(150, lb - 104));
          if (f.region && meta.region) {
            x.font = F(48);
            x.fillText(meta.region, pad, H - pad - 6);
          }
          x.textAlign = "right";
          x.font = F(44);
          var n = Math.min(rows.length, 3),
            by2 = H - pad - 6 - (n - 1) * G(52);
          rows.slice(0, 3).forEach(function (r) {
            x.fillText(r[0] + ": " + r[1], rx, by2);
            by2 += G(52);
          });
          x.textAlign = "left";
        }
        return c;
      }
      function labelPick(b, after) {
        /* iOS ignores click() on a detached file input, so it must live in the DOM
     for the duration of the pick. It is parked offscreen rather than hidden,
     because display:none inputs are also skipped by some browsers. */
        var inp = document.createElement("input");
        inp.type = "file";
        inp.accept = "image/*";
        inp.style.cssText = "position:fixed;left:-10000px;top:0;opacity:0";
        var done = function () {
          try {
            if (inp.parentNode) inp.parentNode.removeChild(inp);
          } catch (e) {}
        };
        inp.onchange = function () {
          var f = inp.files && inp.files[0];
          if (!f) {
            done();
            return;
          }
          var fr = new FileReader();
          fr.onerror = function () {
            done();
            alert(t("logoFail"));
          };
          fr.onload = function () {
            var im = new Image();
            im.onload = function () {
              var url = "";
              try {
                url = logoThreshold(im, 480);
              } catch (e) {}
              done();
              if (!url) {
                alert(t("logoFail"));
                return;
              }
              logoSet(b.roaster, url);
              if (!logoGet(b.roaster)) {
                alert(t("logoTooBig"));
                return;
              }
              var im2 = new Image();
              im2.onload = function () {
                after(im2);
              };
              im2.onerror = function () {
                after(null);
              };
              im2.src = url;
            };
            im.onerror = function () {
              done();
              alert(t("logoFail"));
            };
            im.src = fr.result;
          };
          fr.readAsDataURL(f);
        };
        document.body.appendChild(inp);
        /* Android fires no change event when the same file is chosen again unless the
     value is cleared first. Harmless on iOS. */
        try {
          inp.value = "";
        } catch (e) {}
        inp.click();
        setTimeout(done, 120000);
      }
      function labelOpen(b) {
        var lg = logoGet(b.roaster);
        if (lg) {
          var im = new Image();
          im.onload = function () {
            labelShow(b, im);
          };
          im.onerror = function () {
            labelShow(b, null);
          };
          im.src = lg;
        } else labelShow(b, null);
      }
      function labelShow(b, logoImg) {
        var isEs = typeof LANG !== "undefined" && LANG === "es";
        var old = document.getElementById("labelOv");
        if (old && old.parentNode) old.parentNode.removeChild(old);
        var url;
        try {
          url = labelDraw(b, logoImg).toDataURL("image/png");
        } catch (e) {
          return;
        }
        var ov = document.createElement("div");
        ov.id = "labelOv";
        ov.style.cssText =
          "position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;overflow:auto";
        var card = document.createElement("div");
        card.style.cssText =
          "background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px;max-width:440px;width:100%;color:var(--text)";
        var h = document.createElement("div");
        h.textContent = t("labelTitle");
        h.style.cssText = "font-weight:600;margin-bottom:9px";
        card.appendChild(h);
        var img = document.createElement("img");
        img.src = url;
        img.alt = "label";
        img.style.cssText = "width:100%;display:block;border-radius:8px;background:#fff";
        card.appendChild(img);
        var hint = document.createElement("div");
        hint.textContent = t("labelHint");
        hint.style.cssText = "color:var(--dim);font-size:12px;margin:10px 0 10px;line-height:1.45";
        card.appendChild(hint);
        var chipRow = function () {
          var d = document.createElement("div");
          d.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px";
          return d;
        };
        var chip = function (txt, on, fn) {
          var e = document.createElement("span");
          e.textContent = txt;
          e.style.cssText =
            "padding:6px 11px;border-radius:14px;font-size:11px;cursor:pointer;border:1px solid " +
            (on ? "var(--sel-line)" : "var(--line)") +
            ";background:" +
            (on ? "var(--sel-bg)" : "transparent") +
            ";color:" +
            (on ? "var(--sel-text)" : "var(--dim)");
          e.onclick = fn;
          return e;
        };
        var sc = lblScale(),
          sr = chipRow();
        [
          ["A-", 0.85],
          ["A", 1],
          ["A+", 1.2],
          ["A++", 1.45],
        ].forEach(function (o) {
          sr.appendChild(
            chip(o[0], Math.abs(sc - o[1]) < 0.01, function () {
              lblSetScale(o[1]);
              labelShow(b, logoImg);
            }),
          );
        });
        card.appendChild(sr);
        var lay = lblLayout(),
          lr = chipRow();
        lr.appendChild(
          chip(t("layoutSplit"), lay === "split", function () {
            lblSetLayout("split");
            labelShow(b, logoImg);
          }),
        );
        lr.appendChild(
          chip(t("layoutStacked"), lay === "stacked", function () {
            lblSetLayout("stacked");
            labelShow(b, logoImg);
          }),
        );
        card.appendChild(lr);
        var ff = lblFields(),
          fr2 = chipRow();
        [
          ["coffee", isEs ? "Nombre" : "Name"],
          ["process", isEs ? "Proceso" : "Process"],
          ["roastlvl", isEs ? "Tueste" : "Roast level"],
          ["varietal", isEs ? "Variedad" : "Varietal"],
          ["region", isEs ? "Origen" : "Origin"],
          ["roast", isEs ? "F. tueste" : "Roast date"],
          ["freeze", isEs ? "F. congelado" : "Freeze date"],
          ["peak", isEs ? "Pico" : "Peak"],
          ["portion", isEs ? "Porción" : "Portion"],
        ].forEach(function (k) {
          fr2.appendChild(
            chip(k[1], !!ff[k[0]], function () {
              lblToggle(k[0]);
              labelShow(b, logoImg);
            }),
          );
        });
        card.appendChild(fr2);
        if (lblFields().portion) {
          var pw = document.createElement("div");
          pw.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:8px";
          var pl = document.createElement("span");
          pl.textContent = isEs ? "Porción" : "Portion";
          pl.style.cssText = "color:var(--dim);font-size:11px";
          pw.appendChild(pl);
          var pi = document.createElement("input");
          pi.className = "fin";
          pi.style.cssText = "flex:1;padding:7px 9px;font-size:13px";
          var pb = (b.portions && b.portions[0]) || {};
          pi.value = LBL_PORTION !== "" ? LBL_PORTION : String(pb.portion_g || "");
          pi.placeholder = isEs ? "p. ej. 20g o bolsa completa" : "e.g. 20g or whole bag";
          pi.onchange = function () {
            LBL_PORTION = pi.value;
            labelShow(b, logoImg);
          };
          pw.appendChild(pi);
          card.appendChild(pw);
        }
        var mk = function (txt, fn, primary) {
          var e = document.createElement("button");
          e.textContent = txt;
          e.style.cssText =
            "flex:1;padding:10px;border-radius:10px;font-size:13px;cursor:pointer;border:1px solid " +
            (primary ? "var(--sel-line)" : "var(--line)") +
            ";background:" +
            (primary ? "var(--sel-bg)" : "var(--panel)") +
            ";color:" +
            (primary ? "var(--sel-text)" : "var(--dim)") +
            (primary ? ";font-weight:600" : "");
          e.onclick = fn;
          return e;
        };
        var r1 = document.createElement("div");
        r1.style.cssText = "display:flex;gap:8px;margin-bottom:8px";
        var dl = document.createElement("a");
        dl.href = url;
        dl.download = String(b.coffee || "label").replace(/[^a-z0-9]+/gi, "-") + "-50x30.png";
        dl.textContent = t("labelSave");
        dl.style.cssText =
          "flex:1;text-align:center;padding:10px;border-radius:10px;border:1px solid var(--sel-line);background:var(--sel-bg);color:var(--sel-text);font-weight:600;text-decoration:none;font-size:13px";
        r1.appendChild(dl);
        r1.appendChild(
          mk(
            t("scoreCancel"),
            function () {
              if (ov.parentNode) ov.parentNode.removeChild(ov);
            },
            false,
          ),
        );
        card.appendChild(r1);
        if (b.roaster) {
          var r2 = document.createElement("div");
          r2.style.cssText = "display:flex;gap:8px";
          var has = !!logoGet(b.roaster);
          r2.appendChild(
            mk(
              has ? t("logoChange") : t("logoAdd"),
              function () {
                labelPick(b, function (im) {
                  labelShow(b, im);
                });
              },
              false,
            ),
          );
          if (has)
            r2.appendChild(
              mk(
                t("logoInvert"),
                function () {
                  LOGO_FLIP_CB = function () {
                    LOGO_FLIP_CB = null;
                    labelOpen(b);
                  };
                  logoFlip(b.roaster);
                },
                false,
              ),
            );
          if (has)
            r2.appendChild(
              mk(
                t("logoRemove"),
                function () {
                  logoSet(b.roaster, "");
                  labelShow(b, null);
                },
                false,
              ),
            );
          card.appendChild(r2);
          var lh = document.createElement("div");
          lh.textContent = t("logoHint");
          lh.style.cssText = "color:var(--dim);font-size:11px;margin-top:8px;line-height:1.4";
          card.appendChild(lh);
        }
        ov.appendChild(card);
        document.body.appendChild(ov);
      }
      function listOptions(srcId) {
        /* iOS renders a datalist only as keyboard suggestions, never as a tappable
     list, so real selects are used instead. The choices are mirrored from the
     pickers the app already has, which keeps a single source of truth. */
        var s = document.getElementById(srcId);
        if (!s) return [];
        var out = [];
        Array.prototype.forEach.call(s.querySelectorAll("option"), function (o) {
          var v = (o.value || o.textContent || "").trim();
          if (!v || /\.\.\.$/.test(v)) return;
          if (out.indexOf(v) < 0) out.push(v);
        });
        return out;
      }
      function pickerize(id) {
        /* A datalist on iOS is only a keyboard suggestion strip, never a tappable
     list, so these fields read as plain free text on a phone. Upgrade them in
     place to real selects, keeping the SAME id so every getElementById read and
     write in the app keeps working untouched. The choices come from the same
     datalist that was already there, so there is still one source of truth.
     The last option swaps a text input back in for anything not on the list. */
        var el = document.getElementById(id);
        if (!el || el.tagName !== "INPUT") return;
        var listId = el.getAttribute("list");
        if (!listId) return;
        var opts = listOptions(listId);
        if (!opts.length) return;
        var isEs = typeof LANG !== "undefined" && LANG === "es";
        var cls = el.className || "fin";
        var ph = el.getAttribute("placeholder") || "";
        var oi = el.getAttribute("oninput") || "";
        var cur = el.value || "";
        var sel = document.createElement("select");
        sel.id = id;
        sel.className = cls;
        sel.style.width = "100%";
        if (oi) sel.setAttribute("onchange", oi);
        var b = document.createElement("option");
        b.value = "";
        b.textContent = ph ? ph : isEs ? "elige..." : "choose...";
        sel.appendChild(b);
        if (cur && opts.indexOf(cur) < 0) opts.unshift(cur);
        opts.forEach(function (o) {
          var e = document.createElement("option");
          e.value = o;
          e.textContent = o;
          if (o === cur) e.selected = true;
          sel.appendChild(e);
        });
        var oth = document.createElement("option");
        oth.value = "__other__";
        oth.textContent = isEs ? "+ escribir otro..." : "+ type another...";
        sel.appendChild(oth);
        sel.addEventListener("change", function () {
          if (sel.value !== "__other__") return;
          var ti = document.createElement("input");
          ti.id = id;
          ti.className = cls;
          ti.value = "";
          if (ph) ti.setAttribute("placeholder", ph);
          if (listId) ti.setAttribute("list", listId);
          if (oi) ti.setAttribute("oninput", oi);
          if (sel.parentNode) sel.parentNode.replaceChild(ti, sel);
          try {
            ti.focus();
          } catch (e) {}
        });
        if (el.parentNode) el.parentNode.replaceChild(sel, el);
      }
      function pickerizeAll() {
        ["ghOrigin", "ghVarietal", "invvarietal", "invregion", "fregion"].forEach(function (id) {
          try {
            pickerize(id);
          } catch (e) {}
        });
      }
      function ensureList(id, srcId) {
        /* The pickers already exist as selects elsewhere in the app. Mirror their
     options into a datalist so an edit field offers the same choices and only
     needs typing for something genuinely new. */
        if (document.getElementById(id)) return;
        var s = document.getElementById(srcId);
        if (!s) return;
        var dl = document.createElement("datalist");
        dl.id = id;
        Array.prototype.forEach.call(s.querySelectorAll("option"), function (o) {
          var v = (o.value || o.textContent || "").trim();
          if (!v || /\.\.\.$/.test(v)) return;
          var e = document.createElement("option");
          e.value = v;
          dl.appendChild(e);
        });
        document.body.appendChild(dl);
      }
      function dOnly(v) {
        var s = String(v || "")
          .trim()
          .slice(0, 10);
        return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : "";
      }
      function editBagOpen(b) {
        if (dataMode() !== "google") {
          alert(t("editNeedSheet"));
          return;
        }
        if (!b || !b.__row) {
          alert(t("editNoRow"));
          return;
        }
        var p = (b.portions && b.portions[0]) || {};
        var isEs = typeof LANG !== "undefined" && LANG === "es";
        ensureList("roasterList", "roaster");
        ensureList("roastList", "roast");
        ensureList("processList", "process");
        try {
          renderCoffeeList();
        } catch (e) {}
        editOverlay(
          t("editBag"),
          [
            { k: "coffee", label: isEs ? "Café" : "Coffee", v: b.coffee, options: knownCoffees() },
            {
              k: "roaster",
              label: isEs ? "Tostador" : "Roaster",
              v: b.roaster,
              options: listOptions("roaster"),
            },
            {
              k: "roast",
              label: isEs ? "Tueste" : "Roast level",
              v: b.roast,
              options: listOptions("roast"),
            },
            {
              k: "process",
              label: isEs ? "Proceso" : "Process",
              v: b.process,
              options: listOptions("process"),
            },
            {
              k: "roast_date",
              label: isEs ? "Fecha de tueste" : "Roast date",
              v: dOnly(p.roast_date),
              type: "date",
            },
            {
              k: "freeze_date",
              label: isEs ? "Fecha de congelado" : "Freeze date",
              v: dOnly(p.freeze_date),
              type: "date",
            },
            {
              k: "portion_g",
              label: isEs ? "Tamaño de porción (g)" : "Portion size (g)",
              v: p.portion_g,
              type: "number",
              step: "0.1",
            },
            {
              k: "varietal",
              label: isEs ? "Variedad" : "Varietal",
              v: b.varietal,
              options: listOptions("ghVarList"),
            },
            {
              k: "region",
              label: isEs ? "Origen / región" : "Origin / region",
              v: b.region,
              options: listOptions("ghOriginList"),
            },
            { k: "qty", label: isEs ? "Cuantas" : "How many", v: p.qty, type: "number" },
          ],
          async function (vals) {
            await gPatchRow(INV_TAB, b.__row, vals);
            try {
              loadInventory();
            } catch (e) {}
          },
        );
      }
      function editLastShotOpen() {
        if (dataMode() !== "google") {
          alert(t("editNeedSheet"));
          return;
        }
        var rows = typeof IROWS !== "undefined" ? IROWS : [],
          last = null;
        for (var i = rows.length - 1; i >= 0; i--) {
          if (rows[i] && rows[i].__row) {
            last = rows[i];
            break;
          }
        }
        if (!last) {
          alert(t("editNoShot"));
          return;
        }
        var isEs = typeof LANG !== "undefined" && LANG === "es";
        try {
          renderCoffeeList();
        } catch (e) {}
        editOverlay(
          t("editShot"),
          [
            {
              k: "coffee",
              label: isEs ? "Café" : "Coffee",
              v: last.coffee,
              options: knownCoffees(),
            },
            { k: "dose_g", label: isEs ? "Dosis (g)" : "Dose (g)", v: last.dose_g },
            {
              k: "yield_g",
              label: isEs ? "Salida / agua (g)" : "Yield / water (g)",
              v: last.yield_g,
            },
            { k: "duration_s", label: isEs ? "Tiempo (s)" : "Time (s)", v: last.duration_s },
            { k: "grind_setting", label: isEs ? "Molienda" : "Grind", v: last.grind_setting },
            { k: "rating", label: isEs ? "Nota" : "Rating", v: last.rating },
          ],
          async function (vals) {
            await gPatchRow(SHOT_TAB, last.__row, vals);
            try {
              await iLoad();
            } catch (e) {}
            try {
              renderHero();
            } catch (e) {}
          },
        );
      }
      function rotRemove(i) {
        var e = typeof ROT !== "undefined" && ROT ? ROT[i] : null;
        if (!e) return;
        var isEs = typeof LANG !== "undefined" && LANG === "es";
        if (
          !confirm((isEs ? "Quitar de la rotación: " : "Remove from rotation: ") + e.coffee + "?")
        )
          return;
        ROT.splice(i, 1);
        try {
          saveRot();
        } catch (err) {}
        try {
          renderChips();
        } catch (err) {}
        try {
          homeExtra();
        } catch (err) {}
      }
      function rotSuggest() {
        var inv = (typeof IINV !== "undefined" && IINV ? IINV : []).filter(function (r) {
          return String(r.status || "") !== "Finished" && String(r.coffee || "").trim();
        });
        if (!inv.length) {
          alert(t("rotNoBags"));
          return;
        }
        var isEs = typeof LANG !== "undefined" && LANG === "es";
        var mode = typeof ROTMODE !== "undefined" && ROTMODE ? ROTMODE : "balanced";
        var seen = {};
        var scored = [];
        inv.forEach(function (r) {
          var key = String(r.coffee).trim().toLowerCase();
          if (seen[key]) return;
          seen[key] = 1;
          var rs = null;
          try {
            rs = restStatus(r.roast || "Light", r.process || "", restDefaultMethod(), r.roast_date);
          } catch (e) {}
          var a = null;
          try {
            a = coffeeAvg(r.coffee);
          } catch (e) {}
          var t0 = dParse(r.roast_date),
            age = isFinite(t0) ? Math.floor((Date.now() - t0) / 86400000) : 0;
          var inRot = false;
          try {
            inRot = (ROT || []).some(function (x) {
              return String(x.coffee || "").toLowerCase() === key;
            });
          } catch (e) {}
          var peak = rs
            ? rs.phase === "in peak"
              ? 3
              : rs.phase === "nearing peak"
                ? 2
                : rs.phase === "resting"
                  ? 1
                  : 0
            : 0;
          var s, why;
          if (mode === "fifo") {
            s = age;
            why = isEs
              ? "el más viejo, " + age + "d desde el tueste"
              : "oldest, " + age + "d off roast";
          } else if (mode === "variety") {
            s = (inRot ? 0 : 500) + (a && a.n ? -a.n * 10 : 0) + age / 10;
            why = inRot
              ? isEs
                ? "ya en rotación"
                : "already in rotation"
              : isEs
                ? "aún no lo has puesto en rotación"
                : "not in your rotation yet";
          } else if (mode === "freshness") {
            s = peak * 100 + (a && a.avg ? a.avg : 0);
            why = rs
              ? rs.phase === "in peak"
                ? isEs
                  ? "en su punto"
                  : "at peak"
                : rs.phase === "nearing peak"
                  ? isEs
                    ? "casi en su punto"
                    : "nearing peak"
                  : rs.phase === "resting"
                    ? isEs
                      ? "todavía reposando"
                      : "still resting"
                    : isEs
                      ? "pasado el pico"
                      : "past peak"
              : isEs
                ? "sin fecha de tueste"
                : "no roast date";
          } else {
            s = peak * 60 + (a && a.avg ? a.avg * 8 : 0) + age / 4;
            why =
              (peak === 3 ? (isEs ? "en su punto" : "at peak") : "") +
              (a && a.n ? (peak === 3 ? " · " : "") + a.avg + (isEs ? " prom" : " avg") : "");
            if (!why) why = isEs ? "balance de edad y punto" : "balance of age and peak";
          }
          scored.push({ coffee: r.coffee, s: s, why: why });
        });
        scored.sort(function (p, q) {
          return q.s - p.s;
        });
        var top = scored[0];
        if (!top) return;
        if (confirm(t("rotPicked").replace("{c}", top.coffee).replace("{why}", top.why)))
          rotEnsure(top.coffee);
      }
      /* ---- coffee identity gate ------------------------------------------------
   Two failures this fixes, both seen in real data on 2026-07-23. A brew was
   logged against a coffee that had no bag in inventory, so cost and rest never
   applied to it. And the same bag got logged twice under two spellings,
   'Bombe Honey' and 'Bomber honey', which splits its history in half and
   quietly poisons every average built on it. Neither threw, neither showed. */
      function bpNorm(s) {
        return String(s || "")
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, " ")
          .trim();
      }
      function bpDigits(s) {
        var m = String(s || "").match(/[0-9]/g);
        return m ? m.join("") : "";
      }
      function bpDist(a, b) {
        var m = a.length,
          n = b.length;
        if (!m) return n;
        if (!n) return m;
        var prev = [],
          cur = [],
          i,
          j;
        for (j = 0; j <= n; j++) prev[j] = j;
        for (i = 1; i <= m; i++) {
          cur[0] = i;
          for (j = 1; j <= n; j++) {
            var cost = a.charAt(i - 1) === b.charAt(j - 1) ? 0 : 1;
            cur[j] = Math.min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost);
          }
          for (j = 0; j <= n; j++) prev[j] = cur[j];
        }
        return prev[n];
      }
      function bpInvNames() {
        var out = [],
          seen = {};
        (typeof IINV !== "undefined" && IINV ? IINV : []).forEach(function (r) {
          if (String(r.status || "") === "Finished") return;
          var n = String(r.coffee || "").trim();
          if (!n) return;
          var k = bpNorm(n);
          if (seen[k]) return;
          seen[k] = 1;
          out.push(n);
        });
        return out;
      }
      function bpKnownNames() {
        var out = bpInvNames().slice(),
          seen = {};
        out.forEach(function (x) {
          seen[bpNorm(x)] = 1;
        });
        try {
          JSON.parse(localStorage.getItem("coffees") || "[]").forEach(function (x) {
            var n = String(x || "").trim();
            if (!n) return;
            var k = bpNorm(n);
            if (seen[k]) return;
            seen[k] = 1;
            out.push(n);
          });
        } catch (e) {}
        return out;
      }
      function bpInInventory(name) {
        var k = bpNorm(name);
        return bpInvNames().some(function (x) {
          return bpNorm(x) === k;
        });
      }
      function bpNearName(name, list) {
        /* One character apart is a typo inside a word and a DIFFERENT LOT inside a
     number. Bombe Honey and Bomber honey are one bag; Lot #25/047 and Lot
     #25/048 are two, and merging those would be worse than never suggesting
     anything at all. So a candidate whose digits differ is never a typo. */
        var n = bpNorm(name);
        if (n.length < 4) return "";
        var nd = bpDigits(name),
          best = "",
          bd = 99;
        for (var i = 0; i < list.length; i++) {
          var cand = list[i],
            m = bpNorm(cand);
          if (!m || m === n) continue;
          if (bpDigits(cand) !== nd) continue;
          var lim = m.length <= 6 ? 1 : m.length <= 14 ? 2 : 3;
          var d = bpDist(n, m);
          if (d <= lim && d < bd) {
            bd = d;
            best = cand;
          }
        }
        return best;
      }
      function bpSingleList() {
        try {
          return JSON.parse(localStorage.getItem("bpSingleDose") || "[]");
        } catch (e) {
          return [];
        }
      }
      function bpIsSingle(name) {
        var k = bpNorm(name);
        return bpSingleList().some(function (x) {
          return bpNorm(x) === k;
        });
      }
      function bpMarkSingle(name) {
        try {
          if (bpIsSingle(name)) return;
          var a = bpSingleList();
          a.push(String(name).trim());
          localStorage.setItem("bpSingleDose", JSON.stringify(a));
        } catch (e) {}
      }
      function bpChoice(title, body, opts) {
        /* Real buttons, because confirm() has room for a yes and a no and these
     questions have three honest answers. Resolves null when dismissed. */
        return new Promise(function (res) {
          var ov = document.createElement("div");
          ov.style.cssText =
            "position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px";
          var card = document.createElement("div");
          card.style.cssText =
            "background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;max-width:420px;width:100%;color:var(--text)";
          var h = document.createElement("div");
          h.textContent = title;
          h.style.cssText = "font-weight:600;margin-bottom:6px";
          card.appendChild(h);
          if (body) {
            var p = document.createElement("div");
            p.textContent = body;
            p.style.cssText = "color:var(--dim);font-size:13px;line-height:1.45;margin-bottom:6px";
            card.appendChild(p);
          }
          function close(v) {
            if (ov.parentNode) ov.parentNode.removeChild(ov);
            res(v);
          }
          opts.forEach(function (o) {
            var b = document.createElement("button");
            b.textContent = o.l;
            b.style.cssText =
              "display:block;width:100%;margin-top:8px;padding:12px;border-radius:10px;border:1px solid var(--sel-line);background:var(--sel-bg);color:var(--sel-text);font-weight:600;cursor:pointer";
            b.onclick = function () {
              close(o.v);
            };
            card.appendChild(b);
          });
          var cx = document.createElement("button");
          cx.textContent = t("scoreCancel");
          cx.style.cssText =
            "display:block;width:100%;margin-top:10px;padding:11px;border-radius:10px;border:1px solid var(--line);background:var(--panel);color:var(--dim);cursor:pointer";
          cx.onclick = function () {
            close(null);
          };
          card.appendChild(cx);
          ov.appendChild(card);
          document.body.appendChild(ov);
        });
      }
      function bpRegisterBag(name) {
        /* Deliberately NOT awaited by the gate. If it were, cancelling this form
     would leave the brew unsaved with nothing on screen explaining why. The
     brew is already good; the bag is a separate piece of bookkeeping. */
        var isEs = typeof LANG !== "undefined" && LANG === "es";
        if (typeof dataMode === "function" && dataMode() !== "google") {
          alert(t("gSaveFirst"));
          return;
        }
        var stIn = isEs ? "En uso, en la barra" : "In use, on the counter";
        var stRest = isEs ? "Reposando afuera" : "Resting out to degas";
        var stFrozen = isEs ? "Congelada y sellada" : "Frozen and sealed";
        editOverlay(
          isEs ? "Registrar una bolsa de " + name : "Register a bag of " + name,
          [
            {
              k: "bag_g",
              label: isEs ? "Gramos por bolsa" : "Grams per bag",
              v: "250",
              type: "number",
            },
            { k: "qty", label: isEs ? "Cuantas bolsas" : "How many bags", v: "1", type: "number" },
            {
              k: "roast_date",
              label: isEs ? "Fecha de tueste" : "Roast date",
              v: "",
              type: "date",
            },
            {
              k: "state",
              label: isEs ? "Estado" : "State",
              v: stIn,
              options: [stIn, stRest, stFrozen],
            },
          ],
          async function (o) {
            var st = String((o && o.state) || stIn);
            try {
              window.REST_MODE = st !== stFrozen;
            } catch (e) {}
            var fo = {
              coffee: name,
              roaster: "",
              portion: "",
              qty: (o && o.qty) || "1",
              roast_date: (o && o.roast_date) || "",
              roast: "",
              process: "",
              freeze_date: "",
              varietal: "",
              region: "",
              bag_g: (o && o.bag_g) || "",
              price: "",
              currency: typeof INVCCY !== "undefined" ? INVCCY : "",
            };
            await gFreeze(fo);
            if (st === stIn) {
              try {
                await gBagState(name, "Counter", "Open");
              } catch (e) {}
            }
            try {
              iLocalInvPush(fo);
            } catch (e) {}
            try {
              loadInventory();
            } catch (e) {}
            try {
              addCoffeeName(name);
            } catch (e) {}
          },
        );
      }
      async function bpCoffeeGate() {
        /* Runs BEFORE the row is written, so a corrected name is the name that gets
     saved. Returns false only when the person backed out on purpose. */
        var el = document.getElementById("coffee");
        if (!el) return true;
        var c = String(el.value || "").trim();
        if (!c) return true;
        var isEs = typeof LANG !== "undefined" && LANG === "es";
        if (bpInInventory(c)) return true;
        var near = bpNearName(c, bpKnownNames());
        if (near) {
          var a = await bpChoice(
            isEs
              ? "Se parece a un cafe que ya tienes"
              : "This looks like a coffee you already have",
            isEs
              ? 'Escribiste "' +
                  c +
                  '". Ya existe "' +
                  near +
                  '". Si son el mismo, usar dos nombres parte su historial en dos y ensucia los promedios.'
              : 'You typed "' +
                  c +
                  '". You already have "' +
                  near +
                  '". If they are the same bag, two spellings split its history and skew every average built on it.',
            [
              { l: isEs ? 'Es "' + near + '"' : 'It is "' + near + '"', v: "use" },
              { l: isEs ? "Es un cafe distinto" : "It is a different coffee", v: "other" },
            ],
          );
          if (a === null) return false;
          if (a === "use") {
            el.value = near;
            c = near;
            if (bpInInventory(c)) return true;
          }
        }
        if (bpIsSingle(c)) return true;
        var b = await bpChoice(
          isEs ? '"' + c + '" no esta en tu inventario' : '"' + c + '" is not in your inventory',
          isEs
            ? "Sin una bolsa no puedo calcular su costo por taza ni su ventana de reposo."
            : "Without a bag I cannot work out its cost per cup or its rest window.",
          [
            { l: isEs ? "Registrar una bolsa" : "Register a bag", v: "bag" },
            { l: isEs ? "Fue una dosis unica" : "It was a single dose", v: "single" },
          ],
        );
        if (b === null) return false;
        if (b === "single") {
          bpMarkSingle(c);
          return true;
        }
        if (b === "bag") {
          try {
            bpRegisterBag(c);
          } catch (e) {}
          return true;
        }
        return true;
      }
      function rotAdd() {
        /* Was a bare prompt(), which meant retyping a coffee name that the app
     already knows, on a phone keyboard, with no protection against a typo
     creating a second entry for the same bag. Offer the inventory instead,
     minus anything already in the rotation, and keep a type-it-yourself route
     for a bag that has not been added to inventory yet. */
        var isEs = typeof LANG !== "undefined" && LANG === "es";
        if (typeof ROT === "undefined" || !ROT) return;
        var seen = {},
          names = [];
        (typeof IINV !== "undefined" && IINV ? IINV : []).forEach(function (r) {
          var n = String(r.coffee || "").trim();
          if (!n) return;
          if (String(r.status || "") === "Finished") return;
          var k = n.toLowerCase();
          if (seen[k]) return;
          seen[k] = 1;
          var already = ROT.some(function (x) {
            return String(x.coffee || "").toLowerCase() === k;
          });
          if (!already) names.push(n);
        });
        try {
          var extra = JSON.parse(localStorage.getItem("coffees") || "[]");
          extra.forEach(function (x) {
            var n = String(x || "").trim();
            if (!n) return;
            var k = n.toLowerCase();
            if (seen[k]) return;
            seen[k] = 1;
            if (
              !ROT.some(function (y) {
                return String(y.coffee || "").toLowerCase() === k;
              })
            )
              names.push(n);
          });
        } catch (e) {}
        names.sort(function (a, b) {
          return a.toLowerCase() < b.toLowerCase() ? -1 : 1;
        });
        var title = isEs ? "Agregar a la rotación" : "Add to rotation";
        var label = names.length
          ? isEs
            ? "Café de tu inventario"
            : "Coffee from your inventory"
          : isEs
            ? "Nombre del café"
            : "Coffee name";
        editOverlay(title, [{ k: "coffee", label: label, v: "", options: names }], function (o) {
          var n = String((o && o.coffee) || "").trim();
          if (!n || n === "__other__") return;
          if (
            ROT.some(function (x) {
              return String(x.coffee || "").toLowerCase() === n.toLowerCase();
            })
          )
            return;
          ROT.push({ coffee: n });
          try {
            saveRot();
          } catch (e) {}
          try {
            renderChips();
          } catch (e) {}
          try {
            addCoffeeName(n);
          } catch (e) {}
          try {
            homeExtra();
          } catch (e) {}
        });
      }
      function addCoffeeName(n) {
        try {
          var a = JSON.parse(localStorage.getItem("coffees") || "[]");
          if (
            a
              .map(function (x) {
                return String(x).toLowerCase();
              })
              .indexOf(n.toLowerCase()) < 0
          ) {
            a.push(n);
            localStorage.setItem("coffees", JSON.stringify(a));
          }
        } catch (e) {}
        try {
          renderCoffeeList();
        } catch (e) {}
      }
      function rotAddChip(box) {
        if (!box) return;
        var isEs = typeof LANG !== "undefined" && LANG === "es";
        var c = document.createElement("div");
        c.textContent = "+ " + (isEs ? "agregar" : "add");
        c.style.cssText =
          "padding:8px 12px;border-radius:20px;border:1px dashed var(--sel-line);background:transparent;color:var(--sel-text);font-size:13px;cursor:pointer";
        c.onclick = rotAdd;
        box.appendChild(c);
        var sg = document.createElement("div");
        sg.textContent = "✨ " + t("rotSuggestBtn");
        sg.style.cssText =
          "padding:8px 12px;border-radius:20px;border:1px dashed var(--sel-line);background:transparent;color:var(--sel-text);font-size:13px;cursor:pointer";
        sg.onclick = rotSuggest;
        box.appendChild(sg);
      }
      function bagStateChips(b) {
        var isEs = typeof LANG !== "undefined" && LANG === "es";
        var out = [];
        var inRot = false;
        try {
          inRot = (typeof ROT !== "undefined" ? ROT : []).some(function (e) {
            return String(e.coffee || "").toLowerCase() === String(b.coffee || "").toLowerCase();
          });
        } catch (e) {}
        if (inRot)
          out.push(
            "<span style='padding:3px 8px;border-radius:12px;font-size:10px;color:var(--weight);border:1px solid var(--weight)'>" +
              (isEs ? "en rotación" : "in rotation") +
              "</span>",
          );
        if (b.inuse)
          out.push(
            "<span style='padding:3px 8px;border-radius:12px;font-size:10px;color:var(--weight);border:1px solid var(--weight)'>" +
              t("chipInUse") +
              "</span>",
          );
        if (b.frozen_portion && !b.resting && !b.inuse)
          out.push(
            "<span style='padding:3px 8px;border-radius:12px;font-size:10px;color:var(--temp);border:1px solid var(--temp)'>" +
              (isEs ? "congelado" : "frozen") +
              "</span>",
          );
        var rd = b.portions && b.portions[0] ? b.portions[0].roast_date : "";
        var rs = null;
        try {
          rs = restStatus(b.roast || "Light", b.process || "", restDefaultMethod(), rd);
        } catch (e) {}
        if (rs && rs.age != null) {
          var txt;
          if (rs.phase === "resting" || rs.phase === "nearing peak") {
            txt =
              (isEs ? "reposando · pico en " : "resting · peak in ") +
              dWeeks(rs.w.peakLo - rs.age, isEs);
          } else if (rs.phase === "in peak") {
            txt = isEs ? "en su punto" : "at peak";
          } else {
            txt = isEs ? "pasado el pico" : "past peak";
          }
          out.push(
            "<span style='padding:3px 8px;border-radius:12px;font-size:10px;color:var(--pressure);border:1px solid var(--pressure)'>" +
              txt +
              "</span>",
          );
        }
        if (!out.length) return "";
        return (
          "<div style='display:flex;gap:5px;flex-wrap:wrap;margin-top:6px'>" +
          out.join("") +
          "</div>"
        );
      }
      function roastWord(r) {
        if (!r) return t("roastLight");
        if (/Dark/i.test(r)) return t("roastDark");
        if (/Medium/i.test(r)) return t("roastMed");
        return t("roastLight");
      }
      /* Read the field of the ACTIVE form, not whichever id exists first.
   csProcess/csRoast used `getElementById('fprocess')||getElementById('process')`.
   #fprocess lives in the (hidden) filter form and ALWAYS exists, so it always won -
   the advisor read the empty filter field while you were editing the gaggia one.
   That is why process and roast moved the number on filter and nowhere else. */
      function csField(base) {
        var fil = false;
        try {
          fil = logMethod() === "filter";
        } catch (e) {}
        return document.getElementById(base); /* merged form: one field set, no f-prefix */
      }
      function csRoast() {
        var e = csField("roast");
        var v = e ? e.value : "";
        return { v: v, f: ROAST_F[v] || 1.0 };
      }
      /* Process nudge. Every 2025-26 source agrees natural coffees want a grind JUST
   slightly coarser than washed - "only slightly" (Rao) - and the DF64 chart rates
   process "low-moderate impact". Small factor, not a big one. Roast stays dominant;
   this breaks ties. */
      /* Process scale. Washed is the clean-celled anchor. The more fruit/sugar/
   fermentation left on the bean, the softer and stickier it grinds, and the
   coarser you start to avoid a choked, over-extracted puck. Oscar: "hyper
   processed must be quite coarser". Standard sources call process "low-moderate"
   for ordinary naturals, so those stay gentle - but modern hyper-processed lots
   (anaerobic, carbonic, thermal-shock, extended-ferment) are a different animal
   and get a real bump. This is a starting point; taste still rules. */
      /* The process dropdown has ~50 entries (every co-ferment fruit, every barrel).
   A fixed key map missed almost all of them - Carbonic, Extended Fermentation and
   25 co-ferments fell through to 1.0, i.e. "no change" for the MOST processed
   coffees, the opposite of the ask. Classify by tier with substring tests so
   every option lands somewhere. Ordered most-processed first; first match wins. */
      /* Process -> grind, classified by EXTRACTION EASE, not by "fruit residue".
   Researched 2026-07-18, sources in GRIND_RESEARCH.md. The mechanism every 2026
   source agrees on: fermentation degrades the bean's cell walls and makes it
   POROUS, so more-fermented coffees surrender solubles almost instantly and
   over-extract. The fix is a COARSER (and cooler) start to avoid dragging out
   ferment bitterness. Oscar asked to "classify depending on the level of
   extraction typically achieved". This is that axis: washed extracts hardest
   (densest, cleanest cell structure), heavy ferments extract easiest.

   Anchor from The Blind Coffee Roaster (Jan 2026): washed 600um -> anaerobic
   750-800um, i.e. ~1.28x. My earlier 1.08 for anaerobic was far too weak - it is
   set to 1.25 now, with the ceiling at 1.35 for the most degraded lots.
   NOTE the one dissent: Nordic Brew Lab says anaerobics can take a slightly FINER
   grind because they produce fewer fines, but still run fast. The safe starting
   point every source shares is coarser, so that is what a STARTING point uses. */
      function processTier(v) {
        if (!v) return 1.0;
        var s = v.toLowerCase();
        // 5 - most degraded cell structure, extracts fastest: barrel-aged, infused,
        //     thermal shock, double/extended anaerobic, spirit yeasts
        if (
          /barrel|infus|thermal|frozen|cryo|double anaerobic|whiskey|rum|bourbon|champagne|wine yeast/.test(
            s,
          )
        )
          return 1.35;
        // 4 - carbonic maceration, co-ferments, extended ferment, anoxic
        if (/carbonic|maceration|co-?ferment|extended|anoxic/.test(s)) return 1.28;
        // 3 - anaerobic family, lactic, yeast-inoculated (the 600->775 anchor)
        if (/anaerobic|lactic|yeast/.test(s)) return 1.25;
        // 2 - naturals and the darker honeys: full mucilage/fruit contact, sun-fermented
        if (/natural|black honey|red honey|pulped natural/.test(s)) return 1.08;
        // 1 - lighter honeys: partial mucilage
        if (/honey/.test(s)) return 1.05;
        // 0 - washed / semi-washed: cleanest cell walls, extracts hardest = anchor
        if (/semi-?washed|washed/.test(s)) return 1.0;
        return 1.0; // Other / unknown: no guess, no nudge
      }
      function csProcess() {
        var e = csField("process");
        var v = e ? e.value : "";
        return { v: v, f: processTier(v) };
      }
      /* how the adjustment reads to a human: coarser / finer / no change, with the %. */
      function csAdjWord(f) {
        if (f > 1.005) return { dir: t("csCoarser"), pct: Math.round((f - 1) * 100) };
        if (f < 0.995) return { dir: t("csFiner"), pct: Math.round((1 - f) * 100) };
        return null;
      }
      function knownCoffees() {
        var set = {};
        try {
          (typeof IROWS !== "undefined" ? IROWS : []).forEach(function (o) {
            var c = String(o.coffee || "").trim();
            if (c) set[c.toLowerCase()] = c;
          });
        } catch (e) {}
        try {
          (typeof IINV !== "undefined" ? IINV : []).forEach(function (o) {
            var c = String(o.coffee || "").trim();
            if (c) set[c.toLowerCase()] = c;
          });
        } catch (e) {}
        try {
          var ex = JSON.parse(localStorage.getItem("coffees") || "[]");
          ex.forEach(function (c) {
            c = String(c || "").trim();
            if (c) set[c.toLowerCase()] = c;
          });
        } catch (e) {}
        return Object.keys(set)
          .map(function (k) {
            return set[k];
          })
          .sort();
      }
      function coffeeAvg(coffee) {
        /* recency-weighted average of ALL notes for this coffee (brews + quick scores).
     Rows are in append order oldest->newest, so newest notes get the most weight. */
        var key = String(coffee || "")
          .trim()
          .toLowerCase();
        if (!key) return null;
        var notes = [];
        try {
          (typeof IROWS !== "undefined" ? IROWS : []).forEach(function (o) {
            if (
              String(o.coffee || "")
                .trim()
                .toLowerCase() !== key
            )
              return;
            var rt = parseFloat(o.rating);
            if (!isNaN(rt) && rt > 0) notes.push(rt);
          });
        } catch (e) {}
        if (!notes.length) return null;
        var decay = 0.85,
          w = 1,
          sw = 0,
          ssum = 0;
        for (var i = notes.length - 1; i >= 0; i--) {
          sw += w;
          ssum += notes[i] * w;
          w *= decay;
        }
        return {
          avg: Math.round((ssum / sw) * 10) / 10,
          n: notes.length,
          last: notes[notes.length - 1],
        };
      }
      function renderCoffeeList() {
        var dl = document.getElementById("coffeeList");
        if (!dl) return;
        dl.innerHTML = "";
        knownCoffees().forEach(function (c) {
          var o = document.createElement("option");
          o.value = c;
          dl.appendChild(o);
        });
      }
      function addCoffee() {
        var v = ((document.getElementById("coffee") || {}).value || "").trim();
        if (!v) return;
        try {
          var arr = JSON.parse(localStorage.getItem("coffees") || "[]");
          if (
            arr
              .map(function (x) {
                return String(x).toLowerCase();
              })
              .indexOf(v.toLowerCase()) < 0
          ) {
            arr.push(v);
            localStorage.setItem("coffees", JSON.stringify(arr));
          }
        } catch (e) {}
        try {
          renderCoffeeList();
        } catch (e) {}
        try {
          updateCoffeeHint();
        } catch (e) {}
      }
      function addToInventory() {
        var v = ((document.getElementById("coffee") || {}).value || "").trim();
        if (!v) return;
        try {
          addCoffee();
        } catch (e) {}
        /* Setting .value on a select does nothing when no option carries that value,
     which is exactly what happens once these fields became selects. Add the
     option first, then assign. */
        var st = function (id, val) {
          var e = document.getElementById(id);
          if (!e || val == null || val === "") return;
          if (e.tagName === "SELECT") {
            var found = false;
            Array.prototype.forEach.call(e.options, function (o) {
              if (o.value === val) found = true;
            });
            if (!found) {
              var n = document.createElement("option");
              n.value = val;
              n.textContent = val;
              e.insertBefore(n, e.options.length > 1 ? e.options[1] : null);
            }
          }
          e.value = val;
        };
        st("invcoffee", v);
        st("invroaster", (document.getElementById("roaster") || {}).value || "");
        st("invroast", (document.getElementById("roast") || {}).value || "");
        st("invprocess", (document.getElementById("process") || {}).value || "");
        st("invvarietal", (document.getElementById("varietal") || {}).value || "");
        st("invregion", (document.getElementById("fregion") || {}).value || "");
        try {
          var p = document.getElementById("invPanel");
          if (p && p.style.display === "none") {
            toggleInv();
          }
        } catch (e) {}
        try {
          var el = document.getElementById("invcoffee");
          if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
        } catch (e) {}
        try {
          updateCoffeeHint();
        } catch (e) {}
      }
      function updateCoffeeHint() {
        var el = document.getElementById("coffeeHint");
        if (!el) return;
        var v = ((document.getElementById("coffee") || {}).value || "").trim();
        if (!v) {
          el.innerHTML = "";
          return;
        }
        var isEs = typeof LANG !== "undefined" && LANG === "es";
        var known = knownCoffees().some(function (c) {
          return c.toLowerCase() === v.toLowerCase();
        });
        if (known) {
          var a = coffeeAvg(v);
          el.style.color = "var(--dim)";
          el.innerHTML = a
            ? a.avg +
              " " +
              (isEs ? "promedio" : "avg") +
              " (" +
              a.n +
              " " +
              (isEs ? "notas" : "notes") +
              ")"
            : isEs
              ? "en tu rotación"
              : "in your rotation";
        } else {
          el.innerHTML =
            "<button type='button' onclick='addCoffee()' style='padding:8px 12px;margin:2px 8px 2px 0;border-radius:10px;border:1px solid var(--sel-line);background:var(--sel-bg);color:var(--sel-text);font-size:12px;font-weight:600;cursor:pointer'>+ " +
            (isEs ? "rotación" : "rotation") +
            "</button>" +
            "<button type='button' onclick='addToInventory()' style='padding:8px 12px;margin:2px 0;border-radius:10px;border:1px solid var(--sel-line);background:var(--sel-bg);color:var(--sel-text);font-size:12px;font-weight:600;cursor:pointer'>+ " +
            (isEs ? "al inventario" : "to inventory") +
            "</button>";
        }
      }
      function adaptedUm(brewer, method, baseUm) {
        /* Learn the user's preferred grind (in grinder-independent um) for this
     method (+brewer for filter), rating-weighted, and shrink toward the research
     default so one shot barely moves it and ~6-10 make it mostly theirs. */
        try {
          var rows = typeof IROWS !== "undefined" && IROWS ? IROWS : [];
          var sw = 0,
            ssum = 0,
            n = 0;
          for (var i = 0; i < rows.length; i++) {
            var o = rows[i];
            if (method && String(o.type || "") !== method) continue;
            if (method === "filter" && brewer && String(o.brewer || "") !== brewer) continue;
            var u = parseFloat(o.grind_um);
            if (isNaN(u) || u <= 0) continue;
            var rf = typeof ROAST_F === "object" && ROAST_F[o.roast] ? ROAST_F[o.roast] : 1;
            var pf = 1;
            try {
              pf = processTier(o.process || "") || 1;
            } catch (e) {}
            var norm = u / (rf * pf || 1);
            var rt = parseFloat(o.rating);
            var w = !isNaN(rt) && rt > 0 ? rt : 5;
            sw += w;
            ssum += norm * w;
            n++;
          }
          if (!n) return { um: baseUm, n: 0, source: "research" };
          var yours = ssum / sw,
            K = 3;
          var adapted = Math.round(baseUm * (K / (n + K)) + yours * (n / (n + K)));
          return {
            um: adapted,
            n: n,
            yours: Math.round(yours),
            source: n >= 3 ? "yours" : "blend",
          };
        } catch (e) {
          return { um: baseUm, n: 0, source: "research" };
        }
      }
      function csFor(brewer, gid) {
        var um = typeof BREWER_UM === "object" && BREWER_UM[brewer] ? BREWER_UM[brewer] : 750;
        var r = csRoast(),
          pr = csProcess();
        var _ad = null;
        try {
          _ad = adaptedUm(brewer, typeof logMethod === "function" ? logMethod() : "", um);
          if (_ad && _ad.um > 0) um = _ad.um;
        } catch (e) {}
        um = Math.round(um * r.f * pr.f);
        try {
          window.CS_ADAPT = _ad;
        } catch (e) {}
        var g = typeof GRINDERS === "object" ? GRINDERS[gid] : null;
        if (!g) return { txt: um + "um", um: um, warn: null };
        var range = gRange(um, gid);
        if (g.um === 0) return { txt: um + "um (" + t("csAbs") + ")", um: um, warn: range };
        var c = umToClicks(um, gid);
        /* show the dial reading when the grinder has one, with the clicks in brackets so
    the number is still checkable */
        var d = dialTxt(gid, c);
        if (d)
          return {
            txt: d + "  (" + Math.round(c) + " " + t("csClicks") + ")",
            um: um,
            warn: range,
          };
        return { txt: "~" + Math.round(c) + " " + t("csClicks"), um: um, warn: range };
      }
      function csWarnText(w, gid) {
        if (!w || w === "ok") return "";
        var g = GRINDERS[gid];
        var n = g ? g.n : gid;
        if (w === "fine") return t("csTooFine").replace("{g}", n).replace("{v}", g.min);
        return t("csTooCoarse").replace("{g}", n).replace("{v}", g.max);
      }

      /* replace the 6-row English dump with a single contextual line */
      function renderColdStart() {
        var box = document.getElementById("coldstartbox");
        if (!box) return;
        if (typeof GRINDERS !== "object" || typeof BREWER_UM !== "object") {
          box.innerHTML = "";
          return;
        }
        var gid = null;
        try {
          gid = lastGrinder() || ownedGrinders()[0];
        } catch (e) {}
        var brewer = csBrewer();
        if (!gid || !brewer) {
          box.innerHTML = "<div class='csS'>" + t("csPick") + "</div>";
          return;
        }
        var g = GRINDERS[gid],
          r = csRoast(),
          c = csFor(brewer, gid);
        var w = csWarnText(c.warn, gid);
        box.innerHTML =
          "<div class='cs" +
          (w ? " csbad" : "") +
          "'><div class='csHd'>" +
          t("csT") +
          "</div>" +
          "<div class='csV'>" +
          (w ? "--" : c.txt) +
          "</div>" +
          "<div class='csS'>" +
          brewer +
          " " +
          t("csOn") +
          " " +
          (g ? g.n : gid) +
          " · " +
          roastWord(r.v) +
          ". " +
          t("csHint") +
          _csTuned() +
          "</div>" +
          (w ? "<div class='cswarn'>" + w + "</div>" : "") +
          "</div>";
      }

      /* mirror it into the filter form next to the grind field, where the decision happens */
      /* Which BREWER_UM key does the current method mean?
   The advisor used to key ONLY off FBREWER, the filter brewer chip. On espresso or
   soup FBREWER is '' forever, so it could never fire - and the box itself lived in
   #setPanel on the INSIGHTS tab, collapsed, two tabs from the form. Oscar: "I also
   could not find the grinder starting point info". It was not findable.
   BREWER_UM already had Espresso 340 and Soup 500 from GRIND_RESEARCH.md; nothing
   ever asked for them. */
      function csBrewer() {
        var m = "";
        try {
          m = logMethod();
        } catch (e) {}
        if (m === "espresso") return "Espresso";
        if (m === "soup") {
          var sr = localStorage.getItem("soupRatio") || "1:3-4";
          var k = "Soup " + sr;
          if (typeof BREWER_UM === "object" && BREWER_UM[k]) return k;
          return "Soup 1:3-4";
        }
        return typeof FBREWER !== "undefined" && FBREWER ? FBREWER : null;
      }
      /* the grind field of whichever form is showing */
      function csHost() {
        var m = "";
        try {
          m = logMethod();
        } catch (e) {}
        return document.getElementById("gset");
      }
      function _csTuned() {
        try {
          var a = window.CS_ADAPT;
          return a && a.source === "yours" ? " · " + t("csTuned").replace("{n}", a.n) : "";
        } catch (e) {
          return "";
        }
      }
      function csInline() {
        var host = csHost();
        if (!host) return;
        var id = "csInline",
          el = document.getElementById(id);
        var gid = null;
        try {
          gid = lastGrinder() || ownedGrinders()[0];
        } catch (e) {}
        var brewer = csBrewer();
        if (!gid || !brewer || typeof BREWER_UM !== "object") {
          if (el) el.remove();
          return;
        }
        /* the form can switch under us, so re-home it if it is in the wrong one */
        if (el && el.parentNode !== host.parentNode) {
          el.remove();
          el = null;
        }
        if (!el) {
          el = document.createElement("div");
          el.id = id;
          el.className = "cs";
          host.parentNode.insertBefore(el, host.nextSibling);
        }
        var g = GRINDERS[gid],
          r = csRoast(),
          pr = csProcess(),
          c = csFor(brewer, gid);
        var w = csWarnText(c.warn, gid);
        el.className = "cs" + (w ? " csbad" : "");
        /* Show WHY the number is what it is: the roast and process each get a line that
    names the direction and the size of their nudge. Oscar: "explicitly show that
    process and roast affect the starting point". */
        var factors = "";
        var ra = csAdjWord(r.f),
          pa = csAdjWord(pr.f);
        if (r.v && ra)
          factors +=
            "<div class='csfac'>" + roastWord(r.v) + ": " + ra.pct + "% " + ra.dir + "</div>";
        if (pr.v && pa)
          factors +=
            "<div class='csfac" +
            (pa.pct >= 8 ? " csfacbig" : "") +
            "'>" +
            pr.v +
            ": " +
            pa.pct +
            "% " +
            pa.dir +
            "</div>";
        if (pr.v && !pa) factors += "<div class='csfac'>" + pr.v + ": " + t("csNoAdj") + "</div>";
        el.innerHTML =
          "<div class='csHd'>" +
          t("csT") +
          "</div><div class='csV'>" +
          (w ? "--" : c.txt) +
          "</div>" +
          "<div class='csS'>" +
          brewer +
          " " +
          t("csOn") +
          " " +
          (g ? g.n : gid) +
          ". " +
          t("csHint") +
          _csTuned() +
          "</div>" +
          (factors ? "<div class='csfacs'>" + factors + "</div>" : "") +
          (w ? "<div class='cswarn'>" + w + "</div>" : "");
      }

      /* ---- add to home screen ----
   Android/Chrome fires beforeinstallprompt and we can trigger a real install.
   iOS does not support that event at all, so the only honest option there is to
   show the user where the Share button is. */
      var DEFERRED_PROMPT = null;
      function isStandalone() {
        return (
          (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) ||
          window.navigator.standalone === true
        );
      }
      function isIos() {
        return /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
      }
      function instDismissed() {
        try {
          return localStorage.getItem("instDismiss") === "1";
        } catch (e) {
          return false;
        }
      }
      function instRender() {
        var card = document.getElementById("instCard");
        if (!card) return;
        if (isStandalone() || instDismissed()) {
          card.style.display = "none";
          return;
        }
        var btn = document.getElementById("instBtn"),
          ios = document.getElementById("instIos");
        if (DEFERRED_PROMPT) {
          card.style.display = "";
          btn.style.display = "";
          ios.style.display = "none";
          return;
        }
        if (isIos()) {
          card.style.display = "";
          btn.style.display = "none";
          ios.style.display = "flex";
          return;
        }
        card.style.display = "none";
      }
      window.addEventListener("beforeinstallprompt", function (e) {
        e.preventDefault();
        DEFERRED_PROMPT = e;
        instRender();
      });
      window.addEventListener("appinstalled", function () {
        DEFERRED_PROMPT = null;
        var c = document.getElementById("instCard");
        if (c) c.style.display = "none";
      });
      (function () {
        var b = document.getElementById("instBtn");
        if (b)
          b.onclick = function () {
            if (!DEFERRED_PROMPT) return;
            DEFERRED_PROMPT.prompt();
            DEFERRED_PROMPT.userChoice.then(function () {
              DEFERRED_PROMPT = null;
              instRender();
            });
          };
        var x = document.getElementById("instX");
        if (x)
          x.onclick = function () {
            try {
              localStorage.setItem("instDismiss", "1");
            } catch (e) {}
            var c = document.getElementById("instCard");
            if (c) c.style.display = "none";
          };
      })();
      if ("serviceWorker" in navigator) {
        window.addEventListener("load", function () {
          var _swv = typeof BUILD !== "undefined" && BUILD ? BUILD : "0";
          navigator.serviceWorker
            .register("sw.js?v=" + encodeURIComponent(_swv))
            .catch(function () {});
        });
      }

      /* ---- grinder math with a zero-point offset ----
   Old model: um = clicks * step. That assumes click 0 is burr contact, which is
   true for the hand grinders but wrong for the Sculptors (the 078 bottoms out at
   370um, the 078S at 235um). off defaults to 0, so anything without measured data
   behaves exactly as before. */
      function gOff(g) {
        return g && typeof g.off === "number" ? g.off : 0;
      }
      function clicksToUm(clicks, gid) {
        var g = GRINDERS[gid];
        if (!g) return null;
        if (g.um === 0) return clicks;
        return gOff(g) + clicks * effUm(g);
      }
      /* Both directions use the EFFECTIVE gap, not the published travel. The converter
   had the same bug as the advisor: it round-trips through um, so every
   conical->flat conversion was out by the same ~3.3x. */
      function umToClicks(um, gid) {
        var g = GRINDERS[gid];
        if (!g) return null;
        if (g.um === 0) return Math.round(um);
        return (um - gOff(g)) / effUm(g);
      }
      /* out of range? returns null when we have no measured range for that grinder */
      function gRange(um, gid) {
        var g = GRINDERS[gid];
        if (!g || typeof g.min !== "number" || typeof g.max !== "number") return null;
        if (um < g.min) return "fine";
        if (um > g.max) return "coarse";
        return "ok";
      }
      function convertGrind(val, fromId, toId) {
        var um = clicksToUm(val, fromId);
        if (um == null) return null;
        var c = umToClicks(um, toId);
        if (c == null) return null;
        var g = GRINDERS[toId];
        if (g && g.um === 0) return Math.round(um);
        return Math.round(c * 10) / 10;
      }

      var HELP = {
        role: {
          en: "Full gives you brewing, logging and gear. Log & manage hides the machine controls and keeps logging, beans, rotation and insights. Change it any time.",
          es: "Completo te da preparación, registro y equipo. Solo registro oculta los controles de la máquina y deja el registro, cafés, rotación y análisis. Puedes cambiarlo cuando quieras.",
        },
        methods: {
          en: "Espresso is a normal 6 to 9 bar shot. Soup is a low pressure, fast flow shot, usually under 2 bar, common with modern light roasts. Filter is pour over. Pick any combination.",
          es: "Espresso es un shot normal de 6 a 9 bar. Soup es un shot de baja presión y flujo rápido, normalmente bajo 2 bar, comun con tuestes claros modernos. Filtrado es vertido. Elige las que quieras.",
        },
        hw: {
          en: "This only changes what gets filled in for you. Scale and timer means you type the numbers. A BLE scale fills weight, time and flow. A Gaggiuino fills the whole pressure and flow curve.",
          es: "Esto solo cambia lo que se rellena solo. Báscula y cronometro significa que tu escribes los números. Una báscula BLE rellena peso, tiempo y flujo. Un Gaggiuino rellena toda la curva de presión y flujo.",
        },
        grinders: {
          en: "Pick the ones you own. Only those appear when logging, so the list stays short. It also lets the converter translate a setting between your grinders.",
          es: "Elige los que tienes. Solo esos aparecen al registrar, así la lista queda corta. Tambien deja que el conversor traduzca un ajuste entre tus molinos.",
        },
        rotation: {
          en: "How the next coffee is suggested. Use oldest brews your oldest bag first, less waste. Keep it interesting picks something different from what is open. Peak flavor picks beans in their best rest window. Balanced mixes all three.",
          es: "Cómo se sugiere el siguiente café. Usar el más viejo prepara primero tu bolsa más vieja, menos desperdicio. Manten la variedad elige algo distinto a lo abierto. Sabor óptimo elige granos en su mejor ventana de reposo. Equilibrado mezcla los tres.",
        },
        conv: {
          en: "Same burr gap, different dial. Enter a setting on one grinder and get the equivalent on another. It is a starting point, not a guarantee: burr shape changes the cup even at the same gap.",
          es: "Misma separacion de fresas, otro dial. Escribe un ajuste de un molino y obten el equivalente en otro. Es un punto de partida, no una garantia: la forma de las fresas cambia la taza aunque la separacion sea igual.",
        },
        water: {
          en: "Water changes taste more than most people expect. Magnesium lifts acidity and clarity. Calcium adds body and sweetness. High alkalinity flattens and mutes. Log it and the insights will correlate it with your ratings.",
          es: "El agua cambia el sabor más de lo que la gente espera. El magnesio levanta la acidez y la claridad. El calcio da cuerpo y dulzor. La alcalinidad alta aplana y apaga. Registrala y el análisis la correlacionara con tus notas.",
        },
        freq: {
          en: "How often the insights digest is generated. It needs a few rated brews before it can say anything useful. Off stops it entirely.",
          es: "Cada cuánto se genera el análisis. Necesita varias preparaciones calificadas antes de decir algo útil. Apagar lo detiene del todo.",
        },
        sheet: {
          en: "Your data lives in your own Google Sheet, in your own Google account. Nobody else can read it, including me. It is what keeps your history when your browser clears itself.",
          es: "Tus datos viven en tu propia Hoja de Google, en tu propia cuenta. Nadie más puede leerlos, ni yo. Es lo que conserva tu historial cuando el navegador se limpia solo.",
        },
        roast: {
          en: "Roast level shifts the starting grind. Lighter roasts are denser and start finer; darker roasts are more soluble and start coarser. It is a nudge, not a rule.",
          es: "El nivel de tueste mueve la molienda inicial. Los tuestes claros son más densos y empiezan más fino; los oscuros son más solubles y empiezan más grueso. Es un empujon, no una regla.",
        },
      };
      function helpToggle(key, btn) {
        var box = btn.nextSibling;
        if (box && box.className === "helpbox") {
          box.parentNode.removeChild(box);
          btn.classList.remove("on");
          return;
        }
        var d = document.createElement("div");
        d.className = "helpbox";
        d.textContent = (HELP[key] && HELP[key][LANG]) || (HELP[key] && HELP[key].en) || "";
        btn.parentNode.insertBefore(d, btn.nextSibling);
        btn.classList.add("on");
      }
      function addHelp(el, key) {
        /* The guard was el.dataset.help - an ATTRIBUTE. applyLang() does
       el.textContent = t(el.getAttribute('data-i18n'))
     for every [data-i18n] element, which wipes that element's CHILDREN, including
     the '?' span this function appends. The attribute survives, so addHelp then
     early-returned forever and the bubble never came back until a reload.
     Measured: 12 bubbles on load, 5 after one setLang(), and wireHelp() could not
     restore them. Spanish is the default and the toggle is in the header, so this
     was the normal path, not an edge case.
     Guard on the span itself, which is the thing we actually care about. */
        if (!el) return;
        if (el.querySelector && el.querySelector(":scope > .helpq")) return;
        var b = document.createElement("span");
        b.className = "helpq";
        b.textContent = "?";
        b.setAttribute("role", "button");
        b.setAttribute("aria-label", "help");
        b.onclick = function (e) {
          e.stopPropagation();
          helpToggle(key, b);
        };
        el.appendChild(b);
      }
      function wireHelp() {
        var map = [
          ["#wizRole", "role"],
          ["#rolechips", "role"],
          ["#wizMethods", "methods"],
          ["#wizHw", "hw"],
          ["#wizGrinders", "grinders"],
          ["#rotmodechips", "rotation"],
          ["#convTool .toolhd", "conv"],
          ["#insfreqchips", "freq"],
          ["#gwaterchips", "water"],
          ["#wahw", "hw"],
        ];
        map.forEach(function (m) {
          var el = document.querySelector(m[0]);
          if (!el) return;
          var host = el.previousElementSibling;
          if (host && /^(DIV|LABEL|SPAN|B)$/.test(host.tagName) && host.textContent.length < 60)
            addHelp(host, m[1]);
          else addHelp(el, m[1]);
        });
        var froast = document.getElementById("roast");
        if (froast && froast.previousElementSibling)
          addHelp(froast.previousElementSibling, "roast");
        /* the 'sheet' help used to hang off the template link's step. That step is gone;
     the Drive step replaced it, so the help follows rather than dying with it. */
        var wt = document.getElementById("wizDriveStep");
        if (wt) {
          var hd = wt.querySelector("b");
          if (hd) addHelp(hd, "sheet");
        }
      }

      /* ---- freeze form now uses the same coffee DB as logging ----
   The Inventory sheet already had roast and process columns; invFreeze_ already
   reads p.roast and p.process. Only the form was missing. Options are cloned from
   the log selects so there is one source of truth. */
      function cloneOpts(fromId, toId) {
        var src = document.getElementById(fromId),
          dst = document.getElementById(toId);
        if (!src || !dst || !src.options || !src.options.length) return false;
        if (dst.options.length === src.options.length) return true; // already done
        var keep = dst.value;
        dst.innerHTML = "";
        Array.prototype.forEach.call(src.children, function (node) {
          dst.appendChild(node.cloneNode(true));
        });
        if (keep) dst.value = keep;
        return true;
      }
      function invSelectsInit() {
        cloneOpts("roaster", "invroaster");
        cloneOpts("roast", "invroast");
        cloneOpts("process", "invprocess");
        /* The coffee-name datalist used to be filled from INV here. INV never existed,
     so the list was never populated and the autocomplete never appeared. Removed
     rather than left as a promise. */
      }
      /* prefill the rest of the bag's details when the coffee name matches one you own */
      /* invPrefill REMOVED. It read INV, which never existed, so it hit `return` on its
   second line every single time it was called. The freeze-form autofill it was
   supposed to provide has never worked for anyone. */

      /* =====================================================================
   Espresso extras. GBASKET/GPREP/GPAPER mirror the filter form's
   FBREWER/FAGIT/FPAPER pattern so both forms behave the same way.
   ===================================================================== */
      var GBASKET = "",
        GPREP = "",
        GPAPER = "";
      try {
        GBASKET = localStorage.getItem("gbasket") || "";
      } catch (e) {}
      var BASKETS = ["Stock", "IMS", "Scott Rao Filter3", "VST", "Pesado", "Other"];
      var PREPS = ["WDT", "WDT + RDT", "RDT", "none"];
      var BASKET_PAPERS = ["none", "bottom", "top", "top + bottom"];
      function renderEspExtras() {
        if (typeof chipRow !== "function") return;
        chipRow(
          "gbasketchips",
          BASKETS,
          GBASKET,
          function (v) {
            GBASKET = v;
            try {
              localStorage.setItem("gbasket", v);
            } catch (e) {}
          },
          renderEspExtras,
        );
        chipRow(
          "gprepchips",
          PREPS,
          GPREP,
          function (v) {
            GPREP = v;
          },
          renderEspExtras,
        );
        chipRow(
          "gpaperchips",
          BASKET_PAPERS,
          GPAPER,
          function (v) {
            GPAPER = v;
          },
          renderEspExtras,
        );
      }
      /* live ratio + the band check. RATIO_BAND and ratioInBand() existed but were
   dead code: no espresso ratio was ever produced, so nothing could call them. */
      function gtimeFmt() {
        /* iOS numpad has no colon, so accept digits and format M:SS. 1-2 digits stay
     as seconds (soup); 3-4 digits become minutes:seconds. toSecs parses both. */
        var e = document.getElementById("gtime");
        if (!e) return;
        var d = e.value.replace(/[^0-9]/g, "");
        if (d.length > 4) d = d.slice(0, 4);
        e.value = d.length > 2 ? d.slice(0, d.length - 2) + ":" + d.slice(-2) : d;
      }
      function gRatioApply() {
        var ri = document.getElementById("gratioIn"),
          d = document.getElementById("dose"),
          y = document.getElementById("gyield");
        if (!ri || !d || !y) return;
        var rv = parseFloat(ri.value),
          dv = parseFloat(d.value);
        if (!isNaN(rv) && rv > 0 && !isNaN(dv) && dv > 0) {
          y.value = Math.round(dv * rv * 10) / 10;
          try {
            gRatioLive();
          } catch (e) {}
        }
      }
      function gRatioLive() {
        var el = document.getElementById("gratioLive");
        if (!el) return;
        var d = parseFloat((document.getElementById("dose") || {}).value);
        var y = parseFloat((document.getElementById("gyield") || {}).value);
        if (!d || !y || d <= 0) {
          el.textContent = "";
          el.style.color = "";
          return;
        }
        var ratio = y / d;
        var method = (document.getElementById("type") || {}).value || "";
        if (!method) method = typeof M_SOUP !== "undefined" && M_SOUP ? "soup" : "espresso";
        var txt = "1:" + ratio.toFixed(2);
        var band = typeof RATIO_BAND === "object" ? RATIO_BAND[method] : null;
        if (method === "soup") {
          var _sr;
          try {
            _sr = localStorage.getItem("soupRatio");
          } catch (e) {}
          _sr = _sr || "1:3-4";
          band = { "1:3-4": [2.5, 5], "1:5-8": [4.5, 9], "1:10": [8, 12] }[_sr] || [2.5, 11];
        }
        if (band) {
          if (ratio < band[0])
            txt += "  " + t("ratioTight").replace("{a}", band[0]).replace("{b}", band[1]);
          else if (ratio > band[1])
            txt += "  " + t("ratioLong").replace("{a}", band[0]).replace("{b}", band[1]);
          else txt += "  " + t("ratioOk");
        }
        el.textContent = txt;
        el.style.color =
          band && (ratio < band[0] || ratio > band[1]) ? "var(--warn)" : "var(--dim)";
      }

      /* =====================================================================
   GAP 2: filter varietal + process, cloned from the espresso selects so
   there is a single source of truth for the lists.
   ===================================================================== */
      function filterSelectsInit() {
        cloneOpts("varietal", "fvarietal");
        cloneOpts("process", "fprocess");
        /* roaster and roast were never cloned, so the filter form's Tostador select had
     exactly ONE option ("-") since the day it shipped, while #roaster next to it
     had 46. An empty <select> does not throw, so nothing ever reported it. */
        cloneOpts("roaster", "froaster");
        cloneOpts("roast", "froast");
      }

      /* =====================================================================
   GAP 3: WATERS held acid/body/note per water and was never read once.
   Show the note under whichever water is selected, on both forms.
   ===================================================================== */
      function waterNote(sel) {
        if (typeof WATERS !== "object" || !sel) return "";
        var w = WATERS[sel];
        return w && w.note ? w.note : "";
      }
      function renderWaterNotes() {
        var pairs = [
          ["gwaterchips", typeof GWATER !== "undefined" ? GWATER : ""],
          ["fwaterchips", typeof FWATER !== "undefined" ? FWATER : ""],
        ];
        pairs.forEach(function (p) {
          var box = document.getElementById(p[0]);
          if (!box) return;
          var id = p[0] + "_note",
            el = document.getElementById(id);
          var note = waterNote(p[1]);
          if (!note) {
            if (el) el.remove();
            return;
          }
          if (!el) {
            el = document.createElement("div");
            el.id = id;
            el.className = "csS";
            el.style.cssText = "margin:2px 0 8px 2px;line-height:1.5";
            box.parentNode.insertBefore(el, box.nextSibling);
          }
          if (el.textContent !== note) el.textContent = note;
        });
      }

      /* Any comma in a free text field would break LogSink's split(",") parser and
   shift every later column. Semicolon keeps the meaning readable and guarantees
   the row stays 23 wide. Newlines would break the row entirely. */
      function csvSafe(v) {
        if (v === undefined || v === null) return "";
        return String(v).replace(/\s+/g, " ").replace(/,/g, ";").trim();
      }

      /* Column order must match LogSink.gs COLS exactly. If you add a column there,
   add it here in the same position. */
      var COLNAMES = [
        "shot_id",
        "timestamp",
        "coffee",
        "roaster",
        "varietal",
        "process",
        "roast",
        "type",
        "dose_g",
        "yield_g",
        "ratio",
        "duration_s",
        "peak_bar",
        "avg_flow_mls",
        "temp_c",
        "rating",
        "brewer",
        "grind_setting",
        "water",
        "prep",
        "paper",
        "taste_tag",
        "bloom_s",
        "region",
        "basket",
        "agitation",
        "brew_water_g",
        "grind_um",
      ];
      function colsToParams(cols) {
        var out = [];
        for (var i = 0; i < COLNAMES.length; i++) {
          var v = cols[i];
          if (v === undefined || v === null || v === "") continue;
          out.push(COLNAMES[i] + "=" + encodeURIComponent(v));
        }
        return out.join("&");
      }

      /* Brand and proper nouns must never be translated, by us or by the browser.
   Chrome offers to auto-translate any page whose lang it has to guess, and it
   happily turns "BrewPilot" into "PrepararPilot". Two defences:
     - <html lang> is declared and kept in sync, so Chrome knows and stops guessing
     - the brand carries translate="no" so even a manual translate leaves it alone */
      function protectProperNouns() {
        var names = [
          "BrewPilot",
          "Gaggiuino",
          "Gaggia",
          "Google",
          "Telegram",
          "GitHub",
          "V60",
          "Chemex",
          "Kalita",
          "AeroPress",
        ];
        document.querySelectorAll(".brand,#appTitle,.appbar b,title").forEach(function (el) {
          el.setAttribute("translate", "no");
          el.classList.add("notranslate");
        });
        /* the brand contains a <span>, so a childless-only check would miss it */
        // any element whose entire text is a proper noun
        var w = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT, null, false),
          n;
        while ((n = w.nextNode())) {
          if (n.children.length) continue;
          var t = (n.textContent || "").trim();
          if (t && names.indexOf(t) >= 0 && !n.hasAttribute("translate")) {
            n.setAttribute("translate", "no");
            n.classList.add("notranslate");
          }
        }
      }

      /* =====================================================================
   Custom roasters / processes persist locally.

   The lists are per-browser (localStorage). They are NOT sent anywhere:
   there is no central server in this design, every user owns their own
   Sheet. shareCustom() lets a tester volunteer the list if they want to.
   ===================================================================== */
      var MYLIST_KEYS = {
        roaster: "myRoasters",
        process: "myProcesses",
        invroaster: "myRoasters",
        fprocess: "myProcesses",
      };

      function myList(kind) {
        try {
          var v = JSON.parse(localStorage.getItem(MYLIST_KEYS[kind] || "my_" + kind) || "[]");
          return Array.isArray(v) ? v : [];
        } catch (e) {
          return [];
        }
      }
      function myListAdd(kind, val) {
        val = String(val || "").trim();
        if (!val) return false;
        if (val.length > 60) val = val.slice(0, 60);
        var key = MYLIST_KEYS[kind] || "my_" + kind;
        var list = myList(kind);
        /* case-insensitive dedupe, and never shadow one already in the shipped DB */
        var lower = list.map(function (x) {
          return x.toLowerCase();
        });
        if (lower.indexOf(val.toLowerCase()) >= 0) return false;
        var base = document.getElementById(
          kind === "invroaster" ? "roaster" : kind === "fprocess" ? "process" : kind,
        );
        if (base) {
          var exists = Array.prototype.some.call(base.options, function (o) {
            return o.value && o.value.toLowerCase() === val.toLowerCase() && o.value !== "Other";
          });
          if (exists) return false;
        }
        list.push(val);
        try {
          localStorage.setItem(key, JSON.stringify(list));
        } catch (e) {
          return false;
        }
        return true;
      }
      function myListRemove(kind, val) {
        var key = MYLIST_KEYS[kind] || "my_" + kind;
        var list = myList(kind).filter(function (x) {
          return x !== val;
        });
        try {
          localStorage.setItem(key, JSON.stringify(list));
        } catch (e) {}
      }
      /* Insert a "Yours" optgroup at the top of a select and keep it in sync. */
      function syncYours(selId, kind) {
        var sel = document.getElementById(selId);
        if (!sel) return;
        var list = myList(kind);
        var og = sel.querySelector("optgroup[data-yours]");
        if (!list.length) {
          if (og) og.remove();
          return;
        }
        if (!og) {
          og = document.createElement("optgroup");
          og.setAttribute("data-yours", "1");
          var first = sel.querySelector("optgroup");
          if (first) sel.insertBefore(og, first);
          else sel.appendChild(og);
        }
        og.label = t("yoursGroup");
        var want = list.join("|");
        if (og.getAttribute("data-sig") === want) return;
        og.setAttribute("data-sig", want);
        og.innerHTML = "";
        list.forEach(function (v) {
          var o = document.createElement("option");
          o.value = v;
          o.textContent = v;
          o.setAttribute("translate", "no");
          og.appendChild(o);
        });
      }
      function syncAllYours() {
        syncYours("roaster", "roaster");
        syncYours("invroaster", "roaster");
        syncYours("process", "process");
        syncYours("fprocess", "process");
        syncYours("invprocess", "process");
      }
      /* Capture whatever was typed into an Other box, then select it next time. */
      function rememberOther(selId, inpId, kind) {
        var sel = document.getElementById(selId),
          inp = document.getElementById(inpId);
        if (!sel || !inp) return "";
        if (sel.value !== "Other") return sel.value;
        var v = (inp.value || "").trim();
        if (!v) return "";
        if (myListAdd(kind, v)) {
          syncAllYours();
        }
        try {
          sel.value = v;
        } catch (e) {}
        return v;
      }
      /* Consent based: copies the list so a tester can send it if they choose. */
      function shareCustom() {
        var NL = String.fromCharCode(10);
        var r = myList("roaster"),
          p = myList("process");
        if (!r.length && !p.length) {
          alert(t("shareNone"));
          return;
        }
        var txt = "BrewPilot custom entries" + NL;
        if (r.length)
          txt +=
            NL +
            "Roasters:" +
            NL +
            r
              .map(function (x) {
                return "- " + x;
              })
              .join(NL);
        if (p.length)
          txt +=
            NL +
            NL +
            "Processes:" +
            NL +
            p
              .map(function (x) {
                return "- " + x;
              })
              .join(NL);
        var done = function () {
          alert(t("shareCopied"));
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(txt).then(done, function () {
            prompt(t("shareManual"), txt);
          });
        } else {
          prompt(t("shareManual"), txt);
        }
      }

      /* Placed at runtime rather than in the markup: the settings panel is built by
   the shell and is always reachable, unlike the durability banner which hides
   itself once a sheet is connected. */
      function placeShareBtn() {
        if (document.getElementById("shareCustomBtn")) return;
        var panel = document.getElementById("setPanel");
        if (!panel) return;
        if (!myList("roaster").length && !myList("process").length)
          return; /* nothing to share yet */
        var b = document.createElement("button");
        b.id = "shareCustomBtn";
        b.className = "off";
        b.style.cssText = "width:100%;margin-top:10px";
        b.textContent = t("shareBtn");
        b.onclick = shareCustom;
        panel.appendChild(b);
      }

      /* =====================================================================
   One sheet prompt at a time.

   Before this, a user with no sheet saw: the durability banner on all four
   tabs, plus a welcome card on Home, plus TWO "Set up your Google Sheet"
   buttons and a lock card on Insights. Four prompts on one screen, five
   across the app, all asking for the same thing. It read as desperate.

   Worse, duraRender showed the banner unconditionally, so a brand new user
   with zero brews was warned that their brews might be lost. Nothing to lose.

   Rules now:
     - nothing logged and no sheet  -> welcome card, Home only, once
     - brews at risk and no sheet   -> durability banner, Home only (real risk)
     - Insights tab and no sheet    -> the lock card, because that IS the reason
     - connected                    -> the confirmation, Home only
     - the standalone setup buttons  -> gone, they duplicated whatever card was up
   Settings always has a connect field; that is a control, not a nag.
   ===================================================================== */
      function sheetCtas() {
        /* Was WEBHOOK() only, which meant a Google connected user still saw 'connect a sheet' everywhere. dataMode() knows about all three backends. */
        var connected = false;
        try {
          connected = dataMode() !== "local";
        } catch (e) {}
        var rows = 0;
        try {
          rows = localRows().length;
        } catch (e) {}
        var panel = document.querySelector(".tabpanel.on");
        var tab = panel ? panel.id : "";
        var onHome = tab === "tab-home";

        var dura = document.getElementById("duraBanner");
        var wel = document.getElementById("welcome");

        /* the banner earns its place only when something can actually be lost */
        var atRisk = !connected && rows > 0;
        /* Nothing logged anywhere means nothing to protect. A '0 brews are in your
     Google Sheet' banner is noise, and it was permanently parked on Home. */
        var known = rows;
        try {
          known = Math.max(rows, (IROWS || []).length);
        } catch (e) {}
        if (dura) dura.style.display = onHome && known > 0 && (atRisk || connected) ? "" : "none";

        /* welcome: only before anything is at risk, so the two never stack */
        if (wel) wel.style.display = onHome && !connected && !atRisk ? "" : "none";

        /* these duplicated whichever card was already on screen */
        var dead = document.querySelectorAll('[data-i18n="setupSheet"]');
        Array.prototype.forEach.call(dead, function (b) {
          b.style.display = "none";
        });
      }

      /* =====================================================================
   Hardware upsell.

   Tapping "+ BLE scale" or "+ Gaggiuino" used to set M_HW, reveal a device
   key field and grey some labels. It LOOKED like it did something, but the
   webapp cannot talk to a BLE scale or a Gaggiuino: no device, no capture.
   Selecting it changed nothing you could feel, which is worse than saying no.

   Now the tap explains what the hardware actually does, admits plainly that
   the webapp alone cannot do it, and says the app is fine without it. That is
   the honest version of the upsell: no fake scarcity, no dark pattern.
   ===================================================================== */
      var HWINFO = {
        device: {
          t: { en: "What the BrewPilot device does", es: "Qué hace el dispositivo BrewPilot" },
          b: {
            en: "It sits on the counter and does the part you do not want to do: watch, measure and write it down. What it is worth depends on what you connect to it.",
            es: "Se queda en la barra y hace la parte que no quieres hacer: mirar, medir y anotar. Lo que vale depende de lo que le conectes.",
          },
          groups: [
            {
              h: { en: "On its own", es: "Solo el dispositivo" },
              i: [
                {
                  en: "LED ring on the machine: state at a glance, no phone in your hand",
                  es: "Anillo LED en la máquina: el estado de un vistazo, sin sacar el teléfono",
                },
                {
                  en: "Alerts to your phone when something needs you",
                  es: "Avisos al teléfono cuando algo te necesita",
                },
                {
                  en: "Its own panel at brewpilot.local, no internet needed",
                  es: "Su propio panel en brewpilot.local, sin internet",
                },
              ],
            },
            {
              h: { en: "With a BLE scale", es: "Con una báscula BLE" },
              topic: "scale",
              i: [
                { en: "Live weight while the shot pours", es: "Peso en vivo mientras cae el shot" },
                {
                  en: "Flow worked out from the weight curve, not just the final number",
                  es: "Flujo calculado de la curva de peso, no solo el número final",
                },
                {
                  en: "Brew seconds counted for you, start to stop",
                  es: "Segundos de extracción contados solos, de inicio a fin",
                },
                {
                  en: "Yield and time land in your log without typing",
                  es: "Salida y tiempo entran a tu registro sin escribir",
                },
                {
                  en: "Nudge mid pour when the flow runs away",
                  es: "Aviso a media extracción cuando el flujo se dispara",
                },
              ],
            },
            {
              h: { en: "With your Gaggiuino", es: "Con tu Gaggiuino" },
              topic: "gaggiuino",
              i: [
                {
                  en: "Knows when the machine is really at temperature, not just the light",
                  es: "Sabe cuándo la máquina está de verdad en temperatura, no solo la luz",
                },
                {
                  en: "Predictive warm-up: starts heating before you walk in",
                  es: "Calentamiento predictivo: empieza a calentar antes de que llegues",
                },
                {
                  en: "Auto-off when you walk away and forget",
                  es: "Apagado automático cuando te vas y se te olvida",
                },
                {
                  en: "Full pressure, flow and temperature curve for every shot",
                  es: "Curva completa de presión, flujo y temperatura en cada shot",
                },
                {
                  en: "Spots the shot by itself, no buttons",
                  es: "Detecta el shot solo, sin botones",
                },
                {
                  en: "Reads the curve and tells you what kind of shot that was",
                  es: "Lee la curva y te dice qué tipo de shot fue",
                },
              ],
            },
          ],
        },
        scale: {
          t: {
            en: "A BLE scale needs the BrewPilot device",
            es: "Una báscula BLE necesita el dispositivo BrewPilot",
          },
          b: {
            en: "The device reads the scale live and writes the numbers down for you.",
            es: "El dispositivo lee la báscula en vivo y anota los números por ti.",
          },
          groups: [
            {
              h: { en: "What you get", es: "Lo que obtienes" },
              i: [
                { en: "Live weight while the shot pours", es: "Peso en vivo mientras cae el shot" },
                {
                  en: "Flow worked out from the weight curve, the number you cannot write by hand",
                  es: "Flujo calculado de la curva de peso, el número que no puedes anotar a mano",
                },
                {
                  en: "Brew seconds counted start to stop",
                  es: "Segundos de extracción contados de inicio a fin",
                },
                {
                  en: "Yield, time and flow logged without typing",
                  es: "Salida, tiempo y flujo registrados sin escribir",
                },
                {
                  en: "A nudge mid pour when the flow runs away",
                  es: "Un aviso a media extracción cuando el flujo se dispara",
                },
                {
                  en: "Works for filter too, no espresso machine needed",
                  es: "Sirve para filtrado también, sin máquina de espresso",
                },
              ],
            },
          ],
          gap: {
            en: "Without it: you type every number from memory after the fact, and flow never gets recorded at all. Flow is what explains why a shot ran fast, and there is no way to write it down by hand.",
            es: "Sin él: escribes cada número de memoria cuando ya acabaste, y el flujo no queda registrado nunca. El flujo es lo que explica por qué un shot corrió rápido, y no hay forma de anotarlo a mano.",
          },
        },
        gaggiuino: {
          t: {
            en: "Gaggiuino capture needs the BrewPilot device",
            es: "Capturar del Gaggiuino necesita el dispositivo BrewPilot",
          },
          b: {
            en: "Wired to your Gaggiuino, the device sees the machine itself, not just the cup.",
            es: "Conectado a tu Gaggiuino, el dispositivo ve la máquina misma, no solo la taza.",
          },
          groups: [
            {
              h: { en: "What you get", es: "Lo que obtienes" },
              i: [
                {
                  en: "Full pressure, flow and temperature curve for every shot",
                  es: "Curva completa de presión, flujo y temperatura en cada shot",
                },
                {
                  en: "Shots log themselves. You add taste and a rating, nothing else",
                  es: "Los shots se registran solos. Tú pones sabor y nota, nada más",
                },
                {
                  en: "Knows when the machine is really at temperature",
                  es: "Sabe cuándo la máquina está de verdad en temperatura",
                },
                {
                  en: "Predictive warm-up before you walk in",
                  es: "Calentamiento predictivo antes de que llegues",
                },
                { en: "Auto-off when you forget", es: "Apagado automático cuando se te olvida" },
                {
                  en: "Reads the curve and names the shot type",
                  es: "Lee la curva y nombra el tipo de shot",
                },
              ],
            },
          ],
          gap: {
            en: "Without it: you have the result but not the curve. You know the shot was good. You cannot see why, or repeat it on purpose.",
            es: "Sin él: tienes el resultado pero no la curva. Sabes que el shot salió bueno. No ves por qué, ni puedes repetirlo a propósito.",
          },
        },
        nudges: {
          t: {
            en: "Live nudges need the BrewPilot device",
            es: "Los avisos en vivo necesitan el dispositivo BrewPilot",
          },
          b: {
            en: "The device watches the shot as it pours and speaks up while you can still act: running fast at 12 seconds, channelling, pressure dropping early. A light on the machine, not a notification you read afterwards.",
            es: "El dispositivo mira el shot mientras corre y te avisa cuando todavía puedes hacer algo: vas rápido a los 12 segundos, hay canalización, la presión cae temprano. Una luz en la máquina, no una notificación que lees después.",
          },
          gap: {
            en: "Without it: every correction arrives one brew late. You find out it ran fast by tasting it, then guess the grind for tomorrow. The app can tell you what happened; only the device can tell you while it is happening.",
            es: "Sin él: cada corrección llega un café tarde. Te enteras de que corrió rápido probándolo, y adivinas la molienda para mañana. La app te dice qué pasó; solo el dispositivo te avisa mientras está pasando.",
          },
        },
      };
      function hwModal(kind) {
        var info = HWINFO[kind];
        if (!info) return;
        var m = document.getElementById("hwMask");
        if (!m) {
          m = document.createElement("div");
          m.id = "hwMask";
          m.className = "wizmask";
          m.innerHTML =
            "<div class='wizcard'><div class='hwT' id='hwT'></div><div class='hwB' id='hwB'></div>" +
            "<div id='hwGroups'></div><div class='hwOk' id='hwB2'></div>" +
            "<button class='grn' id='hwClose' style='width:100%;margin-top:14px'></button></div>";
          document.body.appendChild(m);
          m.onclick = function (e) {
            if (e.target === m) m.classList.remove("on");
          };
          document.getElementById("hwClose").onclick = function () {
            m.classList.remove("on");
          };
        }
        var L = typeof LANG !== "undefined" ? LANG : "en";
        var pick = function (o) {
          return o ? o[L] || o.en : "";
        };
        document.getElementById("hwT").textContent = pick(info.t);
        document.getElementById("hwB").textContent = pick(info.b);

        /* the feature ladder. Each group can point at another topic, so the device
     modal doubles as the way into the BLE and Gaggiuino pitches. */
        var g = document.getElementById("hwGroups");
        g.innerHTML = "";
        (info.groups || []).forEach(function (grp) {
          var head = document.createElement("div");
          head.className = "hwGH" + (grp.topic ? " hwGHlink" : "");
          head.textContent = pick(grp.h) + (grp.topic ? "  →" : "");
          if (grp.topic) {
            head.onclick = function () {
              hwModal(grp.topic);
            };
          }
          g.appendChild(head);
          var ul = document.createElement("div");
          ul.className = "hwList";
          (grp.i || []).forEach(function (it) {
            var li = document.createElement("div");
            li.className = "hwLi";
            var d = document.createElement("span");
            d.className = "hwDot";
            d.textContent = "·";
            var tx = document.createElement("span");
            tx.textContent = pick(it);
            li.appendChild(d);
            li.appendChild(tx);
            ul.appendChild(li);
          });
          g.appendChild(ul);
        });

        var b2 = document.getElementById("hwB2");
        var gap = pick(info.gap);
        b2.textContent = gap;
        b2.style.display = gap ? "" : "none";
        document.getElementById("hwClose").textContent = t("hwGot");
        m.classList.add("on");
      }

      /* Default the freeze date to today so the common case is one tap, while a bag
   that has been in the freezer a while can be backdated. The freshness rotation
   scores on this date, so a wrong one quietly skews which bag it suggests. */
      function invFreezeDateInit() {
        var el = document.getElementById("invfreeze_date");
        if (!el) return;
        if (!el.value) {
          var d = new Date(),
            p = function (n) {
              return (n < 10 ? "0" : "") + n;
            };
          el.value = d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate());
          el.max = el.value; /* you cannot have frozen it in the future */
        }
      }

      /* Cost tracking.
   Price is per bag: the number on the receipt. Per gram is derived, because
   that is the one that tells you whether a bag is actually expensive.
   Currency is stored per row, not as a global setting, because specialty is
   often priced in USD even when you are buying from Mexico, and a row should
   record what you actually paid. Aggregation can group by it later. */
      var INVBAG = "",
        INVCCY = "";
      try {
        INVBAG = localStorage.getItem("invbag") || "250";
      } catch (e) {
        INVBAG = "250";
      }
      try {
        INVCCY = localStorage.getItem("invccy") || "USD";
      } catch (e) {
        INVCCY = "USD";
      }
      var BAGSIZES = ["150", "250", "340", "500", "1000"];
      var CURRENCIES = ["USD", "MXN", "EUR", "GBP", "CAD", "AUD", "JPY"];

      function invCcyInit() {
        var sel = document.getElementById("invccy");
        if (!sel) return;
        if (sel.options.length) {
          sel.value = INVCCY;
          return;
        }
        CURRENCIES.forEach(function (c) {
          var o = document.createElement("option");
          o.value = c;
          o.textContent = c;
          o.setAttribute("translate", "no");
          sel.appendChild(o);
        });
        sel.value = INVCCY;
      }
      function invCcySet(v) {
        INVCCY = v || "USD";
        try {
          localStorage.setItem("invccy", INVCCY);
        } catch (e) {}
        invPerG();
      }
      function renderBagChips() {
        var box = document.getElementById("invbagchips");
        if (!box || typeof chipRow !== "function") return;
        var labels = BAGSIZES.map(function (g) {
          return g === "1000" ? "1kg" : g + "g";
        });
        chipRow(
          "invbagchips",
          labels,
          INVBAG === "1000" ? "1kg" : INVBAG + "g",
          function (v) {
            INVBAG = v === "1kg" ? "1000" : v.replace("g", "");
            try {
              localStorage.setItem("invbag", INVBAG);
            } catch (e) {}
            invPerG();
          },
          renderBagChips,
        );
      }
      /* Show per gram and per shot live. Currency codes, not symbols: $ means four
   different things in this list and the ambiguity is not worth the pixels. */
      function invPerG() {
        var out = document.getElementById("invPerGOut");
        if (!out) return;
        var p = parseFloat((document.getElementById("invprice") || {}).value);
        var b = parseFloat(INVBAG);
        if (!p || !b || p <= 0 || b <= 0) {
          out.textContent = "";
          return;
        }
        var perG = p / b,
          per18 = perG * 18;
        out.textContent =
          LANG === "es"
            ? INVCCY +
              " " +
              perG.toFixed(3) +
              " por gramo  ~  " +
              INVCCY +
              " " +
              per18.toFixed(2) +
              " por shot de 18g"
            : INVCCY +
              " " +
              perG.toFixed(3) +
              " per gram  ~  " +
              INVCCY +
              " " +
              per18.toFixed(2) +
              " per 18g shot";
      }

      /* "Connect my sheet" on the Home welcome card did nothing at all. Two bugs:

   1. The welcome card is in tab-home; setPanel is in tab-insights. Before the
      tabbed shell this was one long scrolling page, so scrollIntoView worked.
      Now the panel sits inside a hidden tabpanel, so display:block on it changes
      nothing you can see and scrollIntoView has nothing to scroll to.
   2. The handler set display='block' and THEN called toggleSettings(), which
      toggles. Seeing "not none", it set display='none' again. The button closed
      the very panel it was trying to open.

   openPanel(id, fn) already exists and ensures-open rather than toggling. Use it. */
      async function goConnectSheet() {
        /* One tap. Gate on a LIVE TOKEN, not just a linked sheet: gConnected() is true
     whenever GSHEET is set, so a relinked-but-expired session must still re-auth
     here instead of falling through to a jarring tab jump (the old /exec path). */
        try {
          if (!gConfigured()) {
            alert(t("gNotSetUp"));
            return;
          }
          if (!gTokenOk() || !GSHEET) {
            var ok = await gConnect();
            if (ok) {
              try {
                sheetCtas();
              } catch (e) {}
              try {
                renderGoogleCard();
              } catch (e) {}
              try {
                renderSheetStatus();
              } catch (e) {}
            }
            return;
          }
          /* already linked with a live token: confirm, do not navigate */
          try {
            renderSheetStatus();
          } catch (e) {}
          alert("Already connected to your BrewPilot Log");
        } catch (e) {}
      }

      /* =====================================================================
   INSIGHTS ENGINE (client side)

   Reads the raw sheet via action=rows and works out what is worth saying.
   Every function here takes rows and returns an array of strings. Adding a
   new insight means adding a function and listing it in INSIGHT_FNS. No
   Apps Script change, no user action.
   ===================================================================== */
      var IROWS = null,
        IINV = null,
        ICOLS = null,
        IINVCOLS = null;

      function iNum(v) {
        var n = parseFloat(v);
        return isFinite(n) ? n : null;
      }
      function iMean(a) {
        return a.length
          ? a.reduce(function (x, y) {
              return x + y;
            }, 0) / a.length
          : NaN;
      }
      function iGroup(rows, key) {
        var g = {};
        rows.forEach(function (r) {
          var k = r[key];
          if (!k) return;
          (g[k] = g[k] || []).push(r);
        });
        return g;
      }
      /* Pearson. Small n lies easily, so callers must gate on sample size. */
      function iCorr(xs, ys) {
        var n = xs.length;
        if (n < 4) return null;
        var mx = iMean(xs),
          my = iMean(ys);
        var num = 0,
          dx = 0,
          dy = 0;
        for (var i = 0; i < n; i++) {
          var a = xs[i] - mx,
            b = ys[i] - my;
          num += a * b;
          dx += a * a;
          dy += b * b;
        }
        if (dx <= 0 || dy <= 0) return null;
        return num / Math.sqrt(dx * dy);
      }

      /* Turn the raw arrays into objects keyed by column name. */
      function iBuild(data) {
        ICOLS = data.cols || [];
        for (var _ci = ICOLS.length; _ci < COLNAMES.length; _ci++) {
          ICOLS[_ci] = COLNAMES[_ci];
        }
        IINVCOLS = data.invCols || [];
        for (var _vi = IINVCOLS.length; _vi < INV_COLNAMES.length; _vi++) {
          IINVCOLS[_vi] = INV_COLNAMES[_vi];
        }
        IROWS = (data.shots || []).map(function (r, _i) {
          var o = {};
          ICOLS.forEach(function (c, i) {
            o[c] = r[i];
          });
          o.__row = _i + 2;
          return o;
        });
        IINV = (data.inv || []).map(function (r) {
          var o = {};
          IINVCOLS.forEach(function (c, i) {
            o[c] = r[i];
          });
          return o;
        });
      }
      /* iFetch REMOVED with /exec: it was the action=rows reader. iLoad's google
   branch reads the same rows through gRead, and iFromLocal covers everyone else. */

      /* ---------------------------------------------------------------- COST */
      /* Joins Shot Log to Inventory on coffee name. price_per_g comes from the sheet,
   which is the single source of truth: the client never recomputes it. */
      function iCostIndex() {
        var idx = {};
        (IINV || []).forEach(function (r) {
          var name = String(r.coffee || "")
            .trim()
            .toLowerCase();
          var ppg = iNum(r.price_per_g);
          if (!name || ppg === null) return;
          /* a coffee can be frozen more than once at different prices: keep the latest */
          idx[name] = {
            ppg: ppg,
            ccy: String(r.currency || "USD"),
            when: String(r.freeze_date || ""),
          };
        });
        return idx;
      }
      function iCostOf(row, idx) {
        var name = String(row.coffee || "")
          .trim()
          .toLowerCase();
        var e = idx[name];
        if (!e) return null;
        var dose = iNum(row.dose_g);
        if (dose === null) return null;
        return { cost: dose * e.ppg, ccy: e.ccy, ppg: e.ppg };
      }
      function insightsCost() {
        var out = [],
          idx = iCostIndex();
        if (!IROWS || !IROWS.length) return out;
        var priced = [];
        IROWS.forEach(function (r) {
          var c = iCostOf(r, idx);
          if (c) priced.push({ r: r, c: c });
        });
        if (priced.length < 3) return out;
        var ccy = priced[0].c.ccy;

        /* 1. what a month of coffee actually costs */
        var byMonth = {};
        priced.forEach(function (p) {
          var t = String(p.r.timestamp || "");
          var m = t.slice(0, 7);
          if (!/^\d{4}-\d{2}$/.test(m)) return;
          byMonth[m] = (byMonth[m] || 0) + p.c.cost;
        });
        var months = Object.keys(byMonth).sort();
        if (months.length) {
          var last = months[months.length - 1];
          out.push(
            t("insSpend")
              .replace("{m}", last)
              .replace("{v}", ccy + " " + byMonth[last].toFixed(0)),
          );
          if (months.length >= 3) {
            var avg = iMean(
              months.map(function (m) {
                return byMonth[m];
              }),
            );
            out.push(t("insSpendAvg").replace("{v}", ccy + " " + avg.toFixed(0)));
          }
        }

        /* 2. the cost of one cup, which is the number people actually feel */
        var costs = priced.map(function (p) {
          return p.c.cost;
        });
        out.push(t("insPerCup").replace("{v}", ccy + " " + iMean(costs).toFixed(2)));

        /* 3. does paying more actually buy a better cup?
        the whole point of tracking cost. Gate hard: needs spread and sample. */
        var rated = priced.filter(function (p) {
          return iNum(p.r.rating) !== null;
        });
        if (rated.length >= 8) {
          var ppgs = rated.map(function (p) {
            return p.c.ppg;
          });
          var rats = rated.map(function (p) {
            return iNum(p.r.rating);
          });
          var spread = Math.max.apply(null, ppgs) - Math.min.apply(null, ppgs);
          if (spread > 0) {
            var c = iCorr(ppgs, rats);
            if (c !== null) {
              if (c >= 0.35) out.push(t("insCostUp"));
              else if (c <= -0.35) out.push(t("insCostDown"));
              else out.push(t("insCostFlat").replace("{n}", rated.length));
            }
          }
        }

        /* 4. best value: highest rated per unit cost, when there is a real choice */
        if (rated.length >= 6) {
          var byC = {};
          rated.forEach(function (p) {
            var k = String(p.r.coffee);
            (byC[k] = byC[k] || []).push(p);
          });
          var rank = Object.keys(byC)
            .filter(function (k) {
              return byC[k].length >= 2;
            })
            .map(function (k) {
              return {
                name: k,
                avg: iMean(
                  byC[k].map(function (p) {
                    return iNum(p.r.rating);
                  }),
                ),
                ppg: byC[k][0].c.ppg,
              };
            })
            .filter(function (x) {
              return !isNaN(x.avg) && x.ppg > 0;
            });
          if (rank.length >= 2) {
            rank.sort(function (a, b) {
              return b.avg / b.ppg - a.avg / a.ppg;
            });
            out.push(t("insValue").replace("{c}", rank[0].name));
          }
        }
        return out;
      }

      /* --------------------------------------------------------------- WATER */
      /* The old .gs version compared water NAMES. WATERS carries acid/body numbers,
   so we can ask the better question: does the underlying property track your
   ratings, across every water you have used? That generalises to waters you
   have not tried yet, which a name comparison never can. */
      function insightsWater() {
        var out = [];
        if (!IROWS || typeof WATERS !== "object") return out;
        var rated = IROWS.filter(function (r) {
          return r.water && iNum(r.rating) !== null && WATERS[r.water];
        });
        if (rated.length < 6) return out;

        var acid = [],
          body = [],
          rats = [];
        rated.forEach(function (r) {
          var w = WATERS[r.water];
          if (typeof w.acid !== "number" || typeof w.body !== "number") return;
          acid.push(w.acid);
          body.push(w.body);
          rats.push(iNum(r.rating));
        });
        if (rats.length >= 6) {
          var ca = iCorr(acid, rats),
            cb = iCorr(body, rats);
          /* report the stronger axis only, and only if it is worth a sentence */
          var best = null;
          if (ca !== null && (cb === null || Math.abs(ca) >= Math.abs(cb)))
            best = { ax: "acid", c: ca };
          else if (cb !== null) best = { ax: "body", c: cb };
          if (best && Math.abs(best.c) >= 0.4) {
            var key =
              best.ax === "acid"
                ? best.c > 0
                  ? "insWAcidUp"
                  : "insWAcidDown"
                : best.c > 0
                  ? "insWBodyUp"
                  : "insWBodyDown";
            out.push(t(key).replace("{n}", rats.length));
          }
        }

        /* which water you actually rate best, when there is a fair comparison */
        var byW = iGroup(rated, "water");
        var opts = Object.keys(byW)
          .map(function (w) {
            return {
              w: w,
              n: byW[w].length,
              avg: iMean(
                byW[w].map(function (r) {
                  return iNum(r.rating);
                }),
              ),
            };
          })
          .filter(function (x) {
            return x.n >= 2 && !isNaN(x.avg);
          });
        if (opts.length >= 2) {
          opts.sort(function (a, b) {
            return b.avg - a.avg;
          });
          if (opts[0].avg - opts[opts.length - 1].avg >= 0.6) {
            out.push(
              t("insWBest")
                .replace("{w}", opts[0].w)
                .replace("{a}", opts[0].avg.toFixed(1))
                .replace("{b}", opts[opts.length - 1].avg.toFixed(1)),
            );
          }
        }
        return out;
      }

      /* -------------------------------------------------------------- TIMING */
      function insightsTiming() {
        var out = [];
        if (!IROWS) return out;
        var rows = IROWS.filter(function (r) {
          return iNum(r.duration_s) !== null && iNum(r.rating) !== null;
        });
        if (rows.length >= 6) {
          var c = iCorr(
            rows.map(function (r) {
              return iNum(r.duration_s);
            }),
            rows.map(function (r) {
              return iNum(r.rating);
            }),
          );
          if (c !== null && Math.abs(c) >= 0.4)
            out.push(t(c > 0 ? "insTimeUp" : "insTimeDown").replace("{n}", rows.length));
        }
        var br = IROWS.filter(function (r) {
          return iNum(r.ratio) !== null && iNum(r.rating) !== null;
        });
        if (br.length >= 6) {
          var c2 = iCorr(
            br.map(function (r) {
              return iNum(r.ratio);
            }),
            br.map(function (r) {
              return iNum(r.rating);
            }),
          );
          if (c2 !== null && Math.abs(c2) >= 0.4)
            out.push(t(c2 > 0 ? "insRatioUp" : "insRatioDown").replace("{n}", br.length));
        }
        return out;
      }

      var INSIGHT_FNS = [insightsCost, insightsWater, insightsTiming];
      function computeInsights() {
        var all = [];
        INSIGHT_FNS.forEach(function (fn) {
          try {
            all = all.concat(fn() || []);
          } catch (e) {}
        });
        return all;
      }

      /* Render client-computed insights into the panel. Falls back to whatever the
   Apps Script cached, so a user on an older LogSink still sees something. */
      async function renderClientInsights() {
        var box = document.getElementById("insText");
        if (!box) return;
        var src = await iLoad();
        var list = computeInsights();
        if (!list.length) {
          var n = (IROWS || []).length;
          box.textContent = n < 6 ? t("insNeedMore").replace("{n}", n) : t("insNothingYet");
          return;
        }
        /* idempotent: an async writer inside a MutationObserver render loop must not
     mutate unless something actually changed, or it re-triggers itself */
        var sig = list.join("|");
        if (box.getAttribute("data-sig") === sig) return;
        box.setAttribute("data-sig", sig);
        box.innerHTML = "";
        list.forEach(function (x) {
          var d = document.createElement("div");
          d.className = "insLine";
          d.style.cssText =
            "display:flex;gap:8px;font-size:13px;color:var(--text);line-height:1.55;margin-bottom:7px";
          var dot = document.createElement("span");
          dot.style.color = "var(--pressure)";
          dot.textContent = "·";
          var tx = document.createElement("span");
          tx.textContent = x;
          d.appendChild(dot);
          d.appendChild(tx);
          box.appendChild(d);
        });
      }

      /* =====================================================================
   LOCAL FIRST.

   Every brew was already being stored in localStorage by localPush, full row,
   up to 400 of them, with no sheet involved. Insights were locked behind
   WEBHOOK() anyway. That gate was a product decision, not a technical limit,
   and it meant a new user had to do a ten step Google Sheets setup BEFORE the
   app did anything interesting. That setup is what people are bouncing off.

   Now: log a brew, get insights. No Google, no Apps Script, no /exec URL.
   The sheet becomes an upgrade for durability and cross device sync, which is
   an honest pitch, instead of a tollgate in front of the value.
   ===================================================================== */
      function iLocalInv() {
        try {
          var v = JSON.parse(localStorage.getItem("localInv") || "[]");
          return Array.isArray(v) ? v : [];
        } catch (e) {
          return [];
        }
      }
      function iLocalInvPush(o) {
        try {
          var a = iLocalInv();
          a.push(o);
          if (a.length > 200) a = a.slice(-200);
          localStorage.setItem("localInv", JSON.stringify(a));
        } catch (e) {}
      }
      var INV_COLNAMES = [
        "coffee",
        "roaster",
        "roast",
        "process",
        "portion_g",
        "qty",
        "location",
        "status",
        "freeze_date",
        "roast_date",
        "bean_id",
        "bag_g",
        "price",
        "currency",
        "price_per_g",
        "varietal",
        "region",
      ];

      /* Build the same shape iBuild wants, straight from localStorage. */
      function iFromLocal() {
        var rows = [];
        try {
          rows = localRows();
        } catch (e) {}
        return {
          cols: COLNAMES,
          shots: rows.map(function (x) {
            return x.row;
          }),
          invCols: INV_COLNAMES,
          inv: iLocalInv().map(function (o) {
            return INV_COLNAMES.map(function (c) {
              return o[c] !== undefined ? o[c] : "";
            });
          }),
        };
      }
      /* Sheet if connected, local otherwise. The sheet is the better source once it
   exists: it survives a cleared browser and spans devices. */
      async function iLoad() {
        /* google first: it is the new default and the only one with no setup cost */
        if (gConnected()) {
          try {
            var shots = await gRead(SHOT_TAB),
              inv = await gRead(INV_TAB);
            if (shots.length) {
              iBuild({
                cols: shots[0],
                shots: shots.slice(1),
                invCols: inv.length ? inv[0] : INV_COLNAMES,
                inv: inv.slice(1),
              });
              return "google";
            }
          } catch (e) {
            /* fall through to local rather than showing nothing */
          }
        }
        iBuild(iFromLocal());
        return "local";
      }

      /* =====================================================================
   PERSISTENCE.

   The app never called navigator.storage.persist(), which means it never once
   asked the browser to keep the data. Browsers evict best-effort storage under
   pressure, and iOS Safari wipes script-writable storage after 7 days of not
   visiting a site AT ALL. That was survivable while a sheet was mandatory.
   Now that the app is useful with zero setup, most users' entire history will
   live in exactly that fragile place, so it has to be asked for and reported
   honestly.

   Key platform fact: on iOS the 7 day eviction does NOT apply to a PWA added to
   the home screen. Installing is not a nice-to-have there, it is the fix. No
   amount of persist() helps in a Safari tab; Safari does not grant it.
   ===================================================================== */
      var PERSIST_STATE = { asked: false, granted: null, quota: null, usage: null };

      async function requestPersistence() {
        if (!navigator.storage) return null;
        try {
          if (navigator.storage.persisted) {
            PERSIST_STATE.granted = await navigator.storage.persisted();
          }
          /* only ask once we actually have something worth keeping: browsers weigh
       engagement, and asking on a blank first load tends to get a no */
          if (!PERSIST_STATE.granted && navigator.storage.persist) {
            var rows = 0;
            try {
              rows = localRows().length;
            } catch (e) {}
            if (rows > 0) {
              PERSIST_STATE.asked = true;
              PERSIST_STATE.granted = await navigator.storage.persist();
            }
          }
          if (navigator.storage.estimate) {
            var e = await navigator.storage.estimate();
            PERSIST_STATE.quota = e.quota;
            PERSIST_STATE.usage = e.usage;
          }
        } catch (e) {}
        return PERSIST_STATE.granted;
      }
      function isIOS() {
        return (
          /iPad|iPhone|iPod/.test(navigator.userAgent) ||
          (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
        );
      }
      function isStandalone() {
        return (
          window.navigator.standalone === true ||
          (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches)
        );
      }
      /* The honest answer to "is my data safe", per platform. */
      function storageVerdict() {
        /* Was WEBHOOK() only. A Google connected user was told their brews were
     at risk while they were sitting in their own Drive. dataMode() covers
     all three backends. */
        var connected = false;
        try {
          connected = dataMode() !== "local";
        } catch (e) {}
        if (connected) return { level: "safe", key: "durSheet" };
        if (isIOS() && !isStandalone()) return { level: "risk", key: "durIOSTab" }; /* 7 day wipe */
        if (isStandalone()) return { level: "ok", key: "durInstalled" };
        if (PERSIST_STATE.granted === true) return { level: "ok", key: "durGranted" };
        return { level: "risk", key: "durBestEffort" };
      }

      /* The banner used to say one thing to everyone: connect a sheet. On an iPhone
   in a Safari tab that is not even the most urgent fix, because iOS wipes the
   storage after 7 days regardless of anything we do in JS. Installing to the
   home screen is what actually stops that. Say the true thing per platform. */
      /* This looked up #duraTitleEl and #duraBodyEl, which DO NOT EXIST. It returned
   on line 3 every single time, so the whole per-platform durability message was
   dead code that never reached a screen. The real elements are the [data-i18n=duraT]
   heading and the .durab body.

   We also strip their data-i18n attributes on takeover, otherwise the translator
   walks the DOM on every language switch and overwrites our per-platform text
   with the generic dictionary string. */
      function renderDurability() {
        var el = document.getElementById("duraBanner");
        if (!el) return;
        var t1 = el.querySelector('[data-i18n="duraT"], .durahd b');
        var t2 = el.querySelector('[data-i18n="duraB"], .durab');
        if (!t1 || !t2) return;
        var v = storageVerdict();
        var rows = 0;
        try {
          rows = Math.max(localRows().length, (IROWS || []).length);
        } catch (e) {}
        t1.removeAttribute("data-i18n");
        t2.removeAttribute("data-i18n");
        var title = t(v.key + "T"),
          body = t(v.key + "B").replace("{n}", rows);
        if (t1.textContent !== title) t1.textContent = title;
        if (t2.textContent !== body) t2.textContent = body;
        el.setAttribute("data-level", v.level);
        var bolt = el.querySelector(".durabolt");
        if (bolt) bolt.textContent = v.level === "safe" || v.level === "ok" ? "✓" : "!";
      }

      /* =====================================================================
   GOOGLE DATA LAYER  (drive.file)

   Validated: drive.file is a NON-SENSITIVE scope. No verification review, no
   unverified-app wall. The Sheets API accepts it for files this app created.
   So we create the user's sheet for them: three taps instead of fourteen steps,
   and no Apps Script anywhere in the path.

   What that deletes: LogSink.gs, CHECK_SETUP.gs, the template sheet, the /exec
   paste, the two-sheet identity problem, and the "users must re-paste the .gs"
   problem, which stops existing because there is no .gs.

   Known limitation, measured not assumed: a browser gets a ~3600s access token
   and NO refresh token. Renewal needs a user gesture. Every write here happens
   inside a click, so that is where we renew.
   ===================================================================== */
      /* Set by set-client-id.ps1 after creating the OAuth client for
   https://oscarbarajasmaker.github.io  (see GOOGLE_SETUP.md).
   Public by design: a client ID is not a secret, it is an identifier. The
   origin allowlist is what actually protects it. While empty, the Google
   option stays hidden and nothing changes for anyone. */
      var GOOGLE_CLIENT_ID =
        typeof window !== "undefined" && window.BREWPILOT_CLIENT_ID
          ? String(window.BREWPILOT_CLIENT_ID).trim()
          : "";
      var GSCOPE = "https://www.googleapis.com/auth/drive.file";
      var GTOKEN = null,
        GTOKEN_EXP = 0,
        GSHEET = null,
        GCLIENT = null,
        GNAME = "";
      var SHOT_TAB = "Shot Log",
        INV_TAB = "Inventory";

      function gConfigured() {
        return !!(typeof GOOGLE_CLIENT_ID !== "undefined" && GOOGLE_CLIENT_ID);
      }
      function gTokenOk() {
        return !!(GTOKEN && Date.now() < GTOKEN_EXP - 60000);
      }
      function gConnected() {
        return !!(GSHEET && gConfigured());
      }

      function gSaveToken() {
        try {
          if (GTOKEN && GTOKEN_EXP) {
            localStorage.setItem("gtok", GTOKEN);
            localStorage.setItem("gtokexp", String(GTOKEN_EXP));
          } else {
            localStorage.removeItem("gtok");
            localStorage.removeItem("gtokexp");
          }
        } catch (e) {}
      }
      function gInit() {
        try {
          GSHEET = localStorage.getItem("gsheet") || null;
        } catch (e) {}
        try {
          GNAME = localStorage.getItem("gsheetname") || "";
        } catch (e) {}
        /* restore the token so a reload inside the hour costs nothing at all */
        try {
          var t = localStorage.getItem("gtok"),
            e2 = parseInt(localStorage.getItem("gtokexp") || "0", 10);
          if (t && e2 && Date.now() < e2 - 60000) {
            GTOKEN = t;
            GTOKEN_EXP = e2;
          } else {
            localStorage.removeItem("gtok");
            localStorage.removeItem("gtokexp");
          }
        } catch (e) {}
      }
      function gForget() {
        try {
          localStorage.removeItem("gsheet");
          localStorage.removeItem("gsheetname");
        } catch (e) {}
        GSHEET = null;
        GTOKEN = null;
        GTOKEN_EXP = 0;
        GNAME = "";
        try {
          localStorage.removeItem("gtok");
          localStorage.removeItem("gtokexp");
        } catch (e) {}
      }

      /* interactive=true shows the account chooser. Otherwise we try silently, which
   works when consent already exists and the Google session is alive. */
      /* GRESOLVE is deliberate. The token client is created ONCE, so its callback
   closes over whichever resolve existed at creation time. Reusing the client on
   a later call would fire that stale resolve and leave the new promise pending
   forever: the first token renewal would hang, silently, an hour into a session.
   Keep the live resolver in a variable the callback reads at call time instead. */
      var GRESOLVE = null;
      function gAuth(interactive) {
        return new Promise(function (resolve) {
          if (!gConfigured()) return resolve(false);
          if (gTokenOk()) return resolve(true);
          if (!(window.google && google.accounts && google.accounts.oauth2)) return resolve(false);
          var done = false;
          GRESOLVE = function (v) {
            if (done) return;
            done = true;
            resolve(v);
          };
          /* never leave a caller awaiting forever if Google never calls back */
          setTimeout(function () {
            if (GRESOLVE) GRESOLVE(false);
          }, 60000);
          try {
            if (!GCLIENT) {
              GCLIENT = google.accounts.oauth2.initTokenClient({
                client_id: GOOGLE_CLIENT_ID,
                scope: GSCOPE,
                callback: function (r) {
                  if (r && r.access_token) {
                    GTOKEN = r.access_token;
                    GTOKEN_EXP = Date.now() + (r.expires_in || 3600) * 1000;
                    gSaveToken();
                    if (GRESOLVE) GRESOLVE(true);
                  } else if (GRESOLVE) GRESOLVE(false);
                  GRESOLVE = null;
                },
                error_callback: function () {
                  if (GRESOLVE) GRESOLVE(false);
                  GRESOLVE = null;
                },
              });
            }
            /* prompt:'' means "show UI only if you actually need to". Google then
         shows the account chooser and consent screen to a first time user, and
         NOTHING to a returning one whose consent already exists.

         prompt:'consent' forces the screen every time. Measured on a real
         account: it produced a pointless "BrewPilot already has some access ->
         Continue" tap on every token renewal, once an hour, forever. The only
         reason to force consent is to obtain a refresh token, and the browser
         token flow does not issue one, so there is no reason at all. */
            GCLIENT.requestAccessToken({ prompt: "" });
          } catch (e) {
            if (GRESOLVE) GRESOLVE(false);
            GRESOLVE = null;
          }
        });
      }

      async function gApi(url, opts) {
        opts = opts || {};
        if (!gTokenOk()) {
          var ok = await gAuth(false);
          if (!ok) throw new Error("needs-gesture");
        }
        opts.headers = Object.assign(
          { Authorization: "Bearer " + GTOKEN, "Content-Type": "application/json" },
          opts.headers || {},
        );
        var r = await fetch(url, opts);
        if (r.status === 401) {
          GTOKEN = null;
          GTOKEN_EXP = 0;
          gSaveToken();
          throw new Error("needs-gesture");
        }
        var txt = await r.text();
        var j = null;
        try {
          j = JSON.parse(txt);
        } catch (e) {}
        if (!r.ok) throw new Error((j && j.error && j.error.message) || "HTTP " + r.status);
        return j;
      }

      /* Born with both schemas, so there is no ensureHeader_ dance and no migration
   later. The client owns the schema now: it is in this file, which updates on
   publish, instead of in code the user pasted months ago. */
      async function gCreateSheet() {
        var ss = await gApi("https://sheets.googleapis.com/v4/spreadsheets", {
          method: "POST",
          body: JSON.stringify({
            properties: { title: "BrewPilot Log" },
            sheets: [{ properties: { title: SHOT_TAB } }, { properties: { title: INV_TAB } }],
          }),
        });
        GSHEET = ss.spreadsheetId;
        GNAME = ss.properties ? ss.properties.title : "BrewPilot Log";
        try {
          localStorage.setItem("gsheet", GSHEET);
          localStorage.setItem("gsheetname", GNAME);
        } catch (e) {}
        await gApi(
          "https://sheets.googleapis.com/v4/spreadsheets/" +
            GSHEET +
            "/values/" +
            encodeURIComponent(SHOT_TAB + "!A1") +
            ":append?valueInputOption=RAW",
          { method: "POST", body: JSON.stringify({ values: [COLNAMES] }) },
        );
        await gApi(
          "https://sheets.googleapis.com/v4/spreadsheets/" +
            GSHEET +
            "/values/" +
            encodeURIComponent(INV_TAB + "!A1") +
            ":append?valueInputOption=RAW",
          { method: "POST", body: JSON.stringify({ values: [INV_COLNAMES] }) },
        );
        return GSHEET;
      }

      async function gAppend(tab, values) {
        return gApi(
          "https://sheets.googleapis.com/v4/spreadsheets/" +
            GSHEET +
            "/values/" +
            encodeURIComponent(tab + "!A1") +
            ":append?valueInputOption=USER_ENTERED",
          { method: "POST", body: JSON.stringify({ values: [values] }) },
        );
      }
      async function gRead(tab) {
        var d = await gApi(
          "https://sheets.googleapis.com/v4/spreadsheets/" +
            GSHEET +
            "/values/" +
            encodeURIComponent(tab + "!A1:AC5000"),
        );
        return d && d.values ? d.values : [];
      }

      /* The whole connect flow: one tap. Must run from a click, because that is what
   Google requires for the token. */
      async function gRowCount(id) {
        /* count logged shots by the coffee column (C); col A/B are blank in every row */
        try {
          var d = await gApi(
            "https://sheets.googleapis.com/v4/spreadsheets/" +
              id +
              "/values/" +
              encodeURIComponent(SHOT_TAB + "!C2:C5000"),
          );
          var v = d && d.values ? d.values : [];
          var n = 0;
          for (var i = 0; i < v.length; i++) {
            if (v[i] && v[i][0] != null && String(v[i][0]).trim() !== "") n++;
          }
          return n;
        } catch (e) {
          return -1;
        }
      }
      async function gListLogs() {
        /* Drive files.list (the DRIVE API, separate from Sheets). THROWS on failure so
     the caller can tell "search failed" (e.g. Drive API not enabled) from "no logs",
     and never creates a duplicate on an error. 'contains' catches renamed copies. */
        var q =
          "name contains 'BrewPilot' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false";
        var d = await gApi(
          "https://www.googleapis.com/drive/v3/files?q=" +
            encodeURIComponent(q) +
            "&orderBy=modifiedTime%20desc&fields=files(id,name)&pageSize=30",
        );
        return d && d.files ? d.files : [];
      }
      async function gScoreLogs(files) {
        var withData = [];
        for (var i = 0; i < files.length; i++) {
          var rc = await gRowCount(files[i].id);
          if (rc > 0) withData.push({ id: files[i].id, rows: rc });
        }
        withData.sort(function (a, b) {
          return b.rows - a.rows;
        });
        return withData;
      }
      function gAdopt(id) {
        GSHEET = id;
        try {
          localStorage.setItem("gsheet", id);
        } catch (e) {}
      }
      async function gAutoLink() {
        /* true = handled (adopted / asked / steered). false = truly nothing, caller creates. */
        var files;
        try {
          files = await gListLogs();
        } catch (e) {
          alert(
            "Could not search your Drive for an existing log. Open Settings and paste your BrewPilot Log link under Reconnect to existing sheet. If this keeps happening, enable the Google Drive API for the app.",
          );
          return true;
        }
        if (!files.length) return false;
        var withData = await gScoreLogs(files);
        if (withData.length === 0) {
          gAdopt(files[0].id);
          return true;
        }
        if (withData.length === 1 || withData[0].rows >= withData[1].rows * 2) {
          gAdopt(withData[0].id);
          return true;
        }
        gPickSheet(withData);
        return true;
      }
      async function gTryUpgrade() {
        /* linked sheet is empty: adopt a populated log if one exists, else stay put */
        try {
          var files = await gListLogs();
          var withData = await gScoreLogs(files);
          if (!withData.length) return;
          if (withData.length === 1 || withData[0].rows >= withData[1].rows * 2) {
            gAdopt(withData[0].id);
          } else gPickSheet(withData);
        } catch (e) {}
      }
      function gPickSheet(cands) {
        var ov = document.createElement("div");
        ov.style.cssText =
          "position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:20px";
        var card = document.createElement("div");
        card.style.cssText =
          "background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;max-width:400px;width:100%;color:var(--text)";
        card.innerHTML =
          "<div style='font-weight:600;margin-bottom:4px'>Which log is yours?</div><div style='color:var(--dim);font-size:12px;margin-bottom:12px'>Found more than one BrewPilot Log. Pick the one with your history.</div>";
        cands.forEach(function (c) {
          var bt = document.createElement("button");
          bt.textContent = c.rows + " logged " + (c.rows === 1 ? "row" : "rows");
          bt.style.cssText =
            "width:100%;margin-bottom:8px;padding:12px;border-radius:10px;border:1px solid var(--sel-line);background:var(--sel-bg);color:var(--sel-text);font-weight:600;cursor:pointer";
          bt.onclick = function () {
            gAdopt(c.id);
            if (ov.parentNode) ov.parentNode.removeChild(ov);
            try {
              renderSheetStatus();
            } catch (e) {}
            try {
              uiRender();
            } catch (e) {}
          };
          card.appendChild(bt);
        });
        var fresh = document.createElement("button");
        fresh.textContent = "None of these - start a new log";
        fresh.style.cssText =
          "width:100%;padding:10px;border-radius:10px;border:1px solid var(--line);background:var(--panel);color:var(--dim);font-size:13px;cursor:pointer";
        fresh.onclick = async function () {
          if (ov.parentNode) ov.parentNode.removeChild(ov);
          await gCreateSheet();
          try {
            renderSheetStatus();
          } catch (e) {}
          try {
            uiRender();
          } catch (e) {}
        };
        card.appendChild(fresh);
        ov.appendChild(card);
        document.body.appendChild(ov);
      }
      async function gRelinkSheet() {
        var el = document.getElementById("relinkSheet");
        if (!el) return;
        var v = el.value.trim();
        if (!v) {
          alert("Paste your BrewPilot Log link or ID");
          return;
        }
        var mm = v.match(/[-\w]{25,}/);
        var id = mm ? mm[0] : v;
        var ok = await gAuth(true);
        if (!ok) {
          alert(t("gAuthFailed"));
          return;
        }
        var prev = GSHEET;
        GSHEET = id;
        try {
          await gRead(SHOT_TAB);
          try {
            localStorage.setItem("gsheet", id);
          } catch (e) {}
          el.value = "";
          try {
            renderSheetStatus();
          } catch (e) {}
          try {
            uiRender();
          } catch (e) {}
          alert("Reconnected to your existing log");
        } catch (e) {
          GSHEET = prev;
          alert(
            "Could not open that sheet. It must be a BrewPilot Log this app created, signed into the same Google account.",
          );
        }
      }
      function gIsMissing(e) {
        var m = String((e && e.message) || "");
        return m.indexOf("HTTP 404") >= 0 || /not ?found/i.test(m);
      }
      async function gConnect() {
        if (!gConfigured()) {
          alert(t("gNotSetUp"));
          return false;
        }
        var ok = await gAuth(true);
        if (!ok) {
          alert(t("gAuthFailed"));
          return false;
        }
        try {
          if (!GSHEET) {
            if (!(await gAutoLink())) {
              await gCreateSheet();
            }
          } else {
            try {
              await gRead(SHOT_TAB);
              var _rc = await gRowCount(GSHEET);
              if (_rc === 0) {
                await gTryUpgrade();
              }
            } catch (e) {
              if (String((e && e.message) || "").indexOf("needs-gesture") >= 0) throw e;
              if (gIsMissing(e)) {
                if (!(await gAutoLink())) {
                  gForget();
                  await gCreateSheet();
                }
              }
              /* any other error (network / 401 / 403 / 429 / 5xx): keep GSHEET, never recreate */
            }
          }
        } catch (e) {
          if (String((e && e.message) || "").indexOf("needs-gesture") >= 0) return false;
        }
        try {
          uiRender();
        } catch (e) {}
        try {
          renderClientInsights();
        } catch (e) {}
        return true;
      }

      function gSheetUrl() {
        return GSHEET ? "https://docs.google.com/spreadsheets/d/" + GSHEET + "/edit" : "";
      }

      /* ---- one data layer over three backends -------------------------------- */
      function dataMode() {
        /* /exec amputated 2026-07-17. Two modes now: the sheet the app made, or local.
     The exec branch is not deprecated, it is gone: LogSink.gs and friends are
     deleted. Anyone who had a webhook reconnects through the Google card. */
        if (gConnected()) return "google";
        return "local";
      }

      /* The connect card. Replaces fourteen steps and a red warning screen with one
   tap. Only rendered once a client ID is baked in, so a build without one is
   simply the old app. */
      function renderGoogleCard() {
        var host = document.getElementById("setPanel");
        if (!host) return;
        var old = document.getElementById("gCard");
        if (old) old.remove();
        if (!gConfigured()) return;
        var box = document.createElement("div");
        box.id = "gCard";
        box.style.cssText =
          "border:1px solid var(--line);border-radius:10px;padding:12px;margin:10px 0";
        var connected = gConnected();
        var h = document.createElement("div");
        h.style.cssText =
          "font-weight:600;margin-bottom:4px;color:" + (connected ? "var(--ready)" : "var(--text)");
        h.textContent = t(connected ? "gConnected" : "gConnect");
        var p = document.createElement("div");
        p.style.cssText = "font-size:12.5px;color:var(--dim);line-height:1.5;margin-bottom:9px";
        p.textContent = t(connected ? "gConnectedSub" : "gConnectSub");
        box.appendChild(h);
        box.appendChild(p);
        if (connected) {
          var a = document.createElement("a");
          a.href = gSheetUrl();
          a.target = "_blank";
          a.rel = "noopener";
          a.style.cssText =
            "display:inline-block;color:var(--sel-text);border:1px solid var(--sel-line);background:var(--sel-bg);border-radius:8px;padding:7px 11px;font-size:12.5px;text-decoration:none;margin-right:8px";
          a.textContent = t("gOpenSheet");
          var d = document.createElement("button");
          d.style.cssText =
            "background:transparent;border:1px solid var(--line);color:var(--dim);" +
            "border-radius:8px;padding:7px 11px;font-size:12.5px;cursor:pointer";
          d.textContent = t("gDisconnect");
          d.onclick = function () {
            gForget();
            renderGoogleCard();
            try {
              uiRender();
            } catch (e) {}
          };
          box.appendChild(a);
          box.appendChild(d);
        } else {
          var b = document.createElement("button");
          b.className = "grn";
          b.style.cssText = "width:100%";
          b.textContent = t("gConnect");
          /* must be a real click: Google will not issue a token without a gesture */
          b.onclick = async function () {
            b.disabled = true;
            b.textContent = "...";
            try {
              await gConnect();
            } finally {
              b.disabled = false;
              renderGoogleCard();
            }
          };
          box.appendChild(b);
        }
        host.insertBefore(box, host.firstChild);
      }

      /* The CTA copy was written for a world where connecting meant copying a
   template and deploying a script. When Google sign-in is live that is a lie:
   it is one tap. Rewrite the visible strings rather than leave the old promise
   on screen. */
      function retitleCtas() {
        if (!gConfigured()) return;
        var wel = document.getElementById("welcome");
        if (wel && !gConnected()) {
          var h = wel.querySelector("div");
          if (h) h.textContent = t("welTitleG");
          var subs = wel.querySelectorAll("div");
          if (subs[1]) subs[1].textContent = t("welBodyG");
          var b = wel.querySelector("button");
          if (b) b.textContent = t("gConnect");
          var foot = wel.querySelector("div:last-child");
          if (foot && /explore|explorar/i.test(foot.textContent || ""))
            foot.textContent = t("welFootG");
        }
        /* The banner button is .durabtn with data-i18n='duraGo'. There is no
     #duraGoBtn: an earlier version of this looked one up, got null, and did
     nothing at all. It also opens the wizard, which IS the old fourteen step
     path, so its handler has to be replaced, not just its label. */
        document.querySelectorAll(".durabtn").forEach(function (btn) {
          if (!/duraGo/.test(btn.getAttribute("data-i18n") || "")) return;
          if (gConnected()) {
            btn.style.display = "none";
            return;
          }
          btn.style.display = "";
          btn.textContent = t("gConnect");
          btn.onclick = function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            goConnectSheet();
          };
          btn.setAttribute("onclick", "");
        });
        /* the lock card on Insights */
        /* The lock only shows when there is NO data. The useful action is therefore
     to log a brew, not to connect anything: insights run on local rows. */
        var lock = document.getElementById("insLock");
        if (lock) {
          var lb = lock.querySelector("button");
          if (lb) {
            lb.textContent = t("insLockGo");
            lb.onclick = function (ev) {
              ev.preventDefault();
              showTab("log");
            };
            lb.setAttribute("onclick", "");
          }
        }
        /* the template copy link belongs to the old world entirely */
        document.querySelectorAll("a").forEach(function (a) {
          if (a.href && a.href.indexOf("/copy") > 0) {
            var row = a.closest("div");
            if (row) row.style.display = "none";
            else a.style.display = "none";
          }
        });
      }

      /* =====================================================================
   INVENTORY ON DRIVE

   Ported from LogSink.gs invFreeze_ / invList_. Same schema, same rules, same
   portion parsing. It runs in the browser now, against the user's own sheet,
   because the .gs only existed to be the thing holding the sheet open.
   ===================================================================== */
      function gPortionG(p) {
        var s = String(p || "").toLowerCase();
        if (s.indexOf("whole") >= 0 || s.indexOf("bolsa") >= 0) return parseFloat(INVBAG) || 250;
        var n = parseFloat(s.replace(/[^0-9.]/g, ""));
        return isFinite(n) && n > 0 ? n : 40;
      }
      /* Same order as INV_COLNAMES. Position matters: the sheet is written by index. */
      function gInvRow(o) {
        try {
          if (window.REST_MODE) {
            o.__rest = true;
            window.__RESTED = true;
            window.REST_MODE = false;
          } else {
            window.__RESTED = false;
          }
        } catch (e) {}
        var ppg = (function () {
          var p = parseFloat(o.price),
            b = parseFloat(o.bag_g);
          return p && b && b > 0 ? Math.round((p / b) * 10000) / 10000 : "";
        })();
        var map = {
          coffee: o.coffee,
          roaster: o.roaster || "",
          roast: o.roast || "",
          process: o.process || "",
          portion_g: gPortionG(o.portion),
          qty: parseInt(o.qty || "1", 10),
          location: o.__rest ? "Counter" : "Freezer",
          status: o.__rest ? "Resting" : "Sealed",
          freeze_date: gFreezeStr(o.freeze_date),
          roast_date: o.roast_date || "",
          bean_id: String(o.coffee || "")
            .toLowerCase()
            .replace(/\s+/g, "-"),
          bag_g: o.bag_g || "",
          price: o.price || "",
          currency: o.currency || "USD",
          price_per_g: ppg,
          varietal: o.varietal || "",
          region: o.region || "",
        };
        return INV_COLNAMES.map(function (c) {
          return map[c] !== undefined ? map[c] : "";
        });
      }
      /* Ported from freezeStr_: blank means now, a past date gets 00:00, today keeps
   the clock time, a full stamp passes through. The freshness maths depends on
   this being honest, so it is worth the ten lines. */
      function gFreezeStr(fd) {
        var pad = function (n) {
          return (n < 10 ? "0" : "") + n;
        };
        var now = new Date();
        var stamp = function (d, withTime) {
          return (
            d.getFullYear() +
            "-" +
            pad(d.getMonth() + 1) +
            "-" +
            pad(d.getDate()) +
            " " +
            (withTime ? pad(d.getHours()) + ":" + pad(d.getMinutes()) : "00:00")
          );
        };
        var s = String(fd || "").trim();
        if (!s) return stamp(now, true);
        if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
          var today = stamp(now, false).slice(0, 10);
          return s === today ? stamp(now, true) : s + " 00:00";
        }
        return s;
      }
      async function gFreeze(o) {
        return gAppend(INV_TAB, gInvRow(o));
      }
      async function quickScore(coffee, rating, roast, process, roaster) {
        /* lightweight per-bag score for people who do not log every brew. A minimal
     shot-log row (type=score) so it feeds cost/value insights but is skipped by
     grind/time/water analysis and by the grind learner. 28 cols, aligned. */
        var cols = [
          "",
          "",
          coffee,
          roaster || "",
          "",
          process || "",
          roast || "",
          "score",
          "",
          "",
          "",
          "",
          "",
          "",
          "",
          String(rating || ""),
          "",
          "",
          "",
          "",
          "",
          "",
          "",
          "",
          "",
          "",
          "",
          "",
        ];
        try {
          localPush(cols);
        } catch (e) {}
        if (dataMode() === "google") {
          try {
            await gAppend(SHOT_TAB, cols);
          } catch (e) {
            if (String(e.message).indexOf("needs-gesture") >= 0) {
              var _ok = await gAuth(true);
              if (_ok) {
                try {
                  await gAppend(SHOT_TAB, cols);
                } catch (e2) {}
              }
            }
          }
        }
      }
      function quickScoreOpen() {
        var coffee = ((document.getElementById("invcoffee") || {}).value || "").trim();
        if (!coffee) {
          alert(t("scoreNeedCoffee"));
          return;
        }
        var roaster = ((document.getElementById("invroaster") || {}).value || "").trim();
        var process = ((document.getElementById("invprocess") || {}).value || "").trim();
        var roast = ((document.getElementById("invroast") || {}).value || "").trim();
        var ov = document.createElement("div");
        ov.style.cssText =
          "position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:20px";
        var card = document.createElement("div");
        card.style.cssText =
          "background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;max-width:400px;width:100%;color:var(--text)";
        card.innerHTML =
          "<div style='font-weight:600;margin-bottom:2px'>" +
          t("scoreBag") +
          "</div><div style='color:var(--dim);font-size:12px;margin-bottom:12px'>" +
          coffee +
          " · " +
          t("scoreTap") +
          "</div>";
        var grid = document.createElement("div");
        grid.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px";
        for (var i = 1; i <= 10; i++) {
          (function (n) {
            var bt = document.createElement("button");
            bt.textContent = n;
            bt.style.cssText =
              "flex:1 1 40px;padding:12px 0;border-radius:10px;border:1px solid var(--sel-line);background:var(--sel-bg);color:var(--sel-text);font-weight:600;cursor:pointer";
            bt.onclick = async function () {
              if (ov.parentNode) ov.parentNode.removeChild(ov);
              await quickScore(coffee, n, roast, process, roaster);
              try {
                loadInventory();
              } catch (e) {}
              alert(t("scoreDone").replace("{c}", coffee).replace("{n}", n));
            };
            grid.appendChild(bt);
          })(i);
        }
        card.appendChild(grid);
        var cx = document.createElement("button");
        cx.textContent = t("scoreCancel");
        cx.style.cssText =
          "width:100%;padding:10px;border-radius:10px;border:1px solid var(--line);background:var(--panel);color:var(--dim);font-size:13px;cursor:pointer";
        cx.onclick = function () {
          if (ov.parentNode) ov.parentNode.removeChild(ov);
        };
        card.appendChild(cx);
        ov.appendChild(card);
        document.body.appendChild(ov);
      }
      /* Ported from invList_: group by bean, skip Finished, sum quantities. */
      async function gInvList() {
        var rows = await gRead(INV_TAB);
        if (rows.length < 2) return { ok: true, beans: [] };
        var head = rows[0],
          idx = {};
        head.forEach(function (h, i) {
          idx[String(h)] = i;
        });
        var by = {};
        for (var r = 1; r < rows.length; r++) {
          var row = rows[r];
          var name = row[idx["coffee"]];
          if (!name) continue;
          if (String(row[idx["status"]] || "") === "Finished") continue;
          var key = String(name).toLowerCase();
          if (!by[key])
            by[key] = {
              __row: r + 1,
              coffee: name,
              roaster: row[idx["roaster"]] || "",
              varietal: row[idx["varietal"]] || "",
              region: row[idx["region"]] || "",
              roast: row[idx["roast"]] || "",
              process: row[idx["process"]] || "",
              resting: String(row[idx["status"]] || "") === "Resting",
              inuse: String(row[idx["status"]] || "") === "Open",
              portions: [],
              total: 0,
            };
          var q = parseInt(row[idx["qty"]] || "0", 10) || 0;
          if (q <= 0) continue;
          by[key].portions.push({
            portion_g: row[idx["portion_g"]],
            qty: q,
            freeze_date: row[idx["freeze_date"]] || "",
            roast_date: row[idx["roast_date"]] || "",
          });
          by[key].total += q;
        }
        /* Decorate to the shape loadInventory ACTUALLY renders. It reads b.summary,
     b.total_g, b.age and b.frozen_portion, and gates the whole Thaw button on
     b.frozen_portion being truthy. gInvList returned none of them, so a Drive
     user's inventory card showed a name, a roaster, and a dead Finished button.
     The exec JSON had these fields; the google port never did. Measured, not
     assumed: the Thaw button was never rendered for a google user at all. */
        var beans = Object.keys(by).map(function (k) {
          return by[k];
        });
        beans.forEach(function (b) {
          b.total_g = b.portions.reduce(function (a, p) {
            return a + gPortionG(p.portion_g) * p.qty;
          }, 0);
          if (b.total_g) b.total_g = Math.round(b.total_g);
          b.summary = b.portions
            .map(function (p) {
              return p.qty + " x " + p.portion_g;
            })
            .join(", ");
          b.frozen_portion = b.portions.length ? b.portions[0].portion_g : "";
          b.age = (function () {
            var best = null;
            b.portions.forEach(function (p) {
              var d = dParse(p.roast_date);
              if (isFinite(d) && (best === null || d > best)) best = d;
            });
            if (best === null) return "";
            var days = Math.floor((Date.now() - best) / 86400000);
            return days >= 0 && days < 3650 ? days + "d" : "";
          })();
        });
        return { ok: true, beans: beans };
      }

      /* Update an EXISTING row. The Drive layer was append-and-read only: gAppend
   appends, gRead reads, and nothing could modify a row. That is why invAction
   (Thaw / Finished) was never ported and silently did nothing for every Drive
   user. drive.file permits values.update on a sheet this app created. */
      async function gUpdate(tab, row1, values) {
        return gApi(
          "https://sheets.googleapis.com/v4/spreadsheets/" +
            GSHEET +
            "/values/" +
            encodeURIComponent(tab + "!A" + row1) +
            "?valueInputOption=USER_ENTERED",
          { method: "PUT", body: JSON.stringify({ values: [values] }) },
        );
      }

      /* Thaw / Finished against Drive.
   Semantics are defined HERE now, on purpose. LogSink.gs owned them before and
   is being deleted, so the sheet is the app's own format and the only contract
   that matters is that the writer agrees with the readers. It does:
     thaw     -> qty minus one on the matching portion row. Both gInvList and
                 rotSuggest skip qty<=0, so a drained row disappears by itself.
                 location stays Freezer, because the REMAINING portions are.
     finished -> status Finished on every row for that coffee. Both readers
                 skip Finished.
   Returns true only if a row actually changed, so the caller can tell the user
   the truth instead of assuming. */
      async function gInvAction(action, coffee, portion) {
        var rows = await gRead(INV_TAB);
        if (rows.length < 2) return false;
        var head = rows[0],
          idx = {};
        head.forEach(function (h, i) {
          idx[String(h)] = i;
        });
        var hit = false;
        for (var r = 1; r < rows.length; r++) {
          var row = rows[r];
          if (String(row[idx["coffee"]] || "").toLowerCase() !== String(coffee || "").toLowerCase())
            continue;
          if (String(row[idx["status"]] || "") === "Finished") continue;
          if (action === "finished") {
            row[idx["status"]] = "Finished";
            await gUpdate(INV_TAB, r + 1, row);
            hit = true;
          } else if (action === "thaw") {
            if (String(row[idx["portion_g"]] || "") !== String(portion || "")) continue;
            var q = parseInt(row[idx["qty"]] || "0", 10) || 0;
            if (q <= 0) continue;
            row[idx["qty"]] = q - 1;
            await gUpdate(INV_TAB, r + 1, row);
            hit = true;
            break;
          }
        }
        return hit;
      }

      /* Build stamp. Same job as FW_VERSION in the firmware: answer "which build is
   actually live" without guessing. Generated at build time, printed by
   update.ps1 before publishing, and shown at the bottom of Settings. */
      var BUILD = "__BUILD_STAMP__";
      function renderBuild() {
        var host = document.getElementById("setPanel");
        if (!host) return;
        var old = document.getElementById("buildStamp");
        if (old) old.remove();
        var d = document.createElement("div");
        d.id = "buildStamp";
        d.style.cssText =
          "margin-top:14px;text-align:center;font:11px ui-monospace,monospace;" +
          "color:var(--dim);opacity:.75;user-select:all";
        d.textContent = "build " + BUILD;
        d.title = "Compare this with what update.ps1 printed when you published.";
        host.appendChild(d);
      }

      /* Android fires beforeinstallprompt and we can install in one tap. iOS never
   fires it and forbids programmatic install, so it gets the manual steps. The
   card previously showed the same vague pitch to both. */
      var DEFERRED_PROMPT = null;
      window.addEventListener("beforeinstallprompt", function (e) {
        e.preventDefault();
        DEFERRED_PROMPT = e;
        try {
          renderInstallCard();
        } catch (err) {}
      });
      function renderInstallCard() {
        var card = document.getElementById("instCard");
        if (!card) return;
        /* already installed: nothing to sell */
        if (isStandalone()) {
          card.style.display = "none";
          return;
        }
        var dismissed = false;
        try {
          dismissed = localStorage.getItem("instDismiss") === "1";
        } catch (e) {}
        var rows = 0;
        try {
          rows = localRows().length;
        } catch (e) {}
        /* Once there is data, or Google is connected, this stops being optional:
     both are the things a Safari tab will take away. */
        var stakes = rows > 0 || gConnected();
        if (dismissed && !stakes) {
          card.style.display = "none";
          return;
        }
        card.style.display = "";
        var sub = document.getElementById("instSub");
        if (sub) sub.textContent = isIOS() ? t("instB") : t("instBA");
        var steps = document.getElementById("instIos");
        var btn = document.getElementById("instBtn");
        if (steps) steps.style.display = isIOS() ? "" : "none";
        if (btn) {
          btn.style.display = !isIOS() && DEFERRED_PROMPT ? "" : "none";
          btn.onclick = async function () {
            if (!DEFERRED_PROMPT) return;
            DEFERRED_PROMPT.prompt();
            try {
              await DEFERRED_PROMPT.userChoice;
            } catch (e) {}
            DEFERRED_PROMPT = null;
            renderInstallCard();
          };
        }
      }

      /* =====================================================================
   ROTATION ADVISOR (ported from RotationAdvisor.gs)

   Same model, same weights, same maths. It lived in Apps Script only because
   that is where the sheet was. It runs here now, on rows we already have.

   The mode was a Script Property, which is precisely why this needed a server
   at all. It is a preference, so it lives in localStorage.
   ===================================================================== */
      var REST_MIN_DAYS = 7;
      function rotWeights() {
        var mode = "balanced";
        try {
          mode = localStorage.getItem("rotmode") || "balanced";
        } catch (e) {}
        switch (mode) {
          case "fifo":
            return { fifo: 100, variety: 10, fresh: 5, rest: 5 };
          case "variety":
            return { fifo: 20, variety: 80, fresh: 15, rest: 10 };
          case "freshness":
            return { fifo: 15, variety: 15, fresh: 60, rest: 40 };
          default:
            return { fifo: 40, variety: 30, fresh: 30, rest: 25 };
        }
      }
      function rotProfileKey(b) {
        return String(b.varietal || "").toLowerCase() + "|" + String(b.process || "").toLowerCase();
      }
      function rotDaysSince(d) {
        if (!d) return null;
        var t = Date.parse(d);
        if (isNaN(t)) return null;
        return Math.floor((Date.now() - t) / 86400000);
      }
      function rotIsNum(v) {
        return typeof v === "number" && isFinite(v);
      }

      /* Faithful port of scoreBag_. Every branch matches the .gs. */
      function rotScoreBag(b, liveProfiles, allFrozen) {
        var W = rotWeights(),
          score = 0;
        /* 1. FIFO: longest frozen wins, normalised against the oldest in the stash */
        var fd = rotDaysSince(b.freeze_date);
        var maxFd =
          Math.max.apply(
            null,
            allFrozen.map(function (x) {
              return rotDaysSince(x.freeze_date) || 0;
            }),
          ) || 1;
        score += W.fifo * ((fd || 0) / maxFd);
        /* 2. variety: bonus when this profile is not already open */
        var mine = rotProfileKey(b);
        var clash = liveProfiles.filter(function (k) {
          return k === mine;
        }).length;
        score += clash === 0 ? W.variety : clash === 1 ? W.variety * 0.25 : 0;
        /* 3. roast freshness: decays over about four months */
        var rd = rotDaysSince(b.roast_date);
        if (rotIsNum(rd)) score += W.fresh * Math.max(0, 1 - rd / 120);
        /* 4. rest window: penalise a bag that has not rested since roast */
        if (rotIsNum(rd) && rd < REST_MIN_DAYS) score -= W.rest * 0.4;
        return score;
      }
      /* Ported from suggestRotation: read the freezer, score, return the winner. */
      async function rotSuggest() {
        var rows = [];
        if (gConnected()) {
          try {
            rows = await gRead(INV_TAB);
          } catch (e) {}
        }
        if (rows.length < 2) {
          var li = iLocalInv();
          if (!li.length) return null;
          rows = [INV_COLNAMES].concat(
            li.map(function (o) {
              return INV_COLNAMES.map(function (c) {
                return o[c] !== undefined ? o[c] : "";
              });
            }),
          );
        }
        var head = rows[0],
          idx = {};
        head.forEach(function (h, i) {
          idx[String(h)] = i;
        });
        var frozen = [];
        for (var r = 1; r < rows.length; r++) {
          var row = rows[r];
          if (String(row[idx["location"]]) !== "Freezer") continue;
          if (String(row[idx["status"]] || "") === "Finished") continue;
          if ((parseInt(row[idx["qty"]] || "0", 10) || 0) <= 0) continue;
          frozen.push({
            coffee: row[idx["coffee"]],
            roaster: row[idx["roaster"]] || "",
            varietal: "",
            process: row[idx["process"]] || "",
            freeze_date: row[idx["freeze_date"]] || "",
            roast_date: row[idx["roast_date"]] || "",
            portion_g: row[idx["portion_g"]],
            qty: row[idx["qty"]],
          });
        }
        if (!frozen.length) return null;
        /* what is already open, so variety can avoid a clash */
        var live = [];
        try {
          live = (ROT || []).map(rotProfileKey);
        } catch (e) {}
        var scored = frozen.map(function (b) {
          return { bag: b, score: rotScoreBag(b, live, frozen) };
        });
        scored.sort(function (a, b) {
          return b.score - a.score;
        });
        return {
          pick: scored[0].bag,
          score: Math.round(scored[0].score),
          runners: scored.slice(1, 3).map(function (x) {
            return x.bag.coffee;
          }),
        };
      }

      /* ============================================================
   PLAN vs LOG

   Oscar's point, from trying to log his first soup: the app never asked whether
   the brew has happened yet. It matters. Before, you want a grind starting
   point and no rating box. After, you want to record what happened and rate it.
   The same form was doing both badly.

   startBrew/finishBrew already existed; nothing ever surfaced the choice.
   ============================================================ */
      var LOGMODE = "after"; /* 'before' = about to brew, 'after' = already brewed */
      function setLogMode(m) {
        LOGMODE = m === "before" ? "before" : "after";
        try {
          localStorage.setItem("logmode", LOGMODE);
        } catch (e) {}
        renderLogMode();
      }
      /* hide a field and whatever labels it: its .fcell if it has one, otherwise the
   element plus the label immediately before it */
      function hideField(id, hide) {
        var el = document.getElementById(id);
        if (!el) return;
        var cell = el.closest ? el.closest(".fcell") : null;
        if (cell) {
          cell.style.display = hide ? "none" : "";
          return;
        }
        el.style.display = hide ? "none" : "";
        var lab = el.previousElementSibling;
        if (lab && (lab.tagName === "LABEL" || (lab.className || "").indexOf("fl") >= 0)) {
          lab.style.display = hide ? "none" : "";
        }
      }
      function renderLogMode() {
        var wrap = document.getElementById("logModeRow");
        if (!wrap) return;
        Array.prototype.forEach.call(wrap.querySelectorAll("button"), function (b) {
          var on = b.getAttribute("data-mode") === LOGMODE;
          b.className = on ? "on" : "off";
        });
        /* rating is meaningless for a brew that has not happened */
        /* The chips and their label ARE the rate block; there is no wrapper element.
     Restore the ancestor row too: the rating shares a row with the outcome
     fields below, so hiding that row hid the chips, and showing the chips alone
     could not undo it. */
        ["rateChips", "rateWord"].forEach(function (id) {
          var el = document.getElementById(id);
          if (!el) return;
          el.style.display = LOGMODE === "before" ? "none" : "";
          if (LOGMODE !== "before") {
            var row = el.closest(".frow");
            if (row) row.style.display = "";
          }
        });
        /* The outcome fields are guesses until the brew has happened.
     This used to hide ['fyield','fdur']. NEITHER ID EXISTS - the filter form has
     ftime/frating, the gaggia form has gyield/gtime/r. getElementById returned
     null both times and the function returned early, so "hide the outcome fields
     while planning" has never done anything for anyone. audit.py could not catch
     it because the ids are in an array variable, not a literal. */
        var planning = LOGMODE === "before";
        ["gyield", "gtime", "r", "ftime"].forEach(function (id) {
          hideField(id, planning);
        });
        var plan = document.getElementById("planBox");
        if (plan) plan.style.display = LOGMODE === "before" ? "" : "none";
        /* Both forms have a green button. querySelector returned only the FIRST, so
     the filter form's button never followed the mode toggle at all. */
        Array.prototype.forEach.call(
          document.querySelectorAll("#tab-log button.grn"),
          function (btn) {
            btn.textContent = t(LOGMODE === "before" ? "logStartBtn" : "logSaveBtn2");
          },
        );
        try {
          renderLogMethod();
          renderLogForm();
        } catch (e) {}
        try {
          renderLogPlan();
        } catch (e) {}
      }

      /* ============================================================
   RATING CHIPS
   It was <input type="number" min=1 max=10>. On a phone that is a keyboard, a
   guess about what the numbers mean, and no sense of where 7 sits. Chips are
   one tap and show the whole scale at once.
   ============================================================ */
      function renderRateChips() {
        var host = document.getElementById("rateChips");
        if (!host) return;
        if (host.childNodes.length) return; /* build once */
        var input = document.getElementById("r");
        for (var i = 1; i <= 10; i++) {
          (function (n) {
            var b = document.createElement("button");
            b.type = "button";
            b.className = "off ratechip";
            b.textContent = String(n);
            b.setAttribute("data-rate", String(n));
            b.onclick = function () {
              if (input) input.value = String(n);
              try {
                localStorage.setItem("lastRate", String(n));
              } catch (e) {}
              syncRateChips();
            };
            host.appendChild(b);
          })(i);
        }
        syncRateChips();
      }
      function syncRateChips() {
        var input = document.getElementById("r");
        var v = input ? parseInt(input.value || "0", 10) : 0;
        Array.prototype.forEach.call(document.querySelectorAll(".ratechip"), function (b) {
          var n = parseInt(b.getAttribute("data-rate"), 10);
          b.className = v && n <= v ? "on ratechip" : "off ratechip";
        });
        var lab = document.getElementById("rateWord");
        if (lab) lab.textContent = v ? t("rate" + v) || "" : t("rateNone");
      }

      /* ============================================================
   THE LOG TAB MUST KNOW WHAT YOU BREW

   Oscar picked soup, opened Log, and the only way to record anything was a
   collapsed link reading "+ Log a filter / non-Gaggia brew". Soup IS a Gaggia
   method. So the one form that could take his shot was hidden behind a label
   saying it was for something else, and he used it anyway because there was
   nothing else there.

   There is exactly one form. So stop hiding it, and stop calling it the filter
   form when the user does espresso or soup.
   ============================================================ */
      function methodWord() {
        /* method-aware vocabulary: a shot if any machine method is on, else a brew */
        var machine = false;
        try {
          machine = !!(M_ESP || M_SOUP);
        } catch (e) {}
        return machine ? t("wShot") : t("wBrew");
      }
      function renderLogEntry() {}

      /* The cold start advisor only knew filter brewers, so a soup user got nothing.
   Targets and their provenance are in GRIND_RESEARCH.md. Short version:
     espresso 340um  measured median, dialled-in classical shot, 24 grinders
     soup     500um  DERIVED between that and the 600um ceiling cited for
                     experimental shots. No measured median exists for turbo.
   Oscar runs under 2 bar, below published turbo, so his own soup is plausibly
   coarser still. This is a starting point, not a target. */
      function logBrewerFor() {
        /* This predates the method picker and guessed: FBREWER, else soup, else
     espresso - ignoring the method you actually selected. With method=filter and
     no brewer chosen it returned 'Soup', so the plan banner offered a SOUP
     starting point on a filter brew while csInline said something else. Two
     resolvers, one question, different answers.
     csBrewer() is the one that reads the method. Delegate. */
        try {
          return csBrewer();
        } catch (e) {}
        return null;
      }
      function renderLogPlan() {
        var box = document.getElementById("planBox");
        if (!box) return;
        if (LOGMODE !== "before") {
          box.innerHTML = "";
          return;
        }
        var gid = null;
        try {
          gid = lastGrinder() || ownedGrinders()[0];
        } catch (e) {}
        var brewer = logBrewerFor();
        if (!gid || !brewer) {
          box.innerHTML = "<div class='csS'>" + t("csPick") + "</div>";
          return;
        }
        var c = csFor(brewer, gid);
        var g = typeof GRINDERS === "object" ? GRINDERS[gid] : null;
        box.innerHTML =
          "<div class='cs'><div class='csHd'>" +
          t("csT") +
          " &middot; " +
          brewer +
          (g ? " &middot; " + g.n : "") +
          "</div>" +
          "<div class='csV'>" +
          c.txt +
          "</div>" +
          /* The hedge is only true of CONICAL grinders. On a flat burr the published
       microns-per-click IS the gap, so telling a Lagom P80 or Mignon owner their
       click count is approximate is itself inaccurate - and it teaches people to
       ignore the warning where it matters. Show it where it is true. */
          "<div class='csS'>" +
          t("csHint") +
          (g && g.burr === "conical" ? " " + t("csConical") : "") +
          "</div></div>";
      }
      var _rh2 = renderHero;
      renderHero = function () {
        try {
          _rh2();
        } catch (e) {}
        try {
          homeRender();
        } catch (e) {}
      };

      /* bootstrap last: every definition exists by now */
      /* wizTemplateLink() and wizShots() removed with the Apps Script wizard: one was an
   empty stub left over from the /exec cut, the other lazy-loaded screenshots of a
   flow that no longer exists. Bootstrap is the worst place to leave a dead call. */
      uiStart();
      try {
        pickerizeAll();
      } catch (e) {}
    '''
TAIL = r'''</script>
  </body>
</html>
'''

# ---------- split the source markup into the five tab panels ----------
A_LOG    = '<label id="logLabel">'
A_BEANS  = '<div\n          onclick="toggleInv()"'
A_GRIND  = '<div class="tool" id="convTool">'
A_INS    = '<div class="fl" data-i18n="role">Role</div>'

home,     rest   = cut(body, A_LOG)
logtab,   rest   = cut(rest, A_BEANS)
beanstab, rest   = cut(rest, A_GRIND)
grindtab, instab = cut(rest, A_INS)
for _n, _v in (('home',home),('logtab',logtab),('beanstab',beanstab),('grindtab',grindtab),('instab',instab)):
    _o, _c = len(re.findall(r'<div\b', _v)), _v.count('</div>')
    if _o != _c:
        raise SystemExit('BUILD ABORTED: %s has %d <div> and %d </div>' % (_n, _o, _c))
print('tab split: home %d, log %d, beans %d, grind %d, insights %d bytes'
      % (len(home), len(logtab), len(beanstab), len(grindtab), len(instab)))

# ---------- new patches go here, between the split and the assembly ----------
# (use must_replace, never a bare .replace)

# ===================== PASS 1: shot metrics schema + ESP handoff ingestion ====
#
# P1. gRead was capped at column AC. That is 29 columns and COLNAMES was 28, so
#     the schema had exactly one column of headroom left. Appending the metric
#     tail would have pushed the shot row past the read range, and the Sheets API
#     does not complain about that: it just returns fewer columns. gEnsureHeader,
#     gPatchRow and gInvList all key off rows[0], so every one of them would have
#     started reading a header that stops short of the columns being written.
#     Silent, and it would have looked like the write failed.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '''      async function gRead(tab) {
        var d = await gApi(
          "https://sheets.googleapis.com/v4/spreadsheets/" +
            GSHEET +
            "/values/" +
            encodeURIComponent(tab + "!A1:AC5000"),
        );''',
    '''      async function gRead(tab) {
        /* No column bound, on purpose. A fixed A1 window has to be wide enough
     for the schema and narrow enough to fit inside the tab's actual grid, and
     those two move in opposite directions. AC was too narrow once the metric
     columns were appended. BZ was wider than the Inventory tab's grid, and the
     Sheets API answers 400 rather than clamping, so EVERY read of that tab
     failed: inventory, the identity gate and the header migration all went down
     together. Naming the tab with no range returns everything in it and cannot
     be out of bounds. */
        var d = await gApi(
          "https://sheets.googleapis.com/v4/spreadsheets/" +
            GSHEET +
            "/values/" +
            encodeURIComponent(tab),
        );''',
    'P1 gRead asks for the whole tab, never a fixed column window')

# P2. The metric tail. Appended to COLNAMES by concat rather than typed into the
#     literal, so the list that defines the sheet header and the list bpApplyShot
#     writes values from are the same array and cannot drift apart.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '      var COLNAMES = [\n        "shot_id",',
    r'''      /* The eight scale-invariant metrics the ESP32 companion computes per shot,
   plus the classifier's own read of the shot type and the firmware build that
   produced them. APPENDED, never inserted: gEnsureHeader widens an existing
   sheet by adding missing names at the end, so a name's position here has to
   match its position there for every sheet that already carries rows.
   shot_id, peak_bar and avg_flow_mls are deliberately NOT in this list. Those
   columns have existed since the first schema and logshot only ever wrote them
   blank, so the handoff fills them rather than shipping a second column that
   means the same thing. */
      var BP_METRIC_COLS = [
        "resistance",
        "adherence",
        "undershoot",
        "channel",
        "retention_g",
        "pi_press",
        "temp_err",
        "first_drip_s",
        "shot_type_auto",
        "fw_version",
      ];
      var COLNAMES = [
        "shot_id",''',
    'P2a metric column names')

FEATURES_JS = must_replace(
    FEATURES_JS,
    '        "grind_um",\n      ];',
    '        "grind_um",\n      ].concat(BP_METRIC_COLS);',
    'P2b COLNAMES carries the metric tail')

# P3. The lane store. One row per (coffee, type), in its own tab.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '      var SHOT_TAB = "Shot Log",\n        INV_TAB = "Inventory";',
    r'''      var SHOT_TAB = "Shot Log",
        INV_TAB = "Inventory",
        LANE_TAB = "Lanes";
      /* One row per (coffee, type). Traditional, soup and filter of the same bag
   are three independent rows and are never averaged together: the styles run at
   different pressures, so folding them into one baseline would read a style
   switch as a grind collapse and advise a correction that is not needed.
   h1..h5 are the rolling short history, newest first, one shot per cell as
   date|grind_setting|resistance|rating. Five plain cells rather than one JSON
   blob, so a lane can be read and corrected in the sheet by hand. */
      var LANE_COLNAMES = [
        "lane_id",
        "coffee",
        "type",
        "updated",
        "n_shots",
        "base_resistance",
        "base_adherence",
        "base_channel",
        "base_yield_g",
        "base_grind_um",
        "note",
        "note_date",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
      ];''',
    'P3 lane tab and lane schema')

# P4. gEnsureHeader can only widen a tab that already exists. Every sheet created
#     before today has no Lanes tab at all, and gRead on a missing tab THROWS
#     rather than returning empty, so without this the advisor would fail on
#     every log with nothing the user could do about it.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '      async function gEnsureHeader(tab, want) {',
    r'''      async function gEnsureTab(tab, cols) {
        /* gEnsureHeader widens an existing tab. This one makes sure there IS one.
     A missing range is a 400 from the Sheets API, not an empty result, so the
     read has to be guarded by the create rather than the other way round. */
        var meta = await gApi(
          "https://sheets.googleapis.com/v4/spreadsheets/" +
            GSHEET +
            "?fields=sheets.properties.title",
        );
        var have = ((meta && meta.sheets) || []).some(function (s) {
          return s.properties && s.properties.title === tab;
        });
        if (!have) {
          await gApi(
            "https://sheets.googleapis.com/v4/spreadsheets/" + GSHEET + ":batchUpdate",
            {
              method: "POST",
              body: JSON.stringify({ requests: [{ addSheet: { properties: { title: tab } } }] }),
            },
          );
        }
        var rows = [];
        try {
          rows = await gRead(tab);
        } catch (e) {}
        if (!rows.length || !rows[0] || !rows[0].length) {
          await gAppend(tab, cols);
          return true;
        }
        return gEnsureHeader(tab, cols);
      }
      async function gEnsureHeader(tab, want) {''',
    'P4 gEnsureTab creates a missing tab')

FEATURES_JS = must_replace(
    FEATURES_JS,
    '        var b = await gEnsureHeader(INV_TAB, INV_COLNAMES);',
    '        var b = await gEnsureHeader(INV_TAB, INV_COLNAMES);\n'
    '        try {\n'
    '          await gEnsureTab(LANE_TAB, LANE_COLNAMES);\n'
    '        } catch (e) {}',
    'P4b migrate the lane tab too')

# P5. A sheet born today gets all three tabs, so gEnsureTab is a no-op for it.
FEATURES_JS = must_replace(
    FEATURES_JS,
    'sheets: [{ properties: { title: SHOT_TAB } }, { properties: { title: INV_TAB } }],',
    'sheets: [\n'
    '              { properties: { title: SHOT_TAB } },\n'
    '              { properties: { title: INV_TAB } },\n'
    '              { properties: { title: LANE_TAB } },\n'
    '            ],',
    'P5a new sheets are born with the lane tab')

FEATURES_JS = must_replace(
    FEATURES_JS,
    '          { method: "POST", body: JSON.stringify({ values: [INV_COLNAMES] }) },\n'
    '        );\n'
    '        return GSHEET;',
    '          { method: "POST", body: JSON.stringify({ values: [INV_COLNAMES] }) },\n'
    '        );\n'
    '        await gApi(\n'
    '          "https://sheets.googleapis.com/v4/spreadsheets/" +\n'
    '            GSHEET +\n'
    '            "/values/" +\n'
    '            encodeURIComponent(LANE_TAB + "!A1") +\n'
    '            ":append?valueInputOption=RAW",\n'
    '          { method: "POST", body: JSON.stringify({ values: [LANE_COLNAMES] }) },\n'
    '        );\n'
    '        return GSHEET;',
    'P5b lane header at birth')

# P6. The handoff itself.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '      /* bootstrap last: every definition exists by now */',
    r'''      /* ---- ESP32 shot handoff ----
   The webapp is HTTPS on GitHub Pages and the companion is HTTP on a LAN IP.
   An HTTPS page CANNOT fetch an HTTP LAN address: that is mixed content, the
   browser blocks it outright, and no header on the ESP can lift it. It can only
   be NAVIGATED to. So the device panel builds a link carrying the metrics in
   the query string, and opening that link lands here. This is verified on the
   iPhone; a background fetch is not a thing that can be made to work.

   Contract with the firmware. Everything is optional except bp=1:
     bp=1  marks the link          sid  shot id          fw  FW_VERSION
     t     classifier type read    y    yield g          d   duration s
     pk    peak bar                fl   avg flow ml/s    tc  temp C
     rs    resistance              ad   adherence        us  undershoot
     ch    channel                 rt   retention g      pi  preinfusion bar
     te    temp error C            fd   first drip s

   Nothing here trusts the link. Every numeric is parsed to a finite number or
   dropped, and the type only takes effect if it is one the form actually has.
   The row is still written by logshot behind bpCoffeeGate, so a handoff cannot
   invent a coffee identity or start a lane on its own. */
      var BPSHOT = null;
      var BP_Q = {
        rs: "resistance",
        ad: "adherence",
        us: "undershoot",
        ch: "channel",
        rt: "retention_g",
        pi: "pi_press",
        te: "temp_err",
        fd: "first_drip_s",
      };
      function bpQNum(p, k) {
        var v = p.get(k);
        if (v === null || String(v).trim() === "") return "";
        var n = parseFloat(v);
        return isFinite(n) ? n : "";
      }
      function bpFill(id, v) {
        if (v === "" || v === null || v === undefined) return;
        var el = document.getElementById(id);
        if (!el) return;
        el.value = String(v);
        try {
          el.dispatchEvent(new Event("input", { bubbles: true }));
        } catch (e) {}
      }
      function bpHandoff() {
        var qs = String(location.search || "");
        if (qs.indexOf("bp=1") < 0) return false;
        if (!bpIngest(qs)) return false;
        /* Strip the query before anything else can read it again. A reload used to
     be free; with a handoff sitting in the URL it would re-ingest the same shot
     and there would be no sign of it except a duplicate row. Only the URL path
     needs this; the poller never puts anything in the address bar. */
        try {
          history.replaceState(null, "", location.pathname);
        } catch (e) {}
        return true;
      }
      function bpIngest(qs) {
        /* ONE parser, two callers: the tapped link and the ntfy poller. Two
     parsers for one wire format is how they drift, and a drift here writes
     wrong numbers into a lane baseline with nothing on screen to show it. */
        var p;
        try {
          p = new URLSearchParams(String(qs || "").replace(/^[^?]*\?/, ""));
        } catch (e) {
          return false;
        }
        if (String(p.get("bp") || "") !== "1") return false;
        var s = {
          sid: String(p.get("sid") || "").trim(),
          fw: String(p.get("fw") || "").trim(),
          type: String(p.get("t") || "")
            .trim()
            .toLowerCase(),
          yieldG: bpQNum(p, "y"),
          durationS: bpQNum(p, "d"),
          peakBar: bpQNum(p, "pk"),
          avgFlow: bpQNum(p, "fl"),
          tempC: bpQNum(p, "tc"),
          m: {},
        };
        Object.keys(BP_Q).forEach(function (k) {
          s.m[BP_Q[k]] = bpQNum(p, k);
        });
        BPSHOT = s;
        if (s.sid) bpMarkSeen(s.sid);
        try {
          showTab("log");
        } catch (e) {}
        try {
          setLogMode("after");
        } catch (e) {}
        /* Method BEFORE the fields: setLogMethod re-renders the form, so anything
     filled before it would be wiped. The classifier reads shot SHAPE, not the
     profile name - a shot named "Adaptive Light Roast Soup" ran at 6.5 bar and
     was traditional espresso - so its read is the honest default here, and the
     method chips still override it. */
        if (["espresso", "soup", "filter"].indexOf(s.type) >= 0) {
          try {
            setLogMethod(s.type);
          } catch (e) {}
        }
        bpFill("gyield", s.yieldG === "" ? "" : Math.round(s.yieldG * 10) / 10);
        bpFill("gtime", s.durationS === "" ? "" : Math.round(s.durationS));
        bpFill("gtemp", s.tempC === "" ? "" : Math.round(s.tempC * 10) / 10);
        try {
          gRatioApply();
        } catch (e) {}
        bpShotBanner();
        return true;
      }
      function bpShotBanner() {
        var el = document.getElementById("bpShotBanner");
        if (!el) return;
        if (!BPSHOT) {
          el.style.display = "none";
          el.textContent = "";
          return;
        }
        var isEs = typeof LANG !== "undefined" && LANG === "es";
        var bits = [];
        if (BPSHOT.durationS !== "") bits.push(Math.round(BPSHOT.durationS) + "s");
        if (BPSHOT.yieldG !== "") bits.push(Math.round(BPSHOT.yieldG) + "g");
        if (BPSHOT.peakBar !== "") bits.push(BPSHOT.peakBar.toFixed(1) + " bar");
        if (BPSHOT.m.resistance !== "") bits.push("R " + BPSHOT.m.resistance.toFixed(2));
        var head = isEs ? "Datos del shot recibidos" : "Shot data received";
        var tail = isEs
          ? "Agrega cafe, dosis y calificacion, luego guarda."
          : "Add coffee, dose and rating, then save.";
        el.textContent =
          head +
          (BPSHOT.fw ? " (fw " + BPSHOT.fw + ")" : "") +
          (bits.length ? ": " + bits.join(", ") : "") +
          ". " +
          tail;
        el.style.display = "";
      }
      function bpApplyShot(cols) {
        /* Fills the three columns the schema has always carried but logshot never
     had a value for, then appends the metric tail in BP_METRIC_COLS order. The
     tail is appended even with no handoff, as blanks, so every row is the same
     width and a later append stays safe. */
        var s = BPSHOT;
        if (s) {
          if (s.sid && !cols[0]) cols[0] = s.sid;
          if (s.peakBar !== "") cols[12] = s.peakBar;
          if (s.avgFlow !== "") cols[13] = s.avgFlow;
        }
        return cols.concat(
          BP_METRIC_COLS.map(function (name) {
            if (!s) return "";
            if (name === "shot_type_auto") return s.type || "";
            if (name === "fw_version") return s.fw || "";
            var v = s.m[name];
            return v === undefined || v === "" ? "" : v;
          }),
        );
      }
      function bpClearShot() {
        BPSHOT = null;
        bpShotBanner();
      }

      /* bootstrap last: every definition exists by now */''',
    'P6 handoff ingestion')

FEATURES_JS = must_replace(
    FEATURES_JS,
    '      uiStart();\n      try {\n        pickerizeAll();\n      } catch (e) {}',
    '      uiStart();\n      try {\n        pickerizeAll();\n      } catch (e) {}\n'
    '      try {\n        bpHandoff();\n      } catch (e) {}',
    'P6b call the handoff at boot')

# ===================== PASS 1b: the pre-I18N boot window ====================
#
# P7. t() is called during the boot sequence at the tail of the source script,
#     which is concatenated BEFORE this blob, so I18N is still the hoisted
#     undefined at that point and I18N[LANG] threw. Both callers are async
#     (loadRot, refresh), so it surfaced as an unhandled rejection rather than a
#     script abort, which is why the page booted and the fault stayed invisible.
#     Returning the key is not a new behaviour: t() already falls back to k for a
#     key it cannot resolve, and applyLang() re-renders everything after I18N is
#     assigned and before first paint, so nothing reaches the screen untranslated.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '      function t(k) {\n'
    '        return (I18N[LANG] && I18N[LANG][k]) || I18N.en[k] || k;\n'
    '      }',
    '      function t(k) {\n'
    '        if (typeof I18N === "undefined" || !I18N) return k;\n'
    '        return (I18N[LANG] && I18N[LANG][k]) || I18N.en[k] || k;\n'
    '      }',
    'P7 t() cannot throw before I18N exists')

# ===================== PASS 2a: adoption identity, sheet visibility, two fixes =
#
# P8. The apple- prefixed meta is the only standalone-mode hint the page carried.
#     The unprefixed name is the one every non-Safari engine reads. Both, because
#     dropping the apple one would change nothing except break iOS.
HEAD = must_replace(
    HEAD,
    '    <meta name="apple-mobile-web-app-capable" content="yes" />',
    '    <meta name="apple-mobile-web-app-capable" content="yes" />\n'
    '    <meta name="mobile-web-app-capable" content="yes" />',
    'P8 unprefixed mobile-web-app-capable alongside the apple one')

# P9. The handoff banner is the first Spanish string a shot ever produces and it
#     was the only unaccented one in the file.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '          ? "Agrega cafe, dosis y calificacion, luego guarda."',
    '          ? "Agrega caf\u00e9, dosis y calificaci\u00f3n, luego guarda."',
    'P9 accents in the handoff banner')

# P10. gAdopt set GSHEET and nothing else, so GNAME kept whatever the PREVIOUS
#      sheet was called and the status line, once it started naming the sheet,
#      would have confidently named the wrong one. Take the name where the caller
#      already has it (Drive files.list returns it) and learn it where it does not.
#      gLearnName re-checks GSHEET before assigning: two adoptions in flight would
#      otherwise let the slower response overwrite the newer sheet's name.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '''      function gAdopt(id) {
        GSHEET = id;
        try {
          localStorage.setItem("gsheet", id);
        } catch (e) {}
      }''',
    '''      async function gLearnName(id) {
        /* Some adoption paths know the spreadsheet's name, some do not. The ones
     that do not learn it here rather than leaving the status line blank. The
     GSHEET re-check is not paranoia: this is fired and not awaited, so a second
     adoption during the round trip would otherwise be relabelled by the first. */
        try {
          var d = await gApi(
            "https://sheets.googleapis.com/v4/spreadsheets/" + id + "?fields=properties.title",
          );
          var n = d && d.properties ? String(d.properties.title || "") : "";
          if (!n || GSHEET !== id) return "";
          GNAME = n;
          try {
            localStorage.setItem("gsheetname", n);
          } catch (e) {}
          try {
            renderSheetStatus();
          } catch (e) {}
          return n;
        } catch (e) {
          return "";
        }
      }
      function gAdopt(id, name) {
        GSHEET = id;
        try {
          localStorage.setItem("gsheet", id);
        } catch (e) {}
        GNAME = String(name || "");
        try {
          if (GNAME) localStorage.setItem("gsheetname", GNAME);
          else localStorage.removeItem("gsheetname");
        } catch (e) {}
        if (!GNAME) {
          try {
            gLearnName(id);
          } catch (e) {}
        }
        try {
          renderSheetStatus();
        } catch (e) {}
      }''',
    'P10 gAdopt records which sheet it adopted')

# P11. gListLogs matches any spreadsheet whose NAME CONTAINS BrewPilot. That is a
#      search filter, not an identity test, and it adopted a stray file in a
#      signed-in account without a word on screen. Identity is the schema.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '''      async function gScoreLogs(files) {
        var withData = [];
        for (var i = 0; i < files.length; i++) {
          var rc = await gRowCount(files[i].id);
          if (rc > 0) withData.push({ id: files[i].id, rows: rc });
        }''',
    '''      async function gHasSchema(id) {
        /* Both tabs, not either. A spreadsheet with only Shot Log could be an
     export, a copy, or someone else's tool; the pair is what this app creates
     and nothing else in a Drive is likely to have. Missing tab, no permission
     and malformed response all answer false, so an unreadable file is never
     adopted on the strength of its name. */
        try {
          var meta = await gApi(
            "https://sheets.googleapis.com/v4/spreadsheets/" +
              id +
              "?fields=sheets.properties.title",
          );
          var have = {};
          ((meta && meta.sheets) || []).forEach(function (s) {
            if (s.properties && s.properties.title) have[String(s.properties.title)] = 1;
          });
          return !!(have[SHOT_TAB] && have[INV_TAB]);
        } catch (e) {
          return false;
        }
      }
      async function gRealLogs(files) {
        var out = [];
        for (var i = 0; i < files.length; i++) {
          if (await gHasSchema(files[i].id)) out.push(files[i]);
        }
        return out;
      }
      async function gScoreLogs(files) {
        var withData = [];
        for (var i = 0; i < files.length; i++) {
          var rc = await gRowCount(files[i].id);
          if (rc > 0) withData.push({ id: files[i].id, name: files[i].name || "", rows: rc });
        }''',
    'P11a schema probe: adoption requires both tabs')

FEATURES_JS = must_replace(
    FEATURES_JS,
    '''        if (!files.length) return false;
        var withData = await gScoreLogs(files);
        if (withData.length === 0) {
          gAdopt(files[0].id);
          return true;
        }
        if (withData.length === 1 || withData[0].rows >= withData[1].rows * 2) {
          gAdopt(withData[0].id);
          return true;
        }''',
    '''        if (!files.length) return false;
        /* Filter BEFORE scoring. The zero-rows branch below adopts a candidate
     outright with no further test, and that is the exact branch the stray file
     came in through: it had the name, it had no rows, so it won by default. */
        var real = await gRealLogs(files);
        if (!real.length) return false;
        var withData = await gScoreLogs(real);
        if (withData.length === 0) {
          gAdopt(real[0].id, real[0].name);
          return true;
        }
        if (withData.length === 1 || withData[0].rows >= withData[1].rows * 2) {
          gAdopt(withData[0].id, withData[0].name);
          return true;
        }''',
    'P11b gAutoLink adopts only a real log')

FEATURES_JS = must_replace(
    FEATURES_JS,
    '''          var files = await gListLogs();
          var withData = await gScoreLogs(files);
          if (!withData.length) return;
          if (withData.length === 1 || withData[0].rows >= withData[1].rows * 2) {
            gAdopt(withData[0].id);
          } else gPickSheet(withData);''',
    '''          var files = await gRealLogs(await gListLogs());
          var withData = await gScoreLogs(files);
          if (!withData.length) return;
          if (withData.length === 1 || withData[0].rows >= withData[1].rows * 2) {
            gAdopt(withData[0].id, withData[0].name);
          } else gPickSheet(withData);''',
    'P11c gTryUpgrade adopts only a real log')

# P11d. The chooser listed candidates by row count alone, so two logs with similar
#       histories were two identical buttons.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '          bt.textContent = c.rows + " logged " + (c.rows === 1 ? "row" : "rows");',
    '          bt.textContent =\n'
    '            (c.name ? c.name + " - " : "") + c.rows + " logged " + (c.rows === 1 ? "row" : "rows");',
    'P11d the chooser names each candidate')

FEATURES_JS = must_replace(
    FEATURES_JS,
    '''          bt.onclick = function () {
            gAdopt(c.id);''',
    '''          bt.onclick = function () {
            gAdopt(c.id, c.name);''',
    'P11e the chooser passes the name it just displayed')

# P12. Relink is a deliberate paste, so the schema is not forced on it: the gRead
#      probe already refuses a sheet with no Shot Log. But it wrote gsheet without
#      gsheetname, so the status line would have shown the PREVIOUS sheet's name
#      against the new sheet's data.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '''          try {
            localStorage.setItem("gsheet", id);
          } catch (e) {}
          el.value = "";''',
    '''          try {
            localStorage.setItem("gsheet", id);
          } catch (e) {}
          GNAME = "";
          try {
            localStorage.removeItem("gsheetname");
          } catch (e) {}
          try {
            gLearnName(id);
          } catch (e) {}
          el.value = "";''',
    'P12 relink refreshes the name it shows')

# ===================== PASS 2b: the per-(coffee, type) lane store ============
#
# P13. The store itself. Placed next to LANE_COLNAMES because the row shape and
#      the code that fills it drifting apart is the failure this whole schema is
#      arranged to prevent.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '''        "h4",
        "h5",
      ];

      function gConfigured() {''',
    r'''        "h4",
        "h5",
      ];

      /* ---- the lane store -----------------------------------------------------
   A lane is one row per (coffee, type). Traditional espresso, soup and filter
   of the SAME bag are three lanes and are never averaged: they run at wildly
   different pressures, so folding them together would read a style switch as a
   grind collapse and advise a correction that is not needed.

   A shot files into a lane only when the coffee is a canonical INVENTORY name.
   That is re-checked here rather than trusted from a flag bpCoffeeGate set
   earlier, for two reasons. logAction has a catch path that calls logshot()
   WITHOUT the gate, so a flag would carry the previous shot's grant into a shot
   the gate never saw. And bpInInventory is pure, so re-asking costs nothing and
   cannot go stale. A single dose has no bag, no rest window and no second shot
   to compare against; a name the gate could not place is more likely a typo
   than a new coffee, and starting a lane on a typo is how one bag turns into
   two histories that each look thin. Both get advised generically by type. */
      var LANE_TYPES = ["espresso", "soup", "filter"];
      var LANE_HIST = 5;
      var LANE_MIN = 3;
      /* Weight cap on the running mean. Without it a lane twenty shots old is
   effectively frozen and a real change in the bag never moves it; with it the
   baseline stays responsive without whipsawing on any single shot. */
      var LANE_WCAP = 20;
      /* Measured, not guessed, and from four verified shots only. Soup
   resistance is genuinely noisy at low pressure - two shots of the same coffee
   read 0.09 and 0.20 - so its band is wide on purpose. A tight band there would
   fire on every shot and be ignored within a week. Traditional sat at 2.78 and
   2.88, so its band is tight and a miss there means something.
   Filter is null. There is no measured filter baseline yet and inventing one
   would be worse than saying so. */
      var LANE_SEED = {
        espresso: {
          resistance: 2.83,
          band: 0.12,
          adherence: 0.85,
          channel: 0.05,
          yield_g: 56,
          obs: [2.78, 2.88],
          n: 2,
        },
        soup: {
          resistance: 0.15,
          band: 0.6,
          adherence: 0.75,
          channel: 0.25,
          yield_g: 81,
          obs: [0.09, 0.2],
          n: 2,
        },
        filter: null,
      };

      function laneNum(v) {
        if (v === undefined || v === null || String(v).trim() === "") return "";
        var n = parseFloat(v);
        return isFinite(n) ? n : "";
      }
      function laneRound(v, d) {
        if (v === "") return "";
        var m = Math.pow(10, d);
        return Math.round(v * m) / m;
      }
      function laneNormType(t) {
        var v = String(t || "")
          .trim()
          .toLowerCase();
        if (v === "traditional") v = "espresso";
        return LANE_TYPES.indexOf(v) >= 0 ? v : "";
      }
      function laneId(coffee, type) {
        /* The type is part of the identity, not a column that happens to sit
     next to it. No type, no lane: a row keyed on the coffee alone would collect
     all three styles into one baseline the first time it was written. bpNorm
     collapses every non-alphanumeric to a space, so the coffee half can never
     contain the separator and the id cannot be ambiguous. */
        var c = bpNorm(coffee || ""),
          t = laneNormType(type);
        if (!c || !t) return "";
        return c + "|" + t;
      }
      function laneDay(ts) {
        var s = String(ts || "").trim();
        var m = s.match(/^\d{4}-\d{2}-\d{2}/);
        if (m) return m[0];
        var d = new Date(s);
        if (!isNaN(d.getTime())) return d.toISOString().slice(0, 10);
        return new Date().toISOString().slice(0, 10);
      }
      function laneCellSafe(v) {
        if (v === undefined || v === null) return "";
        return String(v)
          .replace(/[|\r\n]/g, " ")
          .trim();
      }
      function laneHistCell(shot) {
        /* date|grind_setting|resistance|rating, one shot per cell. Five plain
     cells rather than one JSON blob, so a lane can be read and corrected in the
     sheet by hand. The separator is stripped from every field first: a grind
     setting typed as "3|4" would otherwise split the cell and shift every
     field after it. */
        return [laneDay(shot.date), shot.grind, shot.resistance, shot.rating]
          .map(laneCellSafe)
          .join("|");
      }
      function laneCache() {
        try {
          var o = JSON.parse(localStorage.getItem("bpLanes") || "{}");
          return o && typeof o === "object" ? o : {};
        } catch (e) {
          return {};
        }
      }
      function laneCacheWrite(map) {
        try {
          localStorage.setItem("bpLanes", JSON.stringify(map));
        } catch (e) {}
      }
      function laneGet(coffee, type) {
        var id = laneId(coffee, type);
        if (!id) return null;
        return laneCache()[id] || null;
      }
      function laneBlank(id) {
        /* Built from LANE_COLNAMES, so a column added to the schema exists on a
     new lane without a second edit here. */
        var o = {};
        LANE_COLNAMES.forEach(function (k) {
          o[k] = "";
        });
        o.lane_id = id;
        o.n_shots = 0;
        return o;
      }
      function laneShotFromCols(cols) {
        /* Read by NAME through COLNAMES, never by a literal index. The metric
     tail is appended by concat, so an index written here would be correct until
     the day a column moves and then silently wrong. */
        function at(name) {
          var i = COLNAMES.indexOf(name);
          if (i < 0) return "";
          var v = cols[i];
          return v === undefined || v === null ? "" : v;
        }
        return {
          coffee: String(at("coffee") || "").trim(),
          type: laneNormType(at("type")),
          date: String(at("timestamp") || ""),
          grind: at("grind_setting"),
          grindUm: laneNum(at("grind_um")),
          rating: at("rating"),
          resistance: laneNum(at("resistance")),
          adherence: laneNum(at("adherence")),
          channel: laneNum(at("channel")),
          yieldG: laneNum(at("yield_g")),
        };
      }
      function laneBlend(prev, w, v) {
        /* Running mean against a capped weight, not a recompute. The sheet keeps
     five shots of history and a lane may be twenty shots old, so there is
     nothing left to recompute from. A blank shot value leaves the baseline
     alone rather than dragging it toward zero. */
        if (v === "") return prev;
        if (prev === "" || !(w > 0)) return v;
        return (prev * w + v) / (w + 1);
      }
      function laneApply(lane, shot) {
        var n = laneNum(lane.n_shots);
        if (n === "") n = 0;
        var w = Math.min(n, LANE_WCAP);
        lane.lane_id = laneId(shot.coffee, shot.type);
        lane.coffee = shot.coffee;
        lane.type = shot.type;
        lane.updated = laneDay(shot.date);
        lane.n_shots = n + 1;
        lane.base_resistance = laneRound(
          laneBlend(laneNum(lane.base_resistance), w, shot.resistance),
          3,
        );
        lane.base_adherence = laneRound(laneBlend(laneNum(lane.base_adherence), w, shot.adherence), 3);
        lane.base_channel = laneRound(laneBlend(laneNum(lane.base_channel), w, shot.channel), 3);
        lane.base_yield_g = laneRound(laneBlend(laneNum(lane.base_yield_g), w, shot.yieldG), 1);
        lane.base_grind_um = laneRound(laneBlend(laneNum(lane.base_grind_um), w, shot.grindUm), 0);
        var hist = [];
        for (var i = 1; i <= LANE_HIST; i++) hist.push(lane["h" + i] || "");
        hist.unshift(laneHistCell(shot));
        hist = hist.slice(0, LANE_HIST);
        for (var j = 0; j < LANE_HIST; j++) lane["h" + (j + 1)] = hist[j];
        return lane;
      }
      function laneBaseline(coffee, type) {
        /* Three honest answers, and which one it is comes back in .source so a
     caller cannot mistake the population figure for this bag's own. */
        var t = laneNormType(type);
        var l = laneGet(coffee, t);
        var n = l ? laneNum(l.n_shots) : "";
        if (n === "") n = 0;
        if (l && n >= LANE_MIN) {
          var s0 = LANE_SEED[t];
          return {
            source: "lane",
            type: t,
            n: n,
            resistance: laneNum(l.base_resistance),
            adherence: laneNum(l.base_adherence),
            channel: laneNum(l.base_channel),
            yield_g: laneNum(l.base_yield_g),
            grind_um: laneNum(l.base_grind_um),
            band: s0 ? s0.band : 0.4,
          };
        }
        var s = LANE_SEED[t];
        if (!s) return { source: "none", type: t, n: n };
        return {
          source: "type",
          type: t,
          n: n,
          resistance: s.resistance,
          adherence: s.adherence,
          channel: s.channel,
          yield_g: s.yield_g,
          band: s.band,
          obs: s.obs,
        };
      }
      function laneEligible(coffee) {
        /* The whole gate, in one place. Inventory identity and not a single
     dose. Pure, so it can be re-asked at file time without going stale. */
        var c = String(coffee || "").trim();
        if (!c) return false;
        if (typeof bpIsSingle === "function" && bpIsSingle(c)) return false;
        return typeof bpInInventory === "function" && bpInInventory(c);
      }
      function laneRowToObj(head, row) {
        var o = {};
        for (var i = 0; i < head.length; i++) {
          var k = String(head[i]).trim();
          if (k) o[k] = row && row[i] !== undefined ? row[i] : "";
        }
        return o;
      }
      async function gLaneList() {
        /* Reconciliation. The sheet is the truth and this replaces the cache
     wholesale, so a lane corrected by hand in the sheet wins over whatever the
     browser was carrying. Any failure leaves the cache exactly as it was. */
        if (dataMode() !== "google") return laneCache();
        var rows = [];
        try {
          rows = await gRead(LANE_TAB);
        } catch (e) {
          return laneCache();
        }
        if (!rows.length || !rows[0] || !rows[0].length) return laneCache();
        var head = rows[0],
          map = {};
        for (var i = 1; i < rows.length; i++) {
          var o = laneRowToObj(head, rows[i]);
          var id = String(o.lane_id || "").trim();
          if (!id) continue;
          map[id] = o;
        }
        laneCacheWrite(map);
        return map;
      }
      async function gLaneUpsert(lane) {
        if (dataMode() !== "google") return false;
        try {
          await gEnsureTab(LANE_TAB, LANE_COLNAMES);
        } catch (e) {}
        var rows = [];
        try {
          rows = await gRead(LANE_TAB);
        } catch (e) {
          return false;
        }
        if (!rows.length || !rows[0] || !rows[0].length) return false;
        var head = rows[0],
          idc = -1;
        for (var i = 0; i < head.length; i++) {
          if (String(head[i]).trim() === "lane_id") idc = i;
        }
        if (idc < 0) return false;
        var want = String(lane.lane_id),
          at = -1;
        for (var r = 1; r < rows.length; r++) {
          if (String((rows[r] || [])[idc] || "").trim() === want) {
            at = r + 1;
            break;
          }
        }
        if (at > 0) {
          /* note and note_date are deliberately NOT in the patch. They are the
     one part of a lane a person writes by hand, and filing a shot must not be
     able to erase a note. gPatchRow copies every unnamed column back verbatim,
     so leaving them out is what preserves them. */
          var patch = {};
          LANE_COLNAMES.forEach(function (k) {
            if (k === "note" || k === "note_date") return;
            if (lane[k] !== undefined) patch[k] = lane[k];
          });
          await gPatchRow(LANE_TAB, at, patch);
          return true;
        }
        await gAppend(
          LANE_TAB,
          head.map(function (h) {
            var k = String(h).trim();
            return lane[k] === undefined ? "" : lane[k];
          }),
        );
        return true;
      }
      async function laneRecord(cols) {
        /* Returns the reason it declined rather than just falling through. A
     silent no-op is indistinguishable from a bug, and this one runs after the
     row is already saved where nobody would go looking. */
        var shot = laneShotFromCols(cols);
        if (!shot.coffee) return "no-coffee";
        if (!shot.type) return "no-type";
        if (!laneEligible(shot.coffee)) return "not-in-inventory";
        var id = laneId(shot.coffee, shot.type);
        if (!id) return "no-id";
        var map = laneCache();
        var lane = map[id] || laneBlank(id);
        laneApply(lane, shot);
        map[id] = lane;
        laneCacheWrite(map);
        try {
          await gLaneUpsert(lane);
        } catch (e) {
          return "filed-local-only";
        }
        return "filed";
      }

      function gConfigured() {''',
    'P13 the per-(coffee, type) lane store')

# P14. Reconcile the cache against the sheet at startup, right after the Lanes
#      tab is known to exist. Failure leaves the cache untouched.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '''        var b = await gEnsureHeader(INV_TAB, INV_COLNAMES);
        try {
          await gEnsureTab(LANE_TAB, LANE_COLNAMES);
        } catch (e) {}''',
    '''        var b = await gEnsureHeader(INV_TAB, INV_COLNAMES);
        try {
          await gEnsureTab(LANE_TAB, LANE_COLNAMES);
        } catch (e) {}
        try {
          await gLaneList();
        } catch (e) {}''',
    'P14 reconcile the lane cache on sheet read')

# ===================== PASS 3: close the two gaps, then read the lanes =======
#
# P15. i18n. Both dictionaries in one patch so they cannot drift apart, which is
#      the failure audit check 3b exists to catch.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '          insNothingYet: "Nothing stands out in your data yet. That is a real answer, not a bug.",',
    '          insNothingYet: "Nothing stands out in your data yet. That is a real answer, not a bug.",\n'
    '          laneFiled: "Lane updated. {n} shots on this coffee and method.",\n'
    '          laneNotInv: "Not filed to a lane. This coffee is not in your inventory, so it is advised by method only.",\n'
    '          lanePending: "Saved here, but the lane did not reach the sheet. It will sync on the next connection.",\n'
    '          laneNoBase: "No {m} baseline yet. Nothing to compare this against, and guessing one would be worse than saying so.",\n'
    '          laneTypeBase: "Using the general {m} figures. {n} more shots on this coffee before it has its own.",\n'
    '          laneRHigh: "Resistance ran {n}% above this lane. The puck is tighter than usual: grind coarser, or check the dose.",\n'
    '          laneRLow: "Resistance ran {n}% below this lane. The puck is looser than usual: grind finer.",\n'
    '          laneChan: "Channelling above this lane\\u2019s norm. That is distribution and puck prep, not grind.",\n'
    '          laneNoTaste: "These are flow numbers only. They cannot tell you how it tasted.",',
    'P15a lane strings, en')

FEATURES_JS = must_replace(
    FEATURES_JS,
    '          insNothingYet:\n            "Todav\u00eda no destaca nada en tus datos. Eso es una respuesta real, no un error.",',
    '          insNothingYet:\n            "Todav\u00eda no destaca nada en tus datos. Eso es una respuesta real, no un error.",\n'
    '          laneFiled: "Carril actualizado. {n} shots de este caf\u00e9 y m\u00e9todo.",\n'
    '          laneNotInv: "No se archiv\u00f3 en un carril. Este caf\u00e9 no est\u00e1 en tu inventario, as\u00ed que se aconseja solo por m\u00e9todo.",\n'
    '          lanePending: "Guardado aqu\u00ed, pero el carril no lleg\u00f3 a la hoja. Se sincronizar\u00e1 en la pr\u00f3xima conexi\u00f3n.",\n'
    '          laneNoBase: "A\u00fan no hay referencia de {m}. Nada con qu\u00e9 comparar, e inventar una ser\u00eda peor que decirlo.",\n'
    '          laneTypeBase: "Usando las cifras generales de {m}. Faltan {n} shots de este caf\u00e9 para tener las suyas.",\n'
    '          laneRHigh: "La resistencia sali\u00f3 {n}% por encima de este carril. El pastel est\u00e1 m\u00e1s apretado: muele m\u00e1s grueso, o revisa la dosis.",\n'
    '          laneRLow: "La resistencia sali\u00f3 {n}% por debajo de este carril. El pastel est\u00e1 m\u00e1s suelto: muele m\u00e1s fino.",\n'
    '          laneChan: "Canalizaci\u00f3n por encima de lo normal en este carril. Eso es distribuci\u00f3n y preparaci\u00f3n, no molienda.",\n'
    '          laneNoTaste: "Estos son solo n\u00fameros de flujo. No pueden decirte a qu\u00e9 supo.",',
    'P15b lane strings, es')

# P16. A sheet write can fail on quota, a permission change, or simply being
#      offline. gLaneUpsert returned false and laneRecord swallowed it, so the
#      cache advanced n_shots and the NEXT reconcile overwrote it from the sheet.
#      The shot disappeared from the baseline with nothing on screen and nothing
#      in the log. This is the gap the fake-API tests could not have found.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '''      async function gLaneList() {
        /* Reconciliation. The sheet is the truth and this replaces the cache
     wholesale, so a lane corrected by hand in the sheet wins over whatever the
     browser was carrying. Any failure leaves the cache exactly as it was. */
        if (dataMode() !== "google") return laneCache();
        var rows = [];
        try {
          rows = await gRead(LANE_TAB);
        } catch (e) {
          return laneCache();
        }''',
    '''      async function gLaneFlush() {
        /* Retry every lane whose write never landed, before reading the sheet.
     A lane still marked pending after this is genuinely ahead of the sheet. */
        var map = laneCache(),
          ids = Object.keys(map),
          any = false;
        for (var i = 0; i < ids.length; i++) {
          var l = map[ids[i]];
          if (!l || !l._pending) continue;
          try {
            if (await gLaneUpsert(l)) {
              delete l._pending;
              any = true;
            }
          } catch (e) {}
        }
        if (any) laneCacheWrite(map);
        return map;
      }
      async function gLaneList() {
        /* Reconciliation. The sheet is the truth and this replaces the cache
     wholesale, so a lane corrected by hand in the sheet wins over whatever the
     browser was carrying. Any failure leaves the cache exactly as it was. */
        if (dataMode() !== "google") return laneCache();
        var cached = await gLaneFlush();
        var rows = [];
        try {
          rows = await gRead(LANE_TAB);
        } catch (e) {
          return cached;
        }''',
    'P16a flush pending lane writes before reconciling')

FEATURES_JS = must_replace(
    FEATURES_JS,
    '''          map[id] = o;
        }
        laneCacheWrite(map);
        return map;
      }''',
    '''          map[id] = o;
        }
        /* A lane whose write never landed is AHEAD of the sheet. Taking the sheet
     copy would silently drop exactly the shots it is ahead by, which is the
     failure this whole pending mechanism exists to prevent. */
        Object.keys(cached).forEach(function (k) {
          if (cached[k] && cached[k]._pending) map[k] = cached[k];
        });
        laneCacheWrite(map);
        return map;
      }''',
    'P16b a pending lane survives reconciliation')

FEATURES_JS = must_replace(
    FEATURES_JS,
    '''        try {
          await gLaneUpsert(lane);
        } catch (e) {
          return "filed-local-only";
        }
        return "filed";''',
    '''        var ok = false;
        try {
          ok = await gLaneUpsert(lane);
        } catch (e) {
          ok = false;
        }
        if (dataMode() === "google" && !ok) {
          lane._pending = 1;
          map[id] = lane;
          laneCacheWrite(map);
          return "pending";
        }
        if (lane._pending) {
          delete lane._pending;
          map[id] = lane;
          laneCacheWrite(map);
        }
        return "filed";''',
    'P16c laneRecord marks a failed write pending instead of swallowing it')

# P17. The filing outcome was returned and thrown away. laneRecord runs after the
#      row is already saved, where nobody would think to look, so a coffee that
#      never starts a lane looked identical to one that did.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '      function bpApplyShot(cols) {',
    '''      function laneNote(reason, lane) {
        /* Reuses the handoff banner. A shot that did not file into a lane is the
     case worth saying out loud: silence there reads as success. */
        var el = document.getElementById("bpShotBanner");
        if (!el) return;
        var msg = "";
        if (reason === "filed") msg = t("laneFiled").replace("{n}", lane && lane.n_shots ? lane.n_shots : 1);
        else if (reason === "not-in-inventory") msg = t("laneNotInv");
        else if (reason === "pending") msg = t("lanePending");
        if (!msg) return;
        el.textContent = msg;
        el.style.display = "";
      }
      function laneAdvise(coffee, type, shot) {
        /* Descriptive first, one nudge second, and never a taste claim. Flow
     numbers cannot reach taste without TDS, and pretending otherwise is how a
     tool stops being trusted. */
        var out = [],
          b = laneBaseline(coffee, type);
        if (b.source === "none") {
          out.push(t("laneNoBase").replace("{m}", b.type || "filter"));
          return out;
        }
        if (b.source === "type") {
          out.push(
            t("laneTypeBase")
              .replace("{m}", b.type)
              .replace("{n}", Math.max(1, LANE_MIN - (b.n || 0))),
          );
        }
        var r = shot ? laneNum(shot.resistance) : "";
        if (r !== "" && b.resistance) {
          var d = (r - b.resistance) / b.resistance;
          if (Math.abs(d) > (b.band || 0.4)) {
            out.push(t(d > 0 ? "laneRHigh" : "laneRLow").replace("{n}", Math.round(Math.abs(d) * 100)));
          }
        }
        var ch = shot ? laneNum(shot.channel) : "";
        if (ch !== "" && b.channel !== "" && ch > b.channel + 0.15) out.push(t("laneChan"));
        if (out.length) out.push(t("laneNoTaste"));
        return out;
      }
      function insightsLane() {
        /* The most recent shot, read against its own lane. Insights are computed
     from IROWS, so this needs no new plumbing. */
        var out = [];
        if (!IROWS || !IROWS.length) return out;
        var last = null;
        for (var i = IROWS.length - 1; i >= 0; i--) {
          if (IROWS[i] && String(IROWS[i].coffee || "").trim()) {
            last = IROWS[i];
            break;
          }
        }
        if (!last) return out;
        try {
          return laneAdvise(last.coffee, last.type, {
            resistance: last.resistance,
            channel: last.channel,
          });
        } catch (e) {
          return out;
        }
      }
      function bpApplyShot(cols) {''',
    'P17 laneNote, laneAdvise and the insights reader')

FEATURES_JS = must_replace(
    FEATURES_JS,
    '      var INSIGHT_FNS = [insightsCost, insightsWater, insightsTiming];',
    '      var INSIGHT_FNS = [insightsLane, insightsCost, insightsWater, insightsTiming];',
    'P17b lane advice goes first in the insights panel')

# ===================== PASS 4a: the pre-shot lane card =======================
#
# P18. i18n for the card, both dictionaries in one patch.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '          laneNoTaste: "These are flow numbers only. They cannot tell you how it tasted.",',
    '          laneNoTaste: "These are flow numbers only. They cannot tell you how it tasted.",\n'
    '          laneCardHead: "This coffee, {m}: {n} logged",\n'
    '          laneUsually: "Usually {g}",\n'
    '          laneAbout: "about {n} um",\n'
    '          laneHold: "Last one sat in range. Same setting.",\n'
    '          laneGoCoarse: "Last one ran {n}% tight. Go coarser.",\n'
    '          laneGoFine: "Last one ran {n}% loose. Go finer.",\n'
    '          laneTry: "Try about {g}.",\n'
    '          laneNoPhysics: "No flow data on this lane, so grind and rating only.",',
    'P18a card strings, en')

FEATURES_JS = must_replace(
    FEATURES_JS,
    '          laneNoTaste: "Estos son solo n\u00fameros de flujo. No pueden decirte a qu\u00e9 supo.",',
    '          laneNoTaste: "Estos son solo n\u00fameros de flujo. No pueden decirte a qu\u00e9 supo.",\n'
    '          laneCardHead: "Este caf\u00e9, {m}: {n} registrados",\n'
    '          laneUsually: "Normalmente {g}",\n'
    '          laneAbout: "unos {n} um",\n'
    '          laneHold: "El anterior qued\u00f3 en rango. Mismo ajuste.",\n'
    '          laneGoCoarse: "El anterior sali\u00f3 {n}% apretado. Muele m\u00e1s grueso.",\n'
    '          laneGoFine: "El anterior sali\u00f3 {n}% suelto. Muele m\u00e1s fino.",\n'
    '          laneTry: "Prueba alrededor de {g}.",\n'
    '          laneNoPhysics: "Sin datos de flujo en este carril, as\u00ed que solo molienda y calificaci\u00f3n.",',
    'P18b card strings, es')

# P19. The card. Everything here is chosen by what the lane CONTAINS, never by
#      the hardware picker. M_GAG is a declared setting and a declaration can be
#      wrong: Gaggiuino can be selected while the ESP reported nothing, or a shot
#      can be logged from a phone with the machine off. The presence of a
#      resistance value in this lane's own history is the only thing that can
#      honestly promise a physics read.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '      function laneNote(reason, lane) {',
    '''      function laneHistParse(cell) {
        var p = String(cell || "").split("|");
        return { date: p[0] || "", grind: p[1] || "", resistance: p[2] || "", rating: p[3] || "" };
      }
      function laneCardData(coffee, type) {
        /* Pure, so the card can be tested without a DOM. */
        var ty = laneNormType(type);
        if (!String(coffee || "").trim() || !ty) return null;
        var l = laneGet(coffee, ty),
          hist = [];
        if (l) {
          for (var i = 1; i <= LANE_HIST; i++) {
            var c = String(l["h" + i] || "").trim();
            if (c) hist.push(laneHistParse(c));
          }
        }
        var physics = hist.some(function (h) {
          return laneNum(h.resistance) !== "";
        });
        return {
          type: ty,
          lane: l,
          base: laneBaseline(coffee, ty),
          hist: hist,
          physics: physics,
          n: l ? laneNum(l.n_shots) || 0 : 0,
        };
      }
      function laneGrindHint(d) {
        /* The last setting actually used is a fact. The click figure is derived
     from stored microns and only appears when a grinder is selected, because
     a setting number means nothing without knowing which grinder it is on. */
        var last = d.hist.length ? d.hist[0].grind : "";
        var um = d.lane ? laneNum(d.lane.base_grind_um) : "";
        var gid = typeof lastGrinder === "function" ? lastGrinder() : "";
        var clicks = "";
        if (um !== "" && gid && typeof umToClicks === "function") {
          var c = umToClicks(um, gid);
          if (c !== null && isFinite(c)) clicks = String(Math.round(c * 10) / 10);
        }
        return { last: last, um: um, clicks: clicks };
      }
      function laneNudge(d) {
        /* Silent unless the lane carries flow data AND the last shot has a
     reading. A nudge invented from grind alone would be a guess wearing the
     clothes of a measurement. */
        if (!d.physics || !d.base || !d.base.resistance) return "";
        var h = d.hist.length ? d.hist[0] : null;
        if (!h) return "";
        var r = laneNum(h.resistance);
        if (r === "") return "";
        var dv = (r - d.base.resistance) / d.base.resistance;
        if (Math.abs(dv) <= (d.base.band || 0.4)) return t("laneHold");
        return t(dv > 0 ? "laneGoCoarse" : "laneGoFine").replace("{n}", Math.round(Math.abs(dv) * 100));
      }
      function laneLine(el, txt, dim) {
        var d = document.createElement("div");
        if (dim) d.style.color = "var(--dim)";
        d.textContent = txt;
        el.appendChild(d);
      }
      function renderLaneCard() {
        var el = document.getElementById("laneCard");
        if (!el) return;
        var coffee = ((document.getElementById("coffee") || {}).value || "").trim();
        var type = (document.getElementById("type") || {}).value || "";
        var d = laneCardData(coffee, type);
        if (!d) {
          el.style.display = "none";
          el.textContent = "";
          return;
        }
        el.innerHTML = "";
        if (d.n <= 0) {
          /* Nothing of this coffee in this method yet. Say which figures are
       standing in, or that none exist, rather than showing an empty card. */
          if (d.base.source === "none") laneLine(el, t("laneNoBase").replace("{m}", d.type));
          else
            laneLine(
              el,
              t("laneTypeBase")
                .replace("{m}", d.type)
                .replace("{n}", Math.max(1, LANE_MIN - (d.base.n || 0))),
            );
          el.style.display = "";
          return;
        }
        laneLine(el, t("laneCardHead").replace("{m}", d.type).replace("{n}", d.n));
        var g = laneGrindHint(d);
        if (g.last) {
          var line = t("laneUsually").replace("{g}", g.last);
          if (g.um !== "") line += " (" + t("laneAbout").replace("{n}", Math.round(g.um)) + ")";
          laneLine(el, line, true);
        }
        d.hist.forEach(function (h) {
          var bits = [h.date];
          if (h.grind) bits.push(h.grind);
          if (h.resistance !== "") bits.push("R " + h.resistance);
          if (h.rating !== "") bits.push(h.rating + "/10");
          laneLine(el, "  " + bits.join("  "), true);
        });
        var nudge = laneNudge(d);
        if (nudge) {
          if (g.clicks !== "") nudge += " " + t("laneTry").replace("{g}", g.clicks);
          laneLine(el, nudge);
        } else if (!d.physics) {
          laneLine(el, t("laneNoPhysics"), true);
        }
        if (d.base.source === "type") {
          laneLine(
            el,
            t("laneTypeBase")
              .replace("{m}", d.type)
              .replace("{n}", Math.max(1, LANE_MIN - (d.base.n || 0))),
            true,
          );
        }
        el.style.display = "";
      }
      function laneNote(reason, lane) {''',
    'P19 the pre-shot lane card')

# P20. Two triggers, because the card needs BOTH fields and either can move last.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '''      function updateCoffeeHint() {
        var el = document.getElementById("coffeeHint");
        if (!el) return;''',
    '''      function updateCoffeeHint() {
        try {
          renderLaneCard();
        } catch (e) {}
        var el = document.getElementById("coffeeHint");
        if (!el) return;''',
    'P20a coffee change redraws the card')

FEATURES_JS = must_replace(
    FEATURES_JS,
    '''      function renderLogForm() {
        var m = logMethod();''',
    '''      function renderLogForm() {
        try {
          renderLaneCard();
        } catch (e) {}
        var m = logMethod();''',
    'P20b method change redraws the card')


# ===================== PASS 5: pull the shot instead of being pushed ========
#
# P22. iOS will not open an https link in an installed PWA. No URL scheme, no
#      universal link, no manifest field changes it: a tapped ntfy action always
#      lands in the default browser, which is a DIFFERENT storage and a different
#      Google session from the home-screen app. That is why a logged shot ended
#      up under the wrong account.
#
#      So stop being pushed and start pulling. The firmware already publishes
#      every shot to ntfy with the handoff URL in its Actions header, and ntfy's
#      JSON poll returns that actions array verbatim. The app can read its own
#      shots off the topic on launch and the PWA opens normally from the drawer.
#      No firmware change at all.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '      function bpShotBanner() {',
    '''      function bpSeen() {
        try {
          var a = JSON.parse(localStorage.getItem("bpSeenShots") || "[]");
          return a && a.length ? a : [];
        } catch (e) {
          return [];
        }
      }
      function bpMarkSeen(sid) {
        /* Dedupe by shot id. The poller asks for a window of history every time,
     so without this every launch would re-offer the same shot, and accepting it
     twice would double a lane baseline. Capped so the list cannot grow forever. */
        var id = String(sid || "").trim();
        if (!id) return;
        var a = bpSeen();
        if (a.indexOf(id) >= 0) return;
        a.push(id);
        if (a.length > 200) a = a.slice(a.length - 200);
        try {
          localStorage.setItem("bpSeenShots", JSON.stringify(a));
        } catch (e) {}
      }
      function bpTopic() {
        try {
          return String(localStorage.getItem("ntfyTopic") || "").trim();
        } catch (e) {
          return "";
        }
      }
      function bpUrlsFromNtfy(text) {
        /* ntfy returns newline-delimited JSON, one message per line. A view
     action carries the handoff URL the firmware built. Parsed per line and each
     line guarded on its own: one malformed message must not discard the rest. */
        var out = [];
        String(text || "")
          .split("\\n")
          .forEach(function (line) {
            var t = line.trim();
            if (!t) return;
            var o;
            try {
              o = JSON.parse(t);
            } catch (e) {
              return;
            }
            if (!o || o.event !== "message" || !o.actions) return;
            o.actions.forEach(function (a) {
              if (!a || !a.url) return;
              if (String(a.url).indexOf("bp=1") < 0) return;
              out.push({ url: String(a.url), time: Number(o.time) || 0 });
            });
          });
        out.sort(function (a, b) {
          return b.time - a.time;
        });
        return out;
      }
      function bpSidOf(url) {
        try {
          return String(new URLSearchParams(String(url).replace(/^[^?]*\\?/, "")).get("sid") || "").trim();
        } catch (e) {
          return "";
        }
      }
      async function bpPollNtfy(hours) {
        /* Returns the reason it did nothing, so a quiet failure can be told apart
     from having nothing to fetch. Never throws: this runs at launch and must not
     be able to take the app down with it. */
        var topic = bpTopic();
        if (!topic) return "no-topic";
        if (BPSHOT) return "already-have-one";
        var since = String(Math.max(1, Math.min(72, hours || 12))) + "h";
        var txt = "";
        try {
          var r = await fetch(
            "https://ntfy.sh/" + encodeURIComponent(topic) + "/json?poll=1&since=" + since,
            { cache: "no-store" },
          );
          if (!r.ok) return "http-" + r.status;
          txt = await r.text();
        } catch (e) {
          return "offline";
        }
        var cands = bpUrlsFromNtfy(txt);
        if (!cands.length) return "none-found";
        var seen = bpSeen();
        for (var i = 0; i < cands.length; i++) {
          var sid = bpSidOf(cands[i].url);
          if (sid && seen.indexOf(sid) >= 0) continue;
          /* bpIngest marks it seen itself, so a shot cannot be offered twice even
       if the caller forgets. */
          if (bpIngest(cands[i].url)) {
            try {
              showTab("log");
            } catch (e) {}
            try {
              setLogMode("after");
            } catch (e) {}
            return "ingested";
          }
        }
        return "all-seen";
      }
      function bpShotBanner() {''',
    'P22 ntfy poller with dedupe')

# P23. Google picks whichever account the browser considers current. On a phone
#      with two signed-in accounts that is a coin toss, and a wrong pick writes to
#      a different Drive. Remember which account connected and ask for it by name.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '''              GCLIENT = google.accounts.oauth2.initTokenClient({
                client_id: GOOGLE_CLIENT_ID,
                scope: GSCOPE,''',
    '''              GCLIENT = google.accounts.oauth2.initTokenClient({
                client_id: GOOGLE_CLIENT_ID,
                scope: GSCOPE,
                login_hint: gAccount(),''',
    'P23a hint the account at client init')

FEATURES_JS = must_replace(
    FEATURES_JS,
    '            GCLIENT.requestAccessToken({ prompt: "" });',
    '''            /* The hint is also passed per request, because the client is built once
         and the remembered account can be learned after that. */
            var _h = gAccount();
            GCLIENT.requestAccessToken(_h ? { prompt: "", login_hint: _h } : { prompt: "" });''',
    'P23b hint the account per request')

FEATURES_JS = must_replace(
    FEATURES_JS,
    '      function gConfigured() {',
    '''      function gAccount() {
        try {
          return String(localStorage.getItem("gaccount") || "").trim();
        } catch (e) {
          return "";
        }
      }
      async function gLearnAccount() {
        /* Learned, not asked for. drive.file does not grant an email address, so
     this reads the one Drive will admit to and quietly does nothing if it will
     not. A missing hint costs an account chooser; a WRONG hint would be worse,
     so it is only ever written from Drive's own answer. */
        if (gAccount()) return gAccount();
        try {
          var d = await gApi("https://www.googleapis.com/drive/v3/about?fields=user(emailAddress)");
          var e = d && d.user ? String(d.user.emailAddress || "").trim() : "";
          if (!e) return "";
          try {
            localStorage.setItem("gaccount", e);
          } catch (err) {}
          try {
            renderSheetStatus();
          } catch (err) {}
          return e;
        } catch (err) {
          return "";
        }
      }
      function gConfigured() {''',
    'P23c learn and remember the connected account')

# P24. Boot order. The tapped link is the more explicit intent so it wins; the
#      poller only runs when the URL had nothing, which is every normal launch
#      from the phone drawer. Delayed so it cannot compete with the first paint.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '      try {\n        bpHandoff();\n      } catch (e) {}',
    '      try {\n        bpHandoff();\n      } catch (e) {}\n'
    '      setTimeout(function () {\n'
    '        try {\n          bpPollNtfy(12);\n        } catch (e) {}\n'
    '      }, 900);',
    'P24a poll at launch when the URL had nothing')

FEATURES_JS = must_replace(
    FEATURES_JS,
    '      uiStart();\n      try {\n        pickerizeAll();\n      } catch (e) {}',
    '      uiStart();\n      try {\n        pickerizeAll();\n      } catch (e) {}\n'
    '      try {\n        loadNtfyTopic();\n      } catch (e) {}',
    'P24d populate the topic field at boot')

FEATURES_JS = must_replace(
    FEATURES_JS,
    '''                    GTOKEN = r.access_token;
                    GTOKEN_EXP = Date.now() + (r.expires_in || 3600) * 1000;
                    gSaveToken();''',
    '''                    GTOKEN = r.access_token;
                    GTOKEN_EXP = Date.now() + (r.expires_in || 3600) * 1000;
                    gSaveToken();
                    try {
                      gLearnAccount();
                    } catch (e) {}''',
    'P24b learn the account once a token works')

# P24c. The settings field needs a reader, a writer and a manual check, and the
#       status line has to say which account as well as which sheet, since the
#       whole point of the hint is that the wrong one is now possible to notice.
FEATURES_JS = must_replace(
    FEATURES_JS,
    '      function bpSeen() {',
    '''      function loadNtfyTopic() {
        var el = document.getElementById("ntfyTopic");
        if (el) el.value = bpTopic();
        renderNtfyStatus("");
      }
      function saveNtfyTopic() {
        var el = document.getElementById("ntfyTopic");
        if (!el) return;
        /* Accept a pasted ntfy URL as well as a bare topic. Typing the whole
     address is the obvious thing to do and silently storing it would make every
     poll 404. */
        var v = String(el.value || "").trim();
        v = v.replace(/^https?:\\/\\/[^/]+\\//i, "").replace(/[/?].*$/, "");
        el.value = v;
        try {
          localStorage.setItem("ntfyTopic", v);
        } catch (e) {}
        renderNtfyStatus(v ? "saved" : "");
      }
      function renderNtfyStatus(msg) {
        var el = document.getElementById("ntfyStatus");
        if (!el) return;
        el.textContent = msg || "";
      }
      async function checkShotsNow() {
        renderNtfyStatus("checking...");
        var r = "error";
        try {
          r = await bpPollNtfy(48);
        } catch (e) {}
        var say = {
          ingested: "shot loaded, see the Log tab",
          "no-topic": "set your ntfy topic first",
          "none-found": "no shots on that topic in the last 48h",
          "all-seen": "nothing new, every shot there is already logged",
          "already-have-one": "a shot is already loaded, save or clear it first",
          offline: "could not reach ntfy",
        };
        renderNtfyStatus(say[r] || r);
      }
      function bpSeen() {''',
    'P24c topic field, manual check and status')

ASSEMBLED = (HEAD + CSS + SHELL_OPEN + APPBAR_H + WRAP_DURA + TABHOME_O
             + INSTALL_H + HERO_H
             + home + SEP_LOG + logtab + SEP_BEANS + beanstab
             + SEP_GRIND + grindtab + SEP_INS + instab
             + TAIL_HTML + script + SHELL_JS + FEATURES_JS + TAIL)

must_ship(ASSEMBLED)

# ---------- webapp = prettified; firmware = compact ----------
# Prettier version is part of the build contract. 3.9.x formats inline on* event
# handlers; older prettier leaves them compact. A mismatch silently reformats the
# whole file, which changes every byte and every stamp for no real reason.
#
# The path is resolved, not assumed. The previous generator hardcoded the Linux
# sandbox path, so this file could only ever run in a sandbox, which is half the
# reason it was never kept anywhere durable. Every candidate below is PROVEN by
# running --version, not by checking that a file exists.
PRETTIER_EXPECT = '3.9.'

def _npm_root():
    cands = [[shutil.which('npm')], ['npm'], ['npm.cmd']]
    for argv in [c + ['root', '-g'] for c in cands if c[0]]:
        try:
            r = subprocess.run(argv, capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except OSError:
            pass
    return None

def _probe(argv):
    """Return the version string if argv is a working prettier, else None."""
    try:
        r = subprocess.run(argv + ['--version'], capture_output=True, text=True)
    except OSError:
        return None
    v = (r.stdout or '').strip()
    return v if r.returncode == 0 and v[:1].isdigit() else None

def find_prettier():
    cands, seen = [], set()
    def add(argv):
        if argv and tuple(argv) not in seen:
            seen.add(tuple(argv)); cands.append(list(argv))
    env = os.environ.get('PRETTIER')
    if env:
        add(env.split() if ' ' in env else [env])
    # node + the package entry point works identically on Windows and Linux and
    # sidesteps the .cmd shim question entirely, so it is tried early.
    root = _npm_root()
    node = shutil.which('node') or 'node'
    if root:
        for tail in (('prettier', 'bin', 'prettier.cjs'), ('prettier', 'bin-prettier.js')):
            p = os.path.join(root, *tail)
            if os.path.exists(p):
                add([node, p])
    add([shutil.which('prettier')] if shutil.which('prettier') else None)
    add(['/home/claude/.npm-global/bin/prettier'])
    found = []
    for argv in cands:
        v = _probe(argv)
        if v:
            found.append((argv, v))
            if v.startswith(PRETTIER_EXPECT):
                return argv, v
    if found:
        argv, v = found[0]
        raise SystemExit(
            '\n  BUILD ABORTED: prettier %s found, this build needs %sx.\n'
            '  A different prettier reformats every byte and moves the stamp.\n'
            '    npm install -g prettier@3.9.6\n' % (v, PRETTIER_EXPECT))
    raise SystemExit(
        '\n  BUILD ABORTED: no working prettier found.\n'
        '    npm install -g prettier@3.9.6\n'
        '  Or point at one directly:\n'
        '    Linux/macOS   PRETTIER=/path/to/prettier python3 build_v5.py\n'
        '    PowerShell    $env:PRETTIER = C:\\path\\to\\prettier.cmd ; python build_v5.py\n')

PRETTIER, _pv = find_prettier()
print('prettier:', _pv, 'via', ' '.join(PRETTIER))

# Every write below pins newline='' on purpose. Python text mode translates
# '\n' to os.linesep, so on Windows this build would emit CRLF while the stamp
# is a sha1 of the LF string still in memory. The stamp would MATCH a Linux
# build byte for byte while the file on disk did not, which defeats the one
# check the whole verification ritual rests on.
with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8', newline='') as f:
    f.write(ASSEMBLED); tmp = f.name
# encoding='utf-8' is not optional. text=True alone decodes with the LOCALE
# codec, which is cp1252 on a Spanish Windows install, and the app carries UTF-8
# characters. The reader thread dies mid-decode, stdout comes back None, and the
# build then fails somewhere unrelated with a TypeError.
pretty = subprocess.run(PRETTIER + ['--parser', 'html', '--print-width', '100', '--tab-width', '2', tmp],
                        capture_output=True, text=True, encoding='utf-8')
os.unlink(tmp)
if pretty.returncode != 0:
    print('PRETTIER FAILED:\n', (pretty.stderr or '')[:800]); raise SystemExit(1)
webapp = pretty.stdout
if not webapp:
    raise SystemExit('BUILD ABORTED: prettier returned success but produced no output.')
if '__BUILD_STAMP__' not in webapp:
    raise SystemExit('BUILD ABORTED: __BUILD_STAMP__ vanished before stamping')
# Date plus a hash of the actual bytes. The sha6 suffix is deterministic for a
# given source, so compare suffixes (not full stamps) when checking a rebuild.
_stamp = datetime.datetime.now().strftime('%Y-%m-%d-%H%M') + '-' + hashlib.sha1(webapp.encode()).hexdigest()[:6]
webapp = webapp.replace('__BUILD_STAMP__', _stamp)
print('build stamp:', _stamp)
open(OUT, 'w', encoding='utf-8', newline='').write(webapp)

def cstring(s):
    s = s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '')   # compact for flash
    chunks = [s[i:i+3800] for i in range(0, len(s), 3800)]
    return 'static const char PANEL_HTML[] PROGMEM =\n' + '\n'.join('  "%s"' % c for c in chunks) + ';\n'
open(PANEL, 'w', encoding='utf-8', newline='').write(cstring(ASSEMBLED))

resid = [h for h in re.findall(r'#[0-9a-fA-F]{3,6}\b', body + script) if h.lower() != '#fff']
print('residual raw hex in src body+script (should be 0):', len(resid), resid[:10])
print('webapp bytes:', len(webapp), '| firmware bytes:', len(open(PANEL, encoding='utf-8', newline='').read()))

# ---------------------------------------------------------------------------
# RECONSTRUCTION NOTES (2026-07-24)
#
# Rebuilt from the live index.html because the previous generator was lost.
# What is identical to the original: the two-file split, the src_v5.html
# <body>/<script> contract, the tab cut, the theme token table, the prettier
# invocation, the post-prettier stamping, panel_v5.h emission, must_replace
# and must_ship.
#
# What is NOT carried over: the 27 historical must_replace migrations. Their
# "old" text no longer exists anywhere, because their result is what the live
# file already contains. Re-running them would abort the build. The machinery
# is kept for new edits; the exhausted patch log is not.
# ---------------------------------------------------------------------------

