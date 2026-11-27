# Hacker Cam website

A static landing page: no build step, no frameworks, no external fonts or trackers. Open `index.html` in a browser, or host the folder anywhere (GitHub Pages, Netlify, Cloudflare Pages, S3).

## Before publishing

1. **Price and checkout link:** edit `CONFIG` at the top of `main.js`. While `buyUrl` is empty, the buy buttons scroll to the pricing section.
2. **Social preview:** `og:image` is a relative path. Some sites (X, LinkedIn) need an absolute URL, so set it to your domain once it's live.

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
