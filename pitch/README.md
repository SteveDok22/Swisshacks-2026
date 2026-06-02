# Pitch Materials

All materials for presenting Sentinel at SwissHacks 2026 and onboarding team members.

## Documents

| File | Purpose | Audience | Read time |
|---|---|---|---|
| [`deck.md`](./deck.md) | 10-slide pitch deck | Judges | 3 min spoken |
| [`demo-script.md`](./demo-script.md) | Second-by-second demo flow | You, presenting | 5 min reading |
| [`team-onboarding.md`](./team-onboarding.md) | New team member first 30 min | Team members | 30 min interactive |
| [`code-walkthrough.md`](./code-walkthrough.md) | Architecture tour | Team / judges / interviewers | 10-15 min spoken |

## Converting the deck

`deck.md` is in **Marp** format. Three ways to render:

### Option 1: VS Code (easiest)

Install the **Marp for VS Code** extension. Open `deck.md`. Click the slide icon top-right → "Export slide deck" → choose PDF / PPTX / HTML.

### Option 2: CLI

```bash
npm install -g @marp-team/marp-cli
marp pitch/deck.md -o pitch/deck.pdf
marp pitch/deck.md -o pitch/deck.pptx  # for Keynote / PowerPoint
marp pitch/deck.md -o pitch/deck.html  # for web preview
```

### Option 3: Online

Paste contents into [marp.app](https://marp.app/) — preview and export from browser.

## Workflow on hackathon day

**Friday evening** (setup):
1. Convert `deck.md` → `deck.pdf` and put on USB stick
2. Open `demo-script.md` on phone (offline backup)
3. Practice run with team (one of you presents, others quiz with judge questions)

**Saturday morning** (practice):
- 2 full run-throughs with timer
- Identify the 3 spots where you stumble
- Rewrite those sections

**Sunday — pitch day**:
- Pre-demo checklist from `demo-script.md`
- Deep breath
- Go
