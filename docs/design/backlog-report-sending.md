# Backlog design: F9 sends bug reports

**Status:** on the backlog (Tucker, 2026-10-21, D86): it needs a hosted relay Tucker doesn't want to set up yet. Written for M8 and moved out; ready to become a milestone.

## Design
**Today:** F9 writes a full snapshot zip into the player's `reports/` folder. It only helps if the player finds the zip and sends it somehow.

**In M8:** F9 opens a short form and sends the report. The snapshot is taken the moment F9 is pressed, so filling in the form takes as long as it needs. On the couch both games pause; online, the partner keeps playing.

```
 Report a problem                                               
                                                                
 What happened?     [                                         ] 
 What kind?         ‹ Crash or freeze ›    Visuals · Sound · Controls ·
                                           Co-op / sync · Online connection · Other
 How often?         ‹ First time ›         Sometimes · Every time
 Contact (optional) [ GitHub name or e-mail, if you want a reply ]
                                                                
 [✓] Include the game's state: savestates and the last 60 s,    
     so the problem can be replayed exactly.       about 10 MB  
     [See what's sent]                                          
                                                                
            [ Send ]      [ Save only ]      [ Cancel ]         
```

**The form:**
- **Controller-friendly:** the kind and how often are chosen with the d-pad. The text boxes need a keyboard, and they're optional, so a couch player with only a controller can still send.
- **After Send:** "Sent: report #1234. Thank you!" The zip also stays in `reports/`.
- **Offline, or the send fails:** the report is kept, and the launcher offers to send it the next time it starts.

**What's captured.** The snapshot is the same as today:
- both games' savestates and memory cards, plus the joint save
- the states from 5 and 10 s earlier
- 60 s of inputs, link traffic and frame times
- audio stats, versions, settings, controllers, presences and the log

**Added in M8:**
- **The form's answers.**
- **Online, both sides:** the partner's launcher is told over the link and adds its own snapshot to the same report. Most online bugs need both sides. A setting can turn it off; it's on by default, and the partner sees a notice.

**Privacy:**
- **Pictures come only from our own window:** the frames the launcher draws, read back from its own renderer, as now. It never captures the screen, and nothing outside the window.
- **Nothing else from the PC:** the Windows user name in paths is replaced by `%USERPROFILE%`. No disc image, BIOS or other files are included.
- **The player sees the file list and size before sending**, and can untick the game state.
- **The savestates hold the game's memory**, so reports go only to private storage. They're never public and never committed (AGENTS.md).

**Where reports go:**
| Option | Idea | Verdict |
|---|---|---|
| **A. A small relay we host → a private GitHub repo** | The launcher posts the form and zip over HTTPS to a Cloudflare Worker (free tier). It stores the zip in Cloudflare R2 (10 GB free) and opens an issue in a private repo, `tucker-bower/sotn-coop-reports`. The issue has the form, versions, the screenshot and a link to the zip. The GitHub token lives only in the Worker; it caps reports at 50 MB and rate-limits per address. | ✅ **Recommended.** Players need no account, nothing is public, and reports arrive where we already work (`gh`). **Needs Tucker:** a free Cloudflare account and one GitHub token, about 15 minutes with my instructions. |
| B. No server: a prefilled GitHub issue in the browser | The player attaches the zip themselves | ❌ Needs a GitHub account, it's public, and many players won't bother |
| C. A Discord webhook, or Sentry | — | ❌ A webhook address inside the app can be abused; Sentry's free tier caps attachments |

**Downstream:** `scripts/reports.py` lists new reports, downloads a zip and opens it in `harness/replay.py`. I triage reports into issues on the main repo, with a repro.

## Acceptance criteria
1. **F9 reports arrive** (`ux_report_send`):
   - A report sent from the installed build on Tucker's PC arrives in the private repo as an issue, with its zip.
   - That zip replays in `harness/replay.py`.
   - **Online:** one report holds both players' snapshots.
   - **Offline:** the report is kept and offered again at the next start.
   - **Privacy:** the zip contains no user name, no disc or BIOS, and no pixel from outside the launcher window (test: a window placed over ours during the report).
