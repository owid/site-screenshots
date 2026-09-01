---
name: site-screenshot-false-positives
description: Diagnose and fix false positives in the site-screenshots diff that owidbot reports on owid-grapher PRs. Use when a PR reports "N pages changed" or a failed screenshot run and the change looks unrelated to the branch, when asked whether screenshot diffs are real, or when adding a normalisation to config.yaml. Holds the diagnostic method, the catalogue of classes already fixed, and the ones still open.
---

# Fixing site-screenshots false positives

A false positive here is a screenshot diff, or a failed run, caused by the harness or by the
difference between production and staging rather than by the branch. They are expensive out of
proportion to their size: a reviewer opens a 94-pixel diff, finds nothing, and trusts the next
one less.

Most of what follows is method. The catalogue is the part that grows — append to it when you
resolve a class, including the ones you decide not to fix and why.

## How the comparison actually works

Get this wrong and you will chase diffs that aren't there.

- Screenshots are taken by `shot-scraper` against the URLs in `config.yaml`, driven by
  `ops/templates/lxc-manager/site-screenshots` on `lxc-manager-1`. Master runs against
  **production**; a branch runs against **its staging server**.
- The reported diff is `git diff origin/master...HEAD` — three dots, so **against the merge
  base**, not master's head. GitHub's `/compare/<branch>` link shows the same thing. Master's
  later "Update reference screenshots" commits therefore do not count as branch changes, and
  neither should they in your own analysis.
- A branch's screenshot branch keeps the `config.yaml` it was created with. **A fix reaches a
  given owid-grapher branch only when that branch's screenshot branch is next created.** This
  is why a normalisation can look like it did nothing.
- The reference images only change when master runs. Merging a normalisation does not update
  them; the next master run does, and that run rewrites whatever the normalisation touched —
  one-time churn to expect and to say out loud.
- owidbot reports `✅` / `⚠️ N pages changed` / `❌ the run failed`. A failed run leaves the
  compare link showing the *previous* run's diff.
- The step soft-fails on exit 1, so a failure is only visible in owidbot's comment and the
  Buildkite log.

## Method

**1. Diff against the merge base yourself.** `references/mergebase-diff.py` does this: for each
branch it resolves the merge base, downloads both sides of every changed file, and reports pixel
counts, max delta, and the contiguous row bands. Row bands are what let you find the region
without eyeballing a 7000-pixel-tall image.

**2. Look for the same diff on unrelated branches.** This is the single best discriminator and it
has settled almost every case here. A byte-identical pixel count on two branches that touch
different code is the harness, full stop — 66,596 px on four branches, 55,736 px on four, 22.1%
on six. Check this before forming any theory.

**3. Crop and look.** A number tells you a region changed; only the picture tells you what. Crop
both sides at the band with a little padding and read them side by side. Deltas of 1–3/255 mean
resampling or decode; a max delta of 255 with one side at mean 255.0 means something is missing
entirely; text that differs by a few glyphs is usually a date or a count.

**4. Measure the mechanism before writing the fix.** The theory that felt obvious has been wrong
more than once. Instrument the shipped code and get a number: does the thing you blame actually
happen? Two examples worth remembering — "images arrive after the decode pass" (measured: never,
even at 250 kbps) and "the screenshot step races the preview deploy" (measured: passing runs
overlap it exactly as much as failing ones).

**5. A correlation needs a control group.** Every screenshot run starts seconds after the bake,
so "every failure happened during X" is worthless if every run happens during X. Find the runs
that had the condition and passed.

**6. Verify with a 2×2, not a before/after.** Run the old code twice and the new code twice. Old
vs old and new vs new give you the run-to-run noise floor; only then does old vs new mean
anything. This caught a fix that changed 55,736 pixels for a reason unrelated to its purpose.

**7. Where possible, compare against ground truth, not just against stability.** A deterministic
screenshot can still be deterministically wrong. For the capture-time classes, the ground truth
is a capture taken with the viewport never resized (scroll to the region, then a clipped viewport
screenshot) — that is how the image-source fix was shown to be more faithful and not merely more
stable.

**8. Test the shipped source, not a copy.** Extract the function out of `config.yaml` with
`yaml.safe_load(...)[0]["javascript"]` and evaluate it under Playwright. A copied snippet drifts
from what runs in CI, and every one of these fixes lives in that one string.

**9. Say when you could not reproduce it.** A warm laptop makes most of these deterministic. If
the symptom only appears in CI, the honest claim is "the mechanism is gone", not "the symptom is
fixed".

## Constraints on config.yaml

- `run.sh` pipes the file through `envsubst`, so **no `${...}` in the JavaScript** — not even in
  a template literal with a plain identifier. Use string concatenation.
- All seven shots share one YAML anchor (`&default_javascript`). Editing it changes every page.
- A throw inside the `new Promise(async ...)` executor does **not** reject the promise; it leaves
  it unsettled until the 300-second page timeout, so every page fails. Anything that can throw
  needs to be either guarded or avoided. This is why the code uses `getClientRects()` and
  computed `visibility` rather than `Element.checkVisibility()`, whose option names were renamed
  between the pinned Chromium 113 and current ones.
- Prefer failing the shot over photographing a state you know is wrong; the diagnostics on the
  failure path are cheaper to read than a misleading image.
- Scope normalisations by selector, not by matching text anywhere in the page. "Today" and
  "Yesterday" occur in article prose, and rewriting those hides real changes.
- Avoid tunable thresholds. Every fix here keys off something the page itself asserts.

## Catalogue

### Fixed

