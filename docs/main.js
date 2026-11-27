// Hacker Cam landing page.
// ---------------------------------------------------------------------------
// EDIT HERE: links and analytics.
const CONFIG = {
  githubUrl: "https://github.com/rohit-kaundal/HackerCamFilter",   // empty = GitHub links hidden
  downloadUrl: "https://github.com/rohit-kaundal/HackerCamFilter/releases",    // empty = githubUrl + "/releases/latest" (or scroll to #download if no GitHub)
  posthogKey: "phc_t2XZMtYnkraWGJNTWDJHuswZhAwieogsdHuK2aANtckk",     // PostHog project API key ("phc_..."); empty = no analytics
  posthogHost: "https://us.i.posthog.com",   // EU projects: "https://eu.i.posthog.com"
};
// ---------------------------------------------------------------------------

// Cookieless PostHog analytics, loaded only when a key is set. This is the
// official loader stub, unminified: it queues calls until array.js arrives.
(function loadPostHog() {
  if (!CONFIG.posthogKey) return;
  const ph = (window.posthog = window.posthog || []);
  if (ph.__SV) return;
  ph._i = [];
  ph.init = (key, options, name) => {
    const script = document.createElement("script");
    script.async = true;
    script.crossOrigin = "anonymous";
    script.src = options.api_host.replace(".i.posthog.com", "-assets.i.posthog.com") + "/static/array.js";
    document.head.appendChild(script);
    const stub = name !== undefined ? (ph[name] = []) : ph;
    "capture register register_once unregister opt_out_capturing opt_in_capturing set_config reset"
      .split(" ").forEach((m) => { stub[m] = (...args) => { stub.push([m, ...args]); }; });
    ph._i.push([key, options, name]);
  };
  ph.__SV = 1;
  ph.init(CONFIG.posthogKey, {
    api_host: CONFIG.posthogHost,
    defaults: "2026-08-30",
    cookieless_mode: "always",       // no cookies or storage, so no cookie banner
    person_profiles: "identified_only",
  });
})();

// Named events, on top of PostHog's automatic page views and clicks.
const track = (event, props) => { if (window.posthog && window.posthog.capture) window.posthog.capture(event, props); };

