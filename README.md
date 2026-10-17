# CreapKeeper — Office Encounter Tracker

*A small project from 2017 that has turned into a pretty good way for me to test new ideas.*

## What is CreapKeeper?

Back in 2017, we had a coworker who had two very different ways of walking up to someone's desk. The first was what you would expect: walk up and ask a question. The second was to somehow appear behind you without making a sound. You would turn around, and there he was.

We started keeping count. That is really all this project was meant to do.

The buttons are **Count** for a normal approach and **Creap** for the surprise appearance. And before anyone opens a spelling issue: **Creap is intentionally spelled wrong.** It was part of the original inside joke, and I am keeping it that way.

I have since been using the application to try out different things, from rebuilding an old Python project to running a small LAN website and now checking GitHub for software updates. Did a two-button counter need all of that? No. Has it been a useful little project? Absolutely.

CreapKeeper is still a **manual counter**. It does not monitor anyone, watch the screen, record audio, or detect people. You decide when to press a button.

## What it can do

- Record a **Count** or **Creap** event with a timestamp, and see the running totals and recent history.
- Undo the last manually recorded event.
- Export history to CSV or import records from the original 2017 database.
- Use Windows global hotkeys without bringing the app to the front.
- Keep running in the Windows system tray.
- Share a read-only graph, **The Creap Report**, with a couple of people on your LAN.
- Check Windows Firewall rules for the LAN page and, with your permission, offer to create a limited rule.
- **New in v1.3.0:** Check GitHub Releases for updates and, on the portable Windows build, download, verify, install, and restart after you approve the update.

Everything that counts an encounter is still done locally. The LAN page shows totals, not names or the original database.

## Download and run it

