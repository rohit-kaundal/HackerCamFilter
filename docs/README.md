# Hacker Cam website

A Jekyll site, served by GitHub Pages from this `docs/` folder: https://rohit-kaundal.github.io/HackerCamFilter/

## How it's put together

| File | What it is |
|---|---|
| `_config.yml` | Site title, URL and `baseurl` (`/HackerCamFilter`), the GitHub link, and files to leave out of the build |
| `_layouts/default.html` | The theme: `<head>`, nav and footer around every page |
| `_layouts/page.html` | Text pages written in Markdown (title, eyebrow, lede, then the content) |
| `index.html` | The landing page: front matter plus its sections |
| `setup.md`, `privacy.md` | Setup guide and privacy page |
| `404.html` | "Signal lost" page |
| `styles.css`, `main.js`, `assets/` | Shared styles (Markdown styles are under `.prose`), demo and analytics script, images |

To add a page, create `something.md` with `layout: page`, a `title` and a `permalink`, and link it from the nav or footer in `_layouts/default.html`. Always build links with `relative_url`, for example `{{ '/setup/' | relative_url }}`, so they work under `/HackerCamFilter/`.

**Turn it on:** repo Settings → Pages → Build and deployment → *Deploy from a branch* → `main`, `/docs`.

**Preview locally:** `jekyll serve -s docs`, then open http://127.0.0.1:4000/HackerCamFilter/. GitHub Pages builds it for you, so you don't need Jekyll installed to publish.

## Before publishing

1. **Links:** set `githubUrl` in `CONFIG` at the top of `main.js`. Download buttons then point to the latest GitHub release (or set `downloadUrl`), and the GitHub links appear. While both are empty, download buttons scroll to the download section.
2. **Analytics (optional):** set `posthogKey` (and `posthogHost` for an EU project). The page then loads PostHog in cookieless mode: no cookies or storage, so no cookie banner. **Turn on cookieless tracking in the PostHog project settings too**, or PostHog ignores these events. Besides automatic page views and clicks, the page sends `download_clicked`, `github_clicked` and `demo_name_typed` (never the name itself). Leave the key empty for no analytics.
3. **Custom domain:** if you add one, set `url` to it and `baseurl` to `""` in `_config.yml`. The social preview image and canonical links use `url`.

## Structure

The page is one story built around a single problem statement:

| Section | Job |
|---|---|
| Hero | Names the problem ("one of nine identical rectangles") and shows the fix live. Visitors can type their name into the demo. |
| The problem | Makes it concrete: a grid of identical call tiles with you standing out. |
| What it costs | Three consequences: wasted openings, invisible expertise, forgettable meetings. |
| The fix | What Hacker Cam is, with the real intro sequence. |
| Effects | All eight effects. |
| Where it lands | Use cases. |
| How it works | Three setup steps, plus the menu. |
| Privacy | Everything runs locally. |
| Offer | Price and what's included. |
| FAQ | Answers objections. |
| Close | Restates the problem, then the call to action. |

There are no testimonials, user counts or statistics on purpose. Add real ones as you collect them.

## Images

`assets/*.jpg` are real frames rendered by the app's own effect code. Regenerate them after changing effects:

```bash
.venv/bin/python docs/scripts/render_assets.py
```

Effects that need a person (entrance, biometric scan, hologram, filter) are drawn as CSS illustrations with a generic silhouette rather than stock photos. Swap in screen recordings of yourself when you have them.
