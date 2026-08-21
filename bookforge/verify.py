# -*- coding: utf-8 -*-
"""Self-audit of a built book.

Keeps every check the reference pipeline had, with its book-specific literals
moved into meta.yaml, and adds the ones that would have caught the defects found
in the existing PDFs -- five of the seven shipped with Linux fallback fonts
substituted in, which nothing was looking for.

Returns [(severity, message)] where severity is "fail" or "warn".
"""
import os
import re

# Embedded fallback faces mean the intended webfonts never loaded at render time.
FALLBACK_RE = re.compile(
    r"Liberation|DejaVu|Nimbus|TimesNewRoman|ArialMT|Courier(?!Prime)", re.I)


def _norm(text):
    return re.sub(r"\s+", " ", text)


def audit(cfg, pdf_path, html_text, baseline=None, quiet=False):
    import fitz

    out = []
    v = cfg.data.get("verify", {})
    doc = fitz.open(pdf_path)

    # -- fonts ----------------------------------------------------------
    fonts = set()
    for page in doc:
        for f in page.get_fonts(full=True):
            fonts.add((f[3], f[1]))
    if not quiet:
        print("  fonts  %d face(s):" % len(fonts))
        for bf, typ in sorted(fonts):
            print("         %-44s %s" % (bf, typ))

    if [f for f in fonts if f[0].startswith("Helv")]:
        out.append(("fail", "a base-14 font leaked in (not embedded)"))
    t3 = [f for f in fonts if "T3" in f[0] or f[1] == "n/a" or not f[0]]
    if t3:
        out.append(("fail", "Type 3 / unembedded faces present: %s" % t3))
    # A book that declares webfonts and still embeds Liberation/DejaVu did not
    # load them -- that is a defect. A book that declares no webfonts at all is
    # using a system stack on purpose, and Times/Arial/Liberation is just that
    # stack resolving on whichever machine rendered it.
    bad = sorted(f[0] for f in fonts if FALLBACK_RE.search(f[0] or ""))
    # A book may exempt named faces it knowingly falls back to -- far better
    # than switching the whole check off, which is how the original defect went
    # unnoticed for five books.
    allowed = v.get("allow_fonts") or []
    if allowed:
        bad = [f for f in bad if not any(a.lower() in f.lower() for a in allowed)]
    if bad:
        if v.get("allow_system_fonts"):
            out.append(("warn",
                        "system-font stack resolved to: %s -- rendering is "
                        "machine-dependent, but this book declares no webfonts"
                        % ", ".join(s.split("+")[-1] for s in bad)))
        else:
            out.append(("fail",
                        "fallback fonts embedded (the intended webfonts did not load): %s"
                        % ", ".join(bad)))

    # -- text probes ----------------------------------------------------
    front = _norm("".join(doc[i].get_text() for i in range(min(3, doc.page_count))))
    for probe in v.get("cover_probes") or []:
        if probe not in front:
            out.append(("fail", "cover/front text missing: %r" % probe))

    body = _norm("".join(p.get_text() for p in doc))
    for probe in v.get("body_probes") or []:
        if probe.lower() not in body.lower():
            out.append(("fail", "body text missing: %r" % probe))
    for probe in v.get("matter_probes") or []:
        if probe.lower() not in body.lower():
            out.append(("fail", "front/back matter missing: %r" % probe))

    # -- template hygiene ------------------------------------------------
    from .html import unfilled
    left = unfilled(html_text)
    if left:
        out.append(("fail", "unfilled template slot(s): %s" % ", ".join(left)))
    if "{{" in body:
        out.append(("fail", "template placeholder leaked into rendered output"))

    # -- QR round-trip ---------------------------------------------------
    from . import qr as qrmod
    theme_qr = cfg.theme.get("qr", {})
    for spec in cfg.get("qr") or []:
        svg = qrmod.make(spec["target"],
                         dark=theme_qr.get("dark", "#161A21"),
                         error=theme_qr.get("error", "h"),
                         ns=cfg.slug)
        paths = re.findall(r'\sd="([^"]{40,})"', svg)
        if paths and not any(p in html_text for p in paths):
            out.append(("fail", "QR for %s is stale or altered in the output"
                        % spec["target"]))

    # -- images ----------------------------------------------------------
    images = sum(len(p.get_images()) for p in doc)
    if not quiet:
        print("  images %d embedded" % images)
    if images < int(v.get("min_images", 1)):
        out.append(("fail", "expected >= %s image(s), found %d"
                    % (v.get("min_images", 1), images)))

    # -- pagination ------------------------------------------------------
    expect = v.get("expect_pages")
    tol = int(v.get("page_tolerance", 2))
    if expect is not None:
        delta = doc.page_count - int(expect)
        if abs(delta) > tol:
            out.append(("warn", "page count %d, expected %s (+/-%d)"
                        % (doc.page_count, expect, tol)))

    # -- page geometry ---------------------------------------------------
    pw, ph = cfg.page_points
    odd = {(round(p.rect.width), round(p.rect.height)) for p in doc}
    if odd - {(round(pw), round(ph))}:
        out.append(("warn", "page size %s does not match page.size=%s"
                    % (sorted(odd), cfg.get("page.size"))))

    if not quiet:
        print("  text   %d chars across %d pages" % (len(body), doc.page_count))
    doc.close()

    # -- body-text diff vs baseline --------------------------------------
    # This is what makes "front/back matter only" checkable. Adding matter may
    # only INSERT words; if any baseline word went missing, the injection landed
    # somewhere it should not have and the interior changed.
    if baseline and os.path.exists(baseline):
        import difflib
        import io
        # Compared as a whitespace-free character stream, for two reasons:
        # repagination renumbers every folio, and it re-breaks words across
        # lines, so PDF extraction yields "re- route" one build and "re-route"
        # the next. Neither is a content change.
        #
        # Adding matter may only INSERT, so the baseline must survive as a
        # subsequence of the new text. A greedy walk decides that in one pass.
        def stream(text):
            return re.sub(r"[\s ]+", "", re.sub(r"\b\d{1,4}\b", "", text))

        with io.open(baseline, encoding="utf-8") as fh:
            before = stream(fh.read())
        after = stream(body)

        i = 0
        for ch in after:
            if i < len(before) and ch == before[i]:
                i += 1
        if i < len(before):
            ctx = before[max(0, i - 60):i + 60]
            msg = ("baseline diverges after %d/%d chars near ...%s..."
                   % (i, len(before), ctx))
            # Some shipped PDFs predate their manuscript, so a divergence is
            # expected and already understood. Saying so explicitly keeps the
            # check meaningful for every other book.
            stale = v.get("baseline_stale")
            if stale:
                out.append(("warn", "%s -- known: %s" % (msg, stale)))
            else:
                out.append(("fail", "interior changed: %s" % msg))
        elif not quiet:
            print("  diff   +%d chars vs baseline, 0 lost"
                  % (len(after) - len(before)))
    return out
