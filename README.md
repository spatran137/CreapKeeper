# Counter — Office Encounter Tracker

*Because apparently office interruptions needed their own analytics platform.*

Back in **2017**, a coworker had a special talent for interrupting the people around him in one of two ways:

- **Count — The Direct Approach:** Walk right up to someone's desk and ask a question. Work-related? IT-related? A mystery about lunch? All valid entries.
- **Creap — The Stealth Approach:** Approach slowly, silently, and materialize behind someone's chair like a low-budget office horror movie. Wait for the inevitable "HOW LONG HAVE YOU BEEN STANDING THERE?"

Naturally, we responded like responsible IT professionals: **we made a counter.** What started as a tiny inside joke has somehow acquired a proper database, global hotkeys, a system tray, and a LAN dashboard. Apparently the joke now has infrastructure.

### Wait, why "Creap"?

**"Creap" is spelled that way on purpose.** The misspelling was part of the original **inside joke**, and it stays. It isn't a typo, a feature request, or an invitation for spellcheck to get involved. Please do not "fix" it to *creep*. That would ruin the historical record.

> **A quick reality check:** Counter tracks **manual button presses, not people**. No cameras, microphones, sneaky detection systems, or employee-monitoring features. Just an extremely unnecessary amount of technology dedicated to a very specific running joke.

## Features (the joke got out of hand)

- Python 3 desktop GUI with two buttons and running totals. Truly groundbreaking science.
- **Windows global hotkeys** so you can log a surprise visit without interrupting the interruption.
- **Optional system tray** for discreetly maintaining your extremely official unofficial statistics.
- **Opt-in LAN chart** so coworkers can watch the two legendary approaches compete in real time.
- **Consent-based Windows Firewall check** because the scoreboard's greatest enemy turned out to be TCP 8765.
- Date/time-stamped SQLite history
- Undo for those moments when you accuse the wrong approach.
- CSV export and idempotent import of the old 2017 database format
- Headless command-line interface for shortcuts and scripts
- Automatic database creation, data validation, and standard-library tests

## Requirements (mercifully reasonable)

- **Python 3.10+**; no pip dependencies for the CLI or basic desktop app
- To enable the tray icon while running the app from source, install `python -m pip install -r requirements-gui.txt`. The release executable bundles these packages.
- GUI: Tkinter (included with the standard Windows Python installer; on some Linux systems install python3-tk)
- Windows, Linux, or macOS

## Run the desktop application

From the repository root:

    python Counter/Counter.py

Click **+1 Count** when someone announces their presence, or **+1 Creap** when they appear behind you like an NPC whose footstep audio failed to load.

**Global Windows shortcuts (v1.0.1):** Ctrl+Alt+1 (Count), Ctrl+Alt+2 (Creap), Ctrl+Alt+Z (Undo). They work while other applications are active, so long as Counter is running with **Enable global hotkeys** checked. No special Windows administrator privileges or manual key bindings are needed. If another program already owns any combination, Counter reports the conflict and disables global shortcuts until you re-enable them.

**Window-only shortcuts:** Ctrl+1 (Count), Ctrl+2 (Creap), Ctrl+Z (Undo). These still work while Counter has keyboard focus.

**System tray (Windows):** The tray icon is enabled by default in the Windows release. With the tray checkbox enabled, closing the window hides Counter instead of exiting, and global shortcuts stay active. Right-click the notification-area icon to show Counter, record an event, undo, or **Exit Counter** to actually quit. You can disable the tray icon at any time in the window. The **Hide to tray** button does the same thing as closing the window with tray mode enabled.

The app remembers both checkbox settings in `settings.json` next to your selected SQLite database. Existing history remains unchanged when upgrading from v1.0.0. Hotkeys and tray integration are currently **Windows-only**; the basic GUI and CLI work on other platforms.

The GUI shows totals and 20 recent entries. **Undo last click** removes only the most recent manually recorded event. Imported history remains untouched; even this project has standards.

## LAN dashboard (v1.1.0 — now with spectators)

Because apparently tracking this privately wasn't enough, you can share a simple read-only two-line chart with colleagues on the same local network **without** NGINX, Docker, a cloud host, or uploading your database. We showed remarkable restraint here.

1. Run the updated **Counter.exe** on the computer that records your events.
2. Enable **Share read-only chart on local LAN (HTTP port 8765)** in the Counter window.
3. Click **Open dashboard** to preview it on that PC, or **Copy LAN link** to share an address such as `http://YOUR-PC:8765/`.
4. Other users can view the page while Counter is running. If computer-name resolution doesn't work, use `http://YOUR-PC-IP:8765/` instead.

The page refreshes about every 30 seconds and shows **Count** and **Creap** as separate cumulative daily lines over the most recent 30 days, with overall totals. Finally, a leaderboard no one asked for. It shows aggregate counts only, not individual timestamps, event details, or file paths. The chart's HTML/JavaScript is self-contained: **no CDN, external fonts, external scripts, or internet access**.

**Automatic Windows Firewall check (v1.1.1 — the plot thickens):** When LAN sharing is first enabled (including when Counter restarts with sharing enabled), Counter checks the **active** Windows Firewall rules in the background for an enabled inbound **allow** rule covering TCP port 8765 and a Private/Domain profile. A rule you created manually, such as **Creap Counter Dashboard**, is recognized if its application restriction permits Counter. If a suitable rule already exists, **nothing is added or modified**.

