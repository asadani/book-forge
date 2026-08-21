# -*- coding: utf-8 -*-
"""bf -- the book-forge command line."""
import argparse
import os
import sys

from . import __version__
from .errors import ForgeError

DEFAULT_META = "meta.yaml"


def _load(args):
    from . import config
    return config.load(os.path.abspath(args.meta))


def _cover_page(cfg, quiet=False):
    """Render the full-bleed cover page into the book's build cache."""
    from . import cover
    from .paths import cache_dir
    dst = os.path.join(cache_dir(cfg.root), "cover-page.jpg")
    return cover.render(
        cfg.cover_art, dst,
        page=cfg.get("page.size", "A4"),
        dpi=int(cfg.get("cover.dpi", 300)),
        fit=cfg.get("cover.fit", "crop"),
        trim_top_share=float(cfg.get("cover.trim_top_share", 0.47)),
        matte=cfg.get("cover.matte"),
        quiet=quiet)


def cmd_assets(args):
    cfg = _load(args)
    did = False
    if args.fonts:
        from . import fonts
        fonts.cut()
        did = True
    if args.cover:
        _cover_page(cfg)
        did = True
    if not did:
        _cover_page(cfg)
    return 0


def cmd_build(args):
    from . import fonts, html, pdf, qr as qrmod, verify as verifymod

    cfg = _load(args)
    print("building %s" % cfg.slug)

    # 1. HTML
    cover_jpg = _cover_page(cfg)
    uri, nbytes = html.data_uri(cover_jpg, "image/jpeg")
    print("  cover  %d KB embedded" % (nbytes // 1024))

    slots = {"COVER_PAGE_URI": uri, "FONT_FACES": fonts.face_css(cfg.faces)}
    theme_qr = cfg.theme.get("qr", {})
    specs = cfg.get("qr") or []
    for spec in specs:
        slots[spec["slot"]] = qrmod.make(
            spec["target"],
            dark=theme_qr.get("dark", "#161A21"),
            error=theme_qr.get("error", "h"),
            ns=cfg.slug,
            label=spec.get("label"))
    if specs:
        print("  qr     %d code(s) inlined as svg" % len(specs))

    text = html.fill(html.read(cfg.template), slots, required=["COVER_PAGE_URI"])
    html.write(cfg.html_out, text)
    print("  html   %s, %.2f MB"
          % (os.path.basename(cfg.html_out), len(text.encode("utf-8")) / 1048576.0))
    if args.stage == "html":
        return 0

    # 2/3. PDF + folios
    raw = pdf.render(cfg.html_out,
                     chrome=args.chrome,
                     budget_ms=int(cfg.get("pdf.virtual_time_budget_ms", 30000)),
                     timeout_s=int(cfg.get("pdf.timeout_s", 300)))
    if args.no_pdf or args.stage == "pdf":
        print("  (stopping before stamp; raw at %s)" % raw)
        return 0
    written, _ = pdf.stamp(raw, cfg.pdf_out, cfg.get("folio", {}))
    if args.stage == "stamp":
        return 0

    # 4. verify
    issues = verifymod.audit(cfg, written, text, baseline=args.baseline)
    return _report(issues, cfg, written, strict=args.strict)


def _qr_slots(cfg):
    """target -> "{{SLOT}}". The manuscript keeps the slot tokens; `bf build`
    fills them with real SVG, so book.html.in stays readable."""
    return dict((s["target"], "{{%s}}" % s["slot"]) for s in (cfg.get("qr") or []))


REGIONS = [
    ("FRONT-MATTER", "front", "front_matter"),
    ("ABOUT", "about", "about_author"),
]


def cmd_inject(args):
    from . import html, inject, render

    cfg = _load(args)
    text = html.read(cfg.template)
    original = text
    slots = _qr_slots(cfg)

    problems = inject.integrity(text, [r[0] for r in REGIONS])
    if problems:
        for p in problems:
            print("  FAIL  %s" % p)
        return 1

    results = []
    for region, key, fn in REGIONS:
        body = getattr(render, fn)(cfg, slots)
        text, status = inject.apply(
            text, region, body,
            anchor_before=cfg.get("matter.%s.anchor_before" % key),
            anchor_after=cfg.get("matter.%s.anchor_after" % key))
        results.append((region, status))

    css = render.matter_css()
    if css and cfg.get("matter.css", cfg.get("matter.mode") == "flow"):
        anchor = cfg.get("matter.css_anchor", "</style>")
        text, status = inject.apply(text, "MATTER-CSS", css, anchor_before=anchor)
        results.append(("MATTER-CSS", status))

    changed = text != original
    for region, status in results:
        print("  %-13s %s" % (region, status))

    if args.check:
        if changed:
            print("\nout of date: `bf inject` would rewrite %s"
                  % os.path.basename(cfg.template))
            return 1
        print("\nup to date")
        return 0

    if changed:
        html.write(cfg.template, text)
        print("\nwrote %s" % os.path.basename(cfg.template))
    else:
        print("\nno change")
    return 0


def cmd_verify(args):
    from . import html, verify as verifymod
    cfg = _load(args)
    if not os.path.exists(cfg.pdf_out):
        raise ForgeError("no built PDF at %s -- run `bf build` first" % cfg.pdf_out)
    text = html.read(cfg.html_out) if os.path.exists(cfg.html_out) else ""
    issues = verifymod.audit(cfg, cfg.pdf_out, text, baseline=args.baseline)
    return _report(issues, cfg, cfg.pdf_out, strict=args.strict)


def _report(issues, cfg, written, strict=False):
    fails = [m for sev, m in issues if sev == "fail"]
    warns = [m for sev, m in issues if sev == "warn"]
    print("")
    for m in fails:
        print("  FAIL  %s" % m)
    for m in warns:
        print("  warn  %s" % m)
    if fails or (warns and strict):
        print("\n%s: %d failure(s), %d warning(s)" % (cfg.slug, len(fails), len(warns)))
        return 1
    print("OK - %s and %s built and verified"
          % (os.path.basename(cfg.html_out), os.path.basename(written)))
    if warns:
        print("     (%d warning(s) above)" % len(warns))
    return 0


def cmd_doctor(args):
    from .paths import find_chrome, forge_asset
    print("book-forge %s" % __version__)
    ok = True

    try:
        print("  chrome    %s" % find_chrome(args.chrome))
    except ForgeError as e:
        print("  chrome    MISSING - %s" % e)
        ok = False

    print("  python    %s" % sys.version.split()[0])
    for mod in ["yaml", "jinja2", "segno", "fitz", "fontTools", "PIL"]:
        try:
            __import__(mod)
            print("  dep %-9s ok" % mod)
        except ImportError:
            print("  dep %-9s MISSING" % mod)
            ok = False

    fdir = forge_asset("fonts")
    faces = [f for f in os.listdir(fdir) if f.endswith(".woff2")] if os.path.isdir(fdir) else []
    print("  fonts     %d cut face(s)" % len(faces))
    if not faces:
        ok = False

    if os.path.exists(args.meta):
        cfg = _load(args)
        print("  book      %s (theme=%s, mode=%s, fit=%s)"
              % (cfg.slug, cfg.data["theme"], cfg.get("matter.mode"), cfg.get("cover.fit")))
        _git_checks(cfg.root)
    return 0 if ok else 1


def _git_checks(root):
    import subprocess

    def git(*a):
        try:
            r = subprocess.run(["git", "-C", root] + list(a),
                               capture_output=True, text=True, timeout=15)
            return r.stdout.strip() if r.returncode == 0 else None
        except Exception:
            return None

    if git("rev-parse", "--git-dir") is None:
        print("  git       not a repository")
        return
    url = git("remote", "get-url", "origin")
    print("  git remote %s" % (url or "NONE"))
    if url and url.startswith("https://github.com"):
        print("             note: https remote; the other book repos use ssh")
    ssh = git("config", "--local", "core.sshCommand")
    if not ssh:
        print("             note: core.sshCommand not pinned")


def build_parser():
    p = argparse.ArgumentParser(prog="bf", description="book-forge")
    p.add_argument("--version", action="version", version="book-forge " + __version__)
    sub = p.add_subparsers(dest="cmd")

    def common(sp):
        sp.add_argument("--meta", default=DEFAULT_META, help="path to meta.yaml")
        sp.add_argument("--chrome", default=None, help="path to a Chrome/Edge binary")
        sp.add_argument("--baseline", default=None, help="baseline text.txt to diff against")
        sp.add_argument("--strict", action="store_true", help="treat warnings as failures")
        return sp

    a = common(sub.add_parser("assets", help="regenerate cover page / fonts"))
    a.add_argument("--fonts", action="store_true")
    a.add_argument("--cover", action="store_true")
    a.set_defaults(func=cmd_assets)

    b = common(sub.add_parser("build", help="html -> pdf -> folios -> verify"))
    b.add_argument("--stage", choices=["html", "pdf", "stamp", "verify"], default=None)
    b.add_argument("--no-pdf", action="store_true")
    b.set_defaults(func=cmd_build)

    i = common(sub.add_parser("inject", help="render the matter partials into the manuscript"))
    i.add_argument("--check", action="store_true",
                   help="report whether the manuscript is current; write nothing")
    i.set_defaults(func=cmd_inject)

    common(sub.add_parser("verify", help="audit the built PDF")).set_defaults(func=cmd_verify)
    common(sub.add_parser("doctor", help="environment and config check")).set_defaults(func=cmd_doctor)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not getattr(args, "func", None):
        build_parser().print_help()
        return 2
    try:
        return args.func(args)
    except ForgeError as e:
        print("\nERROR: %s" % e, file=sys.stderr)
        return 1