(() => {
  "use strict";

  // Download and GitHub links.
  const downloadUrl = CONFIG.downloadUrl || (CONFIG.githubUrl ? CONFIG.githubUrl.replace(/\/$/, "") + "/releases/latest" : "");
  document.querySelectorAll(".js-download").forEach((a) => {
    if (downloadUrl) a.href = downloadUrl;
    a.addEventListener("click", () => track("download_clicked", { where: a.closest("section, header")?.className || "" }));
  });
  if (CONFIG.githubUrl) {
    document.querySelectorAll(".js-github").forEach((a) => {
      a.href = CONFIG.githubUrl;
      a.addEventListener("click", () => track("github_clicked"));
    });
    document.querySelectorAll(".js-github-row").forEach((el) => { el.hidden = false; });
  }

  // Hotkey labels: ⌃⌥H on a Mac, Ctrl+Alt+H elsewhere.
  const platform = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "";
  const isMac = /mac/i.test(platform);
  document.querySelectorAll(".js-key").forEach((k) => {
    k.textContent = (isMac ? "⌃⌥" : "Ctrl+Alt+") + k.dataset.k;
  });

  // ------------------------------------------------------------------------
  // Hero demo: a browser re-creation of the app's intro sequence.
  const canvas = document.getElementById("demo");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  const GREEN = "#46ff46", DIM = "#2a962a", WHITE = "#dcffdc";
  const MONO = '"JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace';
  const SANS = 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif';
  const GLYPHS = "0123456789ABCDEF@#$%&*+=<>/\\|{}[]?!";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const nameInput = document.getElementById("demo-name");
  const label = document.querySelector(".js-demo-label");
  let name = "Your Name";
  const title = "Security Engineer";

  // Phases (seconds): rain, terminal, granted, name, live camera.
  const PHASES = [["rain", 2.2], ["terminal", 3.0], ["granted", 1.3], ["name", 2.8], ["live", 2.4]];
  const STARTS = {};
  let total = 0;
  for (const [p, d] of PHASES) { STARTS[p] = [total, d]; total += d; }

  const CELL = 18;
  const cols = Math.floor(W / CELL);
  const drops = Array.from({ length: cols }, () => ({ y: -Math.random() * H, v: 260 + Math.random() * 420 }));
  const rnd = (n) => Math.floor(Math.random() * n);
  const hex = (n) => Array.from({ length: n }, () => rnd(256).toString(16).padStart(2, "0")).join(" ");
  let lines = [];
  const newLines = () => {
    const ip = Array.from({ length: 4 }, () => 10 + rnd(244)).join(".");
    lines = [
      "> initializing secure uplink ...",
      `> target acquired: ${ip}:443`,
      "> bypassing firewall ...",
      "%PROGRESS%",
      `> injecting payload 0x${rnd(0xffffffff).toString(16).toUpperCase().padStart(8, "0")}`,
      `> ${hex(12)}`,
      "> handshake complete. session established.",
    ];
  };
  newLines();

  function rain(dt, fade) {
    ctx.fillStyle = `rgba(0, 0, 0, ${fade})`;
    ctx.fillRect(0, 0, W, H);
    ctx.font = `16px ${MONO}`;
    for (let i = 0; i < cols; i++) {
      const d = drops[i];
      d.y += d.v * dt;
      if (d.y > H + Math.random() * H * 0.6) { d.y = -Math.random() * H * 0.4; d.v = 260 + Math.random() * 420; }
      const row = Math.floor(d.y / CELL) * CELL;
      ctx.fillStyle = Math.random() < 0.85 ? GREEN : WHITE;
      ctx.fillText(GLYPHS[rnd(GLYPHS.length)], i * CELL + 2, row);
    }
  }

  function dimmed(alpha) {
    ctx.fillStyle = `rgba(0, 0, 0, ${alpha})`;
    ctx.fillRect(0, 0, W, H);
  }

  function centered(text, y, font, color, glow) {
    ctx.font = font;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = color;
    ctx.shadowColor = color;
    ctx.shadowBlur = glow || 0;
    ctx.fillText(text, W / 2, y);
    ctx.shadowBlur = 0;
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
  }

  function glitch(intensity) {
    if (intensity <= 0.02) return;
    const bands = 3 + Math.floor(intensity * 10);
    for (let i = 0; i < bands; i++) {
      const y = rnd(H), h = 4 + rnd(Math.max(5, Math.floor(40 * intensity)));
      const dx = (Math.random() * 2 - 1) * 80 * intensity;
      ctx.drawImage(canvas, 0, y, W, h, dx, y, W, h);
    }
  }

  function scanlines() {
    ctx.fillStyle = "rgba(0, 0, 0, 0.28)";
    for (let y = 0; y < H; y += 3) ctx.fillRect(0, y, W, 1);
  }

  function terminal(pt, dur) {
    dimmed(0.08);
    const x0 = 70, y0 = 90, x1 = W - 70, y1 = H - 90;
    ctx.fillStyle = "rgba(0, 0, 0, 0.82)";
    ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
    ctx.strokeStyle = DIM;
    ctx.lineWidth = 1;
    ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
    ctx.font = `18px ${MONO}`;
    ctx.fillStyle = DIM;
    ctx.fillText("root@uplink:~", x0 + 12, y0 - 12);
    ctx.font = `26px ${MONO}`;
    const textChars = lines.filter((l) => l !== "%PROGRESS%").reduce((a, l) => a + l.length, 0);
    const progressNeed = 0.18 * dur;
    const cps = textChars / (0.85 * dur - progressNeed);
    let left = pt, y = y0 + 54, cursor = null;
    for (const line of lines) {
      if (left <= 0) break;
      let text;
      if (line === "%PROGRESS%") {
        const p = Math.min(1, left / progressNeed), bars = Math.floor(p * 24);
        text = `  [${"#".repeat(bars)}${"-".repeat(24 - bars)}] ${String(Math.floor(p * 100)).padStart(3)}%`;
        left -= progressNeed;
      } else {
        text = line.slice(0, Math.floor(left * cps));
        left -= line.length / cps;
      }
      ctx.fillStyle = GREEN;
      ctx.fillText(text, x0 + 24, y);
      cursor = [x0 + 26 + ctx.measureText(text).width, y];
      y += 46;
    }
    if (cursor && Math.floor(pt * 4) % 2 === 0) {
      ctx.fillStyle = GREEN;
      ctx.fillRect(cursor[0], cursor[1] - 22, 13, 26);
    }
  }

  function granted(pt, dur) {
    dimmed(0.55);
    const flicker = pt < 0.35 * dur && Math.floor(pt * 30) % 3 === 0;
    if (!flicker) {
      ctx.strokeStyle = GREEN;
      ctx.lineWidth = 3;
      ctx.shadowColor = GREEN;
      ctx.shadowBlur = 18;
      ctx.strokeRect(W / 2 - 430, H / 2 - 72, 860, 144);
      ctx.shadowBlur = 0;
      centered("ACCESS GRANTED", H / 2, `800 88px ${SANS}`, GREEN, 36);
    }
    glitch(Math.max(0.15, 1 - pt / (0.6 * dur)));
  }

  function identity(pt, dur) {
    dimmed(0.6);
    centered("// IDENTITY CONFIRMED //", H * 0.3, `26px ${MONO}`, DIM, 0);
    const typeTime = 0.45 * dur;
    const full = name.toUpperCase();
    const n = Math.floor(Math.min(1, pt / typeTime) * (full.length + title.length));
    const shownName = full.slice(0, n), shownTitle = title.slice(0, Math.max(0, n - full.length));
    let size = 84;
    ctx.font = `800 ${size}px ${SANS}`;
    while (ctx.measureText(full).width > W * 0.86 && size > 30) { size -= 4; ctx.font = `800 ${size}px ${SANS}`; }
    if (shownName) centered(shownName, H * 0.47, `800 ${size}px ${SANS}`, GREEN, 34);
    if (shownTitle) centered(shownTitle, H * 0.6, `600 38px ${SANS}`, DIM, 0);
    glitch(0.5 * Math.max(0, 1 - pt / typeTime) + (Math.random() < 0.06 ? 0.5 : 0));
  }

  // Stand-in for the live camera: a generic silhouette in a dim room.
  const head = new Path2D();
  head.arc(W / 2, H * 0.4, 112, 0, Math.PI * 2);
  const cx = W / 2, top = H * 0.58;
  const body = new Path2D(
    `M ${cx} ${top} C ${cx - 150} ${top} ${cx - 262} ${top + 70} ${cx - 275} ${H} ` +
    `L ${cx + 275} ${H} C ${cx + 262} ${top + 70} ${cx + 150} ${top} ${cx} ${top} Z`);
  function live(pt, dur) {
    const fadeIn = Math.min(1, pt / 0.6);
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, "#1c231c");
    g.addColorStop(1, "#0c100c");
    ctx.globalAlpha = 1;
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = "rgba(255, 255, 255, 0.04)";
    ctx.fillRect(W * 0.07, H * 0.16, W * 0.2, H * 0.62);     // a shelf
    ctx.fillRect(W * 0.72, H * 0.12, W * 0.2, H * 0.34);     // a window
    ctx.shadowColor = GREEN;
    ctx.shadowBlur = 30;
    ctx.fillStyle = "#4a554a";
    ctx.fill(head);
    ctx.fill(body);
    ctx.shadowBlur = 0;
    ctx.font = `600 22px ${MONO}`;
    ctx.fillStyle = GREEN;
    ctx.fillText("● LIVE", 28, 46);
    if (fadeIn < 1) dimmed(1 - fadeIn);
    if (pt > dur - 0.35) dimmed((pt - (dur - 0.35)) / 0.35);
  }

  let t = 0, last = 0, running = true, visible = true;
  function frame(dt) {
    let phase = "live", pt = 0, dur = 1;
    for (const [p] of PHASES) {
      const [s, d] = STARTS[p];
      if (t >= s && t < s + d) { phase = p; pt = t - s; dur = d; break; }
    }
    if (phase === "rain") rain(dt, 0.12);
    else if (phase === "terminal") { rain(dt, 0.12); terminal(pt, dur); }
    else if (phase === "granted") { rain(dt, 0.2); granted(pt, dur); }
    else if (phase === "name") { rain(dt, 0.2); identity(pt, dur); }
    else live(pt, dur);
    if (phase !== "live") scanlines();
  }

  function loop(now) {
    if (!running) return;
    const dt = last ? Math.min(0.1, (now - last) / 1000) : 1 / 60;
    last = now;
    if (visible && !document.hidden) {
      t += dt;
      if (t >= total) { t = 0; newLines(); ctx.fillStyle = "#000"; ctx.fillRect(0, 0, W, H); }
      frame(dt);
    }
    requestAnimationFrame(loop);
  }

  function staticFrame() {                     // reduced motion: one still frame
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, W, H);
    for (let i = 0; i < 90; i++) rain(1 / 30, 0.12);
    t = STARTS.name[0] + STARTS.name[1] * 0.8;
    rain(0, 0.2);
    const [s, d] = STARTS.name;
    identity(t - s, d);
    scanlines();
  }

  nameInput.addEventListener("change", () => track("demo_name_typed"), { once: true });   // never the name itself
  nameInput.addEventListener("input", () => {
    name = nameInput.value.trim() || "Your Name";
    label.textContent = name;
    if (reduceMotion) { staticFrame(); return; }
    const [s] = STARTS.name;
    if (t < s || t > s + 0.5) { t = s; ctx.fillStyle = "#000"; ctx.fillRect(0, 0, W, H); }
  });

  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, W, H);
  if (reduceMotion) {
    staticFrame();
  } else {
    new IntersectionObserver((entries) => { visible = entries[0].isIntersecting; }).observe(canvas);
    requestAnimationFrame(loop);
  }
})();

// Demo video lightbox: loads the video only when opened, pauses on close.
(() => {
  const modal = document.getElementById("video-modal");
  const video = document.getElementById("demo-video");
  if (!modal || !video || typeof modal.showModal !== "function") {
    document.querySelectorAll(".js-video-open").forEach((b) => {
      b.addEventListener("click", () => { if (video) window.location.href = video.querySelector("source").src; });
    });
    return;
  }
  document.querySelectorAll(".js-video-open").forEach((b) => b.addEventListener("click", () => {
    modal.showModal();
    video.play().catch(() => {});
    track("demo_video_opened");
  }));
  modal.addEventListener("close", () => video.pause());
  modal.addEventListener("click", (e) => { if (e.target === modal) modal.close(); });   // click on backdrop
})();