| Class | Symptom | Fix |
|---|---|---|
| Host-dependent content | Staging hostnames, `localhost`, archive URLs and the "Retrieved &lt;date&gt;" citation stamp rewrap every block below them | Text-walker rewrites to a canonical origin, PR #6 |
| Copy-to-clipboard buttons | Need a secure context, so production has them and plain-HTTP staging never does; they share a flex row with the code they copy | Removed before the shot, PR #6 |
| Archived-version link | Only production has one, and it takes a line in the header | Removed, PR #6 |
| Charts redrawing during capture | The full-page screenshot collapses the viewport to 1×1 for ~175 ms; mobile CSS collapses the containers, grapher re-measures and redraws small, and its 400 ms debounce lands after the pixels are read | Pin container widths inline and freeze `window.innerWidth`/`innerHeight`, PR #7 |
| HTTP error pages | A staging server down for a minute produced six nginx 502 images committed as that branch's screenshots | `--fail` in `run.sh`, PR #8 |
| CSS motion | The cookie banner fades in over the last rows, so two runs catch it at different opacities — 2,705 px at 10/255 | Freeze all transitions and animations, PR #9 |
| Charts still loading | A spinner or a half-width chart shifts everything below it | Wait for quiet, then fail rather than shoot, PR #9; budget raised to 180 s in PR #10 |
| Browser-computed dates | The homepage kicker ("7 DAYS AGO") and a data insight's dateline ("Today"/"Yesterday") are rendered from `dayjs()`, so they record when the shot was taken. The `--is-today` class also turns the dateline vermillion | Canonicalise both, and drop the highlight class, PR #11 |
| Blank charts | A grapher that mounted but never announced itself has an empty `.GrapherComponent`, a zero loading count and no spinner, so the page reads as finished and is photographed with a white box — 68,959 px on one branch, 23.6% on another | Settle on "every visible placeholder holds a non-empty chart", PR #12 |
| Homepage editorial content | Production and staging serve different featured articles, because staging is baked from a DB snapshot taken when its container was created. The list is offset by one and the page shifts — 22.1%, six branches at once. Not normalisable: there is no value to agree on | Remove the featured-work, announcement and data-insight *items*, PR #13 |
| Image source flipping | 58 of 66 images on `/life-expectancy` are a `<picture>` whose `<source sizes="350px">` beats an `<img>` carrying a `w=1200`–`w=3542` fallback. At the capture's 1×1 viewport the source stops winning and the browser falls back, so the same picture is drawn from a different file — 66,596 px at 1–3/255, four branches | Pin `img.src = img.currentSrc` and drop the candidates, for loaded images only, PR #14 |

### Open

- **Lazy thumbnails that are never requested.** `/energy`'s reference is missing two chart
  thumbnails the branch runs have, rendering their alt text instead — 21,250 px, three branches.
  Different mechanism from the decode band: these were never requested, not requested late (40 of
  66 images on `/life-expectancy` never load at all, ~108 per topic page on `/energy`), so no wait
  reaches them. Forcing them is what the decode comment says hangs the shot. Left alone.

- **A chart whose config fetch fails spins forever.** Build 33174: eight
  `HTTP 500`/`502` responses for `/grapher/<slug>.config.json` from the branch's own staging
  server, and `no page error(s)` — grapher swallowed all eight and left all eight graphers
  loading. This is an owid-grapher bug and should be filed: a failed config fetch should not
  leave a grapher in a permanent loading state.

- **A chart that requests nothing at all.** Build 33178: the Key Charts carousel on `/energy`
  (`708x575 at y=6559`) drawn nothing, with no failed request, nothing in flight and no page
  error. Not a network problem — the client decided not to load. `GrapherWithFallback` logs a
  `console.error` when handed neither a slug nor a configUrl, which the diagnostics do not yet
  capture; adding `console.error` to them is the cheapest next step.

### Disproved, so don't re-derive it

- **Machine contention during the build window.** The screenshot step, the Cloudflare preview
  deploy and the BDD tests all hang off the bake and start within two seconds of each other, so
  every failure is inside that window — and so is every success. Build 33112 ran entirely inside
  the preview deploy and passed in 2 minutes; 33121 and 33124 are the same branch 50 minutes
  apart, same overlap, opposite outcomes. `lxc-manager-1` has 100 cores. ops#645, closed.

- **Waiting longer for images.** Measured at the decode pass and at the capture, unthrottled and
  at ~250 kbps with 300 ms RTT: 26 of 66 complete, both times, every time. The chart settle wait
  already outlasts every image fetch.

- **Retrying a page.** On build 33124 the charts were still empty 108 seconds after every other
  step on the box had finished. Stuck, not queued — another attempt has nothing to gain.

## Where the code lives

| What | Where |
|---|---|
| The shot: URLs, the settle loop, all normalisations | `config.yaml` (one shared anchor) |
| `shot-scraper multi --fail` | `run.sh` |
| Runner: checkout, run, commit, push, report to owidbot | `ops/templates/lxc-manager/site-screenshots` |
| Pipeline step, concurrency group, soft-fail | `ops/.buildkite/grapher/automated_staging_environment.yml` |
| The loading count the settle loop reads | owid-grapher `site/runGrapherLoadingTracker.ts` (`window._OWID_GRAPHERS_LOADING`) |
| Chart mounting and the fallback | owid-grapher `site/GrapherWithFallback.tsx`, `site/blocks/RelatedCharts.tsx` |
| Chart data fetching and its retries | owid-grapher `packages/@ourworldindata/grapher/src/core/loadVariable.ts`, `utils/src/Util.ts` (`fetchWithRetry`, 5 attempts, ~8 s) |
