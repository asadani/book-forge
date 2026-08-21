# book-forge

A shared build pipeline for the books. HTML → headless Chrome → folio-stamped,
self-audited PDF.

This is the pipeline that produced *Speed Is the Moat*, lifted out of that repo
and generalised. Previously it was git-ignored — the `.gitignore` said *"Build
tooling lives locally; this is a reading repo, not a code repo"* — so it shipped
nowhere and existed only on one laptop. Books stayed inconsistent because there
was nothing to be consistent with.

## What a book looks like

```
my-book/
  meta.yaml            # everything that used to be a hardcoded constant
  book.html.in         # the prose, hand-authored HTML
  assets/cover.png
  tools/book-forge     # this repo, pinned (submodule)
  book-forge.lock      # the pin, in a form that survives zip export
```

Build it:

```
bf build
```

## Commands

| | |
|---|---|
| `bf build` | html → pdf → folios → verify. `--stage html\|pdf\|stamp` to stop early. |
| `bf verify` | audit an already-built PDF |
| `bf assets --cover --fonts` | regenerate the cover page; re-cut static font faces |
| `bf doctor` | Chrome, deps, fonts, and git-config check |

All take `--meta PATH` (default `./meta.yaml`), `--chrome PATH`, `--baseline
PATH`, `--strict`.

## Why the fonts are committed

Chrome degrades **variable** fonts to Type 3 when printing, which is unusable
for print. So the variable masters are flattened to static `.woff2` once and
those are embedded. The cut faces live in `fonts/` and are committed, so an
ordinary build never touches the network; the masters (`_var_*.ttf`) are ignored
and refetched on demand by `bf assets --fonts`.

## What the verifier checks

Beyond "did it render": no Type 3 or unembedded faces, **no fallback fonts**
(`Liberation*`, `DejaVu*`, `Nimbus*`, `TimesNewRoman`, `ArialMT`), no unfilled
`{{SLOT}}` tokens, cover/body/matter text probes, QR round-trip against
`meta.yaml`, image count, page-count drift, and page geometry.

The fallback-font gate exists for a reason: an audit of the seven published
books found **five** had Linux fallback faces substituted in, because nothing
was looking.

## Requirements

Python 3.9+, Chrome or Edge, and `pyyaml jinja2 segno pillow fonttools pymupdf`.
`bf doctor` will tell you what is missing.
