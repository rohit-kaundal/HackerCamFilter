---
layout: page
title: "Privacy · Hacker Cam"
heading: Privacy
eyebrow: Your camera never leaves your computer
description: "What Hacker Cam and this website collect, and what they never do."
lede: "Hacker Cam processes your video on your computer. Here is exactly what is, and isn't, collected."
permalink: /privacy/
---

## The app

- **Your video stays local.** Background removal and face tracking run on your device. Video goes from your webcam to Hacker Cam to your call app, and nowhere else.
- **No accounts.** There is nothing to sign up for.
- **Optional usage stats, off unless you say yes.** On first launch the app asks whether to share anonymous usage stats. If you agree, it sends event names such as `app_started` and `effect_used` (with the effect's name, for example `hologram`), the app version, your OS and CPU type, how long the app ran, and a random install ID created on your computer.
- **Never sent:** video, images, your name or title, camera names, or anything you type.
- **Change it any time** under *Open window → Options → Share anonymous usage stats*. Setting `DO_NOT_TRACK=1` turns it off regardless.

Stats go to [PostHog](https://posthog.com). They're not linked to a person profile, and IP addresses are discarded.

The command-line version never sends anything.

## This website

This site uses PostHog in **cookieless** mode: no cookies, no local storage, and no cookie banner. It counts page views and clicks on buttons such as *Download*. When you type your name into the demo, the site records only that the demo was used, never the name.

## Check it yourself

Hacker Cam is open source under the MIT license. The stats code is one short file, [`telemetry.py`]({{ site.github_url }}/blob/main/telemetry.py).