The easiest option for Windows is to download the latest **[CreapKeeper.exe](https://github.com/spatran137/CreapKeeper/releases/latest)**. This is a portable executable; there is no separate Python installation required.

1. Download `CreapKeeper.exe` from the latest release.
2. Put it somewhere your Windows account can write to if you want automatic updates later (for example, a folder under your user profile).
3. Run it and start counting.

The executable is not code-signed, so Windows SmartScreen might warn you about an unfamiliar application. The source is in this repository if you want to review it.

### Running from source

You will need Python **3.10 or newer**. For the GUI, Tkinter is also needed (included in the normal Windows Python installation; some Linux distributions package it as `python3-tk`).

From the repository root:

```powershell
python Counter/CreapKeeper.py
```

To use the optional Windows tray icon when running from source:

```powershell
python -m pip install -r requirements-gui.txt
```

The older launcher `python Counter/Counter.py` still works. I left the original paths in place for compatibility.

## Using the counter

Click **+1 Count** for the direct approach or **+1 Creap** when someone quietly appears behind you.

On Windows, there are two sets of shortcuts:

| Shortcut | What it does | When it works |
| --- | --- | --- |
| Ctrl+Alt+1 | Count +1 | Anywhere, while CreapKeeper is running |
| Ctrl+Alt+2 | Creap +1 | Anywhere, while CreapKeeper is running |
| Ctrl+Alt+Z | Undo | Anywhere, while CreapKeeper is running |
| Ctrl+1 | Count +1 | When the app window has focus |
| Ctrl+2 | Creap +1 | When the app window has focus |
| Ctrl+Z | Undo | When the app window has focus |

The global shortcuts use Windows hotkey registration, not a keyboard logger. If another program has registered the same keys, CreapKeeper will tell you that it could not register them.

### System tray

On Windows the tray icon is enabled by default. Closing the window hides it instead of quitting, which was one of the first features I wanted once I started using this while doing other things.

Right-click the tray icon to reopen the window, record an event, undo, check for an update, or **Exit CreapKeeper**. Exiting from the tray actually closes the program. Disabling the tray setting makes closing the window exit normally.

Global hotkeys and the tray are Windows-only. The regular Python GUI and command-line tools can run on other platforms.

## The Creap Report — LAN dashboard

After I had the counter working, I thought it would be interesting to let a couple of other people see the totals. I did not want to set up another server or put this on the internet just to display two lines on a graph.

So the application hosts a small webpage itself.

1. Open CreapKeeper on the computer recording the events.
2. Check **Share read-only chart on local LAN (HTTP port 8765)**.
3. Click **Open dashboard** to test it on that computer.
4. Click **Copy LAN link**, or open `http://YOUR-PC-IP:8765/` from another computer on the same LAN.

The page has one line for **Count** and another for **Creap**, with daily cumulative totals for the most recent 30 days. It refreshes every 30 seconds. The HTML and chart code are bundled with CreapKeeper, so viewers do not need internet access.

You can leave CreapKeeper minimized to the tray and the page will keep working. Turn off LAN sharing or exit the app and the website stops.

**A few things to know:** LAN sharing starts **off**, there is no login, and anyone able to reach the allowed LAN port can view the totals. It does **not** expose individual event details or the SQLite database. It rejects connections outside its allowed LAN address ranges, but you should still use your network firewall. No router port forwarding is needed or intended.

### Windows Firewall — the part that initially got me

When I first got the dashboard working, I could open it on the computer running CreapKeeper, but not from another device. It turned out Windows Firewall was blocking TCP port **8765**.

To save that troubleshooting step next time, CreapKeeper checks for an existing applicable inbound allow rule when LAN sharing starts. It checks first rather than adding duplicate rules. If it does not find one, it asks whether you want to create it. You have to confirm in CreapKeeper **and** approve Windows UAC; nothing is added silently.

The rule that CreapKeeper can create is limited to:

- Inbound TCP port **8765**.
- **Private and Domain** network profiles (not Public).
- Remote addresses in **LocalSubnet**.

You can also click **Check firewall** at any time. Disabling the dashboard does not remove the firewall rule; Windows rules are persistent. Existing manually created rules are not changed.

To remove only the rule created with CreapKeeper's standard name, open PowerShell **as Administrator** and run:

```powershell
Remove-NetFirewallRule -Name "Counter-LAN-Dashboard-8765"
```

If automatic setup is blocked by your organization's policy, check for an existing matching rule first. For a manual exception on a trusted Private/Domain LAN, an administrator can run:

```powershell
New-NetFirewallRule -Name "Counter-LAN-Dashboard-8765" -DisplayName "CreapKeeper LAN Dashboard" -Direction Inbound -Protocol TCP -LocalPort 8765 -Profile Private,Domain -RemoteAddress LocalSubnet -Action Allow
```

To troubleshoot, on the CreapKeeper computer check whether the web server is listening:

```powershell
Get-NetTCPConnection -LocalPort 8765 -State Listen
```

Then test from a second Windows computer (replace the address):

```powershell
Test-NetConnection 192.168.1.100 -Port 8765
```

If the test fails, look at the Windows network profile with `Get-NetConnectionProfile`, the effective firewall rules, and whether the other computer is on another subnet or VLAN. `LocalSubnet` normally does not include other VLANs. Also, an allow rule will not override a higher-priority block from your organization's security policies.

## Updating CreapKeeper (v1.3.0 and later)

This was another feature I wanted to test: could a small Windows app notice a new GitHub release and update itself without needing a separate update server?

Starting with **v1.3.0**, yes.

On the packaged Windows version, **Check GitHub for new releases automatically** is enabled by default. When it starts, it checks at most once every 24 hours. You can disable the setting or click **Check for updates** whenever you want. There is also a tray-menu option.

When there is a newer stable release, CreapKeeper asks whether you want it. If you approve, it downloads the `CreapKeeper.exe` release asset over HTTPS, checks its file size and GitHub-provided SHA-256 digest, then stages it next to the existing executable. A temporary helper waits for CreapKeeper to close, keeps a `CreapKeeper.exe.previous` backup, replaces the executable, and restarts the app.

A few limits worth mentioning:

- **v1.2.0 and older cannot update themselves.** Download v1.3.0 manually once to get the new updater.
- The updater needs **outbound internet access** to GitHub. The LAN dashboard does not.
- Updates are **never installed without your approval**. You can disable automatic release checks.
- If a network check or integrity check fails, the current version stays in place.
- If the executable is in a protected folder such as `C:\Program Files`, the update may fail due to permissions. Use a user-writable folder or install manually.
- The updater does not modify the database or settings.
- Running from Python source can check GitHub and open the release page, but it will not replace a source checkout.

The SHA-256 comparison verifies that the download matches the asset information from GitHub. It is not a substitute for a code-signing certificate. The background update helper and restart behavior still need hands-on testing on a Windows desktop; automated tests cover versioning, metadata checks, failure cases, and downloads.

## Where the data is stored

One thing I did not want was an app rename or update wiping out years of history. CreapKeeper deliberately keeps the original data location:

| OS | Database |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Counter\Counter.db` |
| Linux / macOS | `~/.local/share/counter/Counter.db` |

Settings are saved in `settings.json` next to the selected database. You can specify a different database using `--db PATH` or the existing `COUNTER_DB_PATH` environment variable.

If you were using **Counter.exe** before the rename, close it completely from the tray and launch **CreapKeeper.exe**. Your old counts should be there automatically. Do **not** rename or delete the `Counter` data folder.

## Bringing in the 2017 database

The original app used a `Counter.db` with a `tb_count` table containing `COUNT`, `CREAP`, and `DATE`.

Make a backup of that original file first. Then use **Import old DB** in the GUI, or run:

```powershell
python Counter/cli.py import-legacy "C:\path\to\old\Counter.db"
```

The importer reads the old file without modifying it. Importing the same source path again skips records already brought over. Older timestamps are interpreted in the computer's current local time zone, so check that if the data came from another location.

## Command-line options

The original scripts still work:

```powershell
python Counter/count.py
python Counter/creap.py
```

For more options:

```powershell
python Counter/cli.py count
python Counter/cli.py creap
python Counter/cli.py stats
python Counter/cli.py history --limit 10
python Counter/cli.py undo
python Counter/cli.py export encounters.csv
python Counter/cli.py stats --db "C:\Temp\Counter.db"
```

## Testing and a few final notes

From the repository root:

```powershell
python -m unittest discover -s tests -v
```

The tests cover the database, legacy imports, desktop preferences, hotkey mapping, dashboard routes, firewall checks, and GitHub update validation. GitHub Actions runs tests on Windows and Linux and builds the Windows executable. Actual hotkeys, system tray behavior, Windows Firewall UAC, and self-replacement are still worth testing on a real Windows desktop.

The original `Counter.sln` and old Python entry points remain in the repo. I kept them partly for compatibility and partly because I like being able to look back at where the project started.

### Final thoughts

I started with a counter because someone had a talent for showing up behind my chair. Now there is a database, a LAN graph, firewall integration, and a software updater. This has probably gone further than it needed to, but that was also the point: something small enough to experiment with and useful enough to see if each part really works.

If you use it, keep it friendly. The idea is a running office joke, not monitoring or singling anyone out.