If a suitable rule is missing, Counter asks whether to create one. **Nothing changes unless you click Yes and approve the separate Windows administrator (UAC) prompt.** The requested rule allows **TCP 8765**, **Private/Domain network profiles only**, and **LocalSubnet remote clients only**; Public networks and internet port forwarding are not enabled. Counter does **not** run as administrator after setup. You can also click **Check firewall** to check again. It confirms success only after detecting the rule, not merely after launching UAC.

Windows Firewall rules are **persistent**: disabling the LAN dashboard or exiting Counter stops the listener, but intentionally **does not delete or alter the firewall rule**. If you ever want to remove only the Counter-managed rule, use an elevated PowerShell window:

    Remove-NetFirewallRule -Name "Counter-LAN-Dashboard-8765"

This removal does not affect manually created or IT-managed rules with different identifiers.

**Manual fallback (if UAC is declined or organizational policy blocks automatic changes):** In an elevated PowerShell terminal on the Counter computer, after checking that a matching rule does not already exist, run:

    New-NetFirewallRule -Name "Counter-LAN-Dashboard-8765" -DisplayName "Counter LAN Dashboard" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765 -Profile Private,Domain -RemoteAddress LocalSubnet

**Troubleshooting:** On the Counter PC run `Get-NetTCPConnection -LocalPort 8765 -State Listen`; `0.0.0.0:8765` is the expected listener. On another PC, run `Test-NetConnection <COUNTER-PC-IP> -Port 8765`. If the TCP test fails, verify the Counter PC's active profile using `Get-NetConnectionProfile` and the effective firewall/endpoint security policies. Public-profile rules are intentionally not created. `LocalSubnet` generally excludes other VLANs, so cross-subnet clients may require an approved, narrowly scoped remote-address exception and any necessary inter-VLAN permissions. Having an inbound allow rule does not override higher-priority block rules or organizational Group Policy. The desktop firewall check detects applicable rule **configuration**, not guaranteed reachability from every client.

LAN sharing is off by default. The server only accepts IPv4 loopback and common private/LAN address ranges, and rejects clients with public addresses. It has no write endpoints; no port-forwarding or public exposure is intended. If your workplace uses a segmented network or a VPN, access may be restricted by those rules. No password protection is provided; **any authorized device that can reach the LAN port can see the totals**.

The built-in server stops when you uncheck LAN sharing or exit Counter. Closing the window to the tray keeps it running, including the dashboard, until you select **Exit Counter**.

## Command-line usage (for the terminally committed)

The original one-shot entry points are preserved, including our beloved `creap.py`:

    python Counter/count.py
    python Counter/creap.py

Or use the consolidated interface:

    python Counter/cli.py count
    python Counter/cli.py creap
    python Counter/cli.py stats
    python Counter/cli.py history --limit 10
    python Counter/cli.py undo
    python Counter/cli.py export encounters.csv

To choose a specific database, add **--db PATH** after a command:

    python Counter/cli.py stats --db C:\Temp\Counter.db
    python Counter/Counter.py --db C:\Temp\Counter.db

You can also set the **COUNTER_DB_PATH** environment variable to a file path. That setting works with the GUI, CLI, and original scripts.

## Where data lives (the very important evidence)

By default, the SQLite file is stored outside your Git checkout:

| System | Default |
| --- | --- |
| Windows | %LOCALAPPDATA%\Counter\Counter.db |
| Linux | ~/.local/share/counter/Counter.db |
| macOS | ~/.local/share/counter/Counter.db |

On Linux, XDG_DATA_HOME is respected. Counter does not make outbound network connections. The optional LAN dashboard is disabled by default and only shares aggregate data after you enable it.

## Import your original 2017 database (preserve the legend)

The old scripts wrote a local Counter.db with a tb_count table containing COUNT, CREAP, and DATE columns.

**Make a backup** of your original database first. We may be counting awkward encounters, but there's no reason to create a data-loss incident. Then import it:

    python Counter/cli.py import-legacy "C:\path\to\old\Counter.db"

Or select **Import old DB** in the GUI. The importer reads the old database without changing it, retains per-row quantities and timestamps, and skips previously imported rows when you run it again with the same source path.

Historical time.ctime() timestamps are interpreted using the computer's current local time zone. If the logs were captured in a different time zone, account for that before importing.

You can also choose the new destination explicitly:

    python Counter/cli.py import-legacy "C:\old\Counter.db" --db "C:\new\Counter.db"

## Tests (yes, really)

From the repository root:

    python -m unittest discover -s tests -v

The automated tests cover data creation, counts, undo, CSV export, legacy import, environment configuration, desktop settings, hotkey routing, LAN HTTP routes, read-only firewall inspection, UAC request handling (mocked), and basic CLI operation. Automated tests do not emulate keyboard presses or an interactive desktop session. The desktop UI additionally requires a manual smoke test.

## Original project (circa 2017)

The original Visual Studio solution (`Counter.sln`) and Python project are retained for posterity. A normal terminal is sufficient to run the app; a time machine is optional.

Counter is meant to be a **good-natured inside joke**, not a tool for embarrassing or singling out coworkers. Keep it anonymous, keep it friendly, and remember: the funniest part is that someone eventually gave this thing a web server.
