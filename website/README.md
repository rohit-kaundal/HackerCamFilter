# Hacker Cam website

A static landing page: no build step, no frameworks, no external fonts. Analytics (PostHog, cookieless) load only if you add a key. Open `index.html` in a browser, or host the folder anywhere (GitHub Pages, Netlify, Cloudflare Pages, S3).

## Before publishing

1. **Links:** set `githubUrl` in `CONFIG` at the top of `main.js`. Download buttons then point to the latest GitHub release (or set `downloadUrl`), and the GitHub links appear. While both are empty, download buttons scroll to the download section.
2. **Analytics (optional):** set `posthogKey` (and `posthogHost` for an EU project). The page then loads PostHog in cookieless mode: no cookies or storage, so no cookie banner. **Turn on cookieless tracking in the PostHog project settings too**, or PostHog ignores these events. Besides automatic page views and clicks, the page sends `download_clicked`, `github_clicked` and `demo_name_typed` (never the name itself). Leave the key empty for no analytics.
3. **Social preview:** `og:image` is a relative path. Some sites (X, LinkedIn) need an absolute URL, so set it to your domain once it's live.

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
.venv/bin/python website/scripts/render_assets.py
```

Effects that need a person (entrance, biometric scan, hologram, filter) are drawn as CSS illustrations with a generic silhouette rather than stock photos. Swap in screen recordings of yourself when you have them.
