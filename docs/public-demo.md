# Public Demo (temporary tunnel)

Share the locally-running stack on a public URL in ~1 minute — no cloud
account, no deploy. Useful for showing the demo to judges/teammates from your
laptop. **This is a tunnel, not a deployment**: your laptop stays the server.

## TL;DR

```bash
docker compose up --build          # stack must be running on :3000
npx --yes localtunnel --port 3000  # prints: your url is https://<random>.loca.lt
```

Share the printed `https://<random>.loca.lt` URL. Done.

## How it works

Your laptop sits behind WiFi/NAT and has no public address, so nobody on the
internet can reach it directly. The tunnel fixes this by dialing **outbound**
(which passes through NAT like normal browsing) to a public relay and holding
that connection open:

```
Visitor browser
   │  https://<random>.loca.lt
   ▼
loca.lt  (public relay on the internet)
   │  pushes the request DOWN the open pipe
   ▼
localtunnel client on your laptop
   │  forwards to
   ▼
localhost:3000  →  Next.js frontend  →  (internally) backend:8000
```

**One port (3000) covers everything.** The frontend serves the UI *and* proxies
`/api/backend/*` to the backend over the private Docker network (see the
`rewrites` in `frontend/next.config.ts`), so only port 3000 is exposed and one
tunnel is enough.

## The password page

First-time browser visitors hit a localtunnel speed-bump asking for a
**"Tunnel Password"** = the **public IP of the host laptop**. Find it with:

```bash
curl https://loca.lt/mytunnelpassword
```

Give visitors both the URL and this IP; they enter it once and continue.

## Things to remember

- **Your laptop is the server.** If it sleeps, Docker stops, or the tunnel
  process is killed → the URL goes dead instantly.
- **The URL is random and temporary** — it changes every restart. Pin a name
  with `npx localtunnel --port 3000 --subdomain my-demo` (subject to
  availability).
- **Keep the laptop awake** for the duration of the demo.

## Alternatives

- **Cloudflare Tunnel** — same mechanism, often cleaner (no password page):
  `cloudflared tunnel --url http://localhost:3000`. Note: its API endpoint
  (`api.trycloudflare.com`) is **blocked on some restricted networks** (e.g.
  certain event WiFi) — if it connection-resets, fall back to localtunnel.
- **ngrok** — `ngrok http 3000`; reliable but needs a free account + authtoken.

## Want always-on instead?

For a URL that survives your laptop sleeping, deploy both containers to a real
host (Railway / Render / Fly.io — all Docker-native with a free tier and a
stable public address). That's a true deployment, not a tunnel.
