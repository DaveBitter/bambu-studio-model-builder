---
name: bambu-studio-model-builder
description: Build and iterate parametric 3D-printable models as Bambu Studio .3mf files on a Mac, written into the user's models folder and reloaded in Studio, keeping their saved print settings. Use when designing a printable object for a Bambu Lab printer.
---

# Bambu Studio model builder

Unofficial, not affiliated with Bambu Lab. Goal: go from a rough idea ("a holder for my brush and scraper") to a `.3mf` that appears in the user's Bambu Studio without downloading or importing anything, then iterate on it live ("make it taller", "round the corners").

The reload in Studio is part of the job, not an extra: after EVERY write, reload the file in Studio yourself (section 6). Only fall back to asking the user to reopen it when the reload really cannot be done, and then say which step failed.

## Scope and what has been tested
- Platform: macOS with Bambu Studio installed, used through Claude Cowork in the Claude macOS app. Windows and Linux are not covered (menu paths and app identifiers differ).
- Tested on October 27, 2026 (build, write and reload end to end): Bambu Studio 02.08.02.61, Bambu Lab A1, 0.4 nozzle, 0.20 mm Standard, Bambu PLA Pure, in a Cowork session linked to the Mac (device shell + computer use).
- NOT tested: Claude Code in a terminal, other printers (X1, P1, H2 series), per-object override carry-over, models with more than one object or plate, opening a never-opened file through File > Open Project with computer use.
- Say which of these applies when it matters; never present untested paths as working.

## Preferences
Follow the user's own style preferences for tone and design. If they give no style, pick a plain, minimal default and say what you assumed in one line. Don't ask a pile of questions before the first version: build it with clearly labelled placeholder dimensions, then refine.

## 1. Set up once per session
1. **Models folder.** Ask the user once which folder their Studio projects live in and remember it for the session. Never guess a path or request a broad folder (home, Documents); ask for one dedicated folder. In Cowork, the user attaches it with the **Add folder** button (a native picker, nothing to type). Folder access is per folder, not per file.
2. **Settings source.** Look in the models folder for a `.3mf` saved from Bambu Studio with the user's printer, filament and process selected. If there is none, ask the user to open Studio, pick their printer and filament, and save an empty project into that folder. It carries their profile. If none exists, stop and ask; do not invent a config.
3. **Libraries.** Check `python3 -c "import trimesh, manifold3d, numpy"` on the machine that will run the build. In Cowork, Python is already part of the app's environment. If the libraries are missing, tell the user and ask before running `pip install --user --break-system-packages trimesh manifold3d numpy`.
4. **Work folder** `$HOME/work` on the machine that runs the build (never inside the models folder). Copy `build.py` from this skill's folder there. Backups go to `$HOME/work/backups`.
5. **Computer use** (needed for the reload). Do this during setup, before the first build, so the user can approve it while you work:
   - Load the `computer-use` skill if one is listed, and follow it.
   - If no `computer_*` tools are present, call the `enable__mcp__remote-devices__computer` tool once first (the computer tools arrive with it, possibly a turn later). Load the `computer_app_*` tools you need with one ToolSearch (`computer_resolve_access`, `computer_request_access`, `computer_app_list_windows`, `computer_app_menu`, `computer_app_screenshot`, `computer_wait`).
   - Two calls, in this order: `computer_resolve_access` with the app name `BambuStudio`, then `computer_request_access` with the entries it returned passed VERBATIM (bundleId, displayName, tier, isSentinel, plus willHide / screenshotFiltering / preferredModeDefault) and a one-sentence reason. A bare bundle id like `com.bambulab.bambu-studio` in `apps` is rejected. Check the result: `granted` must list Bambu Studio.
   - Access expires after about 30 minutes without computer-use activity. If any `computer_*` call says so, run resolve + request again.
   - If the user declines or it cannot be granted, say that in one line, finish the build and ask them to close and reopen the file.

## 2. Where the build runs
Build where the models folder is mounted, and write the `.3mf` straight into it.
- **Cowork session linked to the Mac:** run the build in the device shell (`device_bash`), where the folder shows up under `$HOME/mnt/<folder-name>`. Do NOT build in the cloud workspace and copy across with `device_commit_files`: its source folder syncs with a delay and silently wrote the previous version twice during testing. The device shell cannot launch Mac apps, so `open -a` does not work from there.
- **Local terminal on the Mac (untested):** run the same script locally. `open -a "BambuStudio" <file>` should open the file, but whether it refreshes an already open project is unverified. If it doesn't, ask the user to close and reopen it.
- **No folder connected:** build in the cloud workspace and send the file with `SendUserFile`, and tell the user once how to attach a folder.

## 3. The script
The build script is `build.py`, in the same folder as this SKILL.md. Copy it to `$HOME/work/build.py` on the machine that runs the build, then run:

    python3 $HOME/work/build.py <models-folder>/<name>.3mf <settings-source>.3mf

Iterate by changing the parameters at the top and re-running. Replace `build_body()` with the real design; leave the rest unchanged.

Why it is built this way (all observed in testing):
- A `.3mf` exported straight from trimesh has no Bambu config and Studio reports "The 3mf file has invalid config, load geometry data only". Copying `Metadata/project_settings.config` from a Studio-saved file fixes that and applies the user's profile.
- The existing output file is the settings source, so settings the user saves in Studio carry over a rebuild (verified for filament colour, seam position and support settings). The settings-source file is used only on the first build of a model.
- Studio stores numbers such as `printable_height` as strings in the profile; comparing them without `float()` crashed the first version of the script.

## 4. Design guidance
- Print without supports where possible: flat base, vertical walls, openings facing up.
- Fits: leave clearance as a named parameter. Starting points: 0.2-0.4 mm per side for snug fits, 0.5-1 mm for loose holders. Say these are starting points and test with a small fit piece when it matters.
- Anything that holds wet items needs drainage (holes or a perforated floor); keep the structure above it solid.
- Put every dimension in a named parameter at the top of the script.
- Confirm `is_watertight`, `extents` and the fit within the build volume after each build (the script prints them).

## 5. Real dimensions, not guesses
For real products, look dimensions up (spec pages from the manufacturer or retailers). Report which values are verified and which are placeholders, and ask the user to measure the widest point of anything unverified. Never present a placeholder as measured.

## 6. Deliver, verify, reload
1. Run the script so it writes straight into the models folder. Reuse the same file name every iteration. Write only the `.3mf` into that folder; no scripts, previews or temp files, and never touch other files there.
2. Verify on disk (`ls -l`, the script's printed extents and the "settings from" line) before saying it is updated.
3. **Reload in Studio, every time, including after the first build and after a change you consider small.** Studio does not watch files. Use computer use in the background so the user can keep working. "It's a new file" and "it's a small change" are NOT reasons to skip the reload:
   - List the app's windows. Studio reports many auxiliary windows (Settings, Colors, Send print job, ...) and the `is_main` flag is unreliable, so pick the window whose TITLE is the project name; a leading `* ` means unsaved changes. Always pass that window id when taking screenshots (the default can be an empty Settings window).
   - If the title shows `*`, do not close the project: closing raises a save prompt and the wrong answer loses the user's changes. Ask them to save (or save it for them if they say so, via File > Save Project; a greyed-out item means it is already saved), verify on disk, then continue.
   - **File is already open in Studio (the usual case):** File > New Project closes the loaded project. Reopening the same path directly does NOT refresh it. Then File > Recent projects: list the items first and press the one whose path matches the file. Do not assume it is item 1.
   - **File was never opened in Studio (first build of a new name):** it is not in Recent projects yet. Ask the user once to open it (File > Open Project, or double-click it in Finder). From then on it appears in Recent projects and every later change reloads without them. (Opening it yourself via the native file dialog is untested.)
   - Wait about 3 seconds, take a screenshot of the project window and check the shape matches the latest parameters. Screenshots sometimes fail or come back shrunken mid-transition; retry once and say so if the frame is not clean. If it still shows the old geometry, check the file on disk before blaming Studio.
4. **If the reload cannot be done**, say exactly which step failed (tools missing, access not granted or expired, window not found, unsaved changes) and ask the user to close and reopen the file. Do not present this as the normal flow, and do not stop trying after one failed call: fix the cause (for example redo resolve + request after an expiry) and retry once.

## 7. Settings and overwrite rules
- Only global settings the user has SAVED in Studio carry over a rebuild. Unsaved changes are lost.
- Per-object overrides are carried over by the script but untested; check them before relying on them.
- Studio edits to geometry (extra parts, moved objects, modifiers, painted supports, plate layout) are not preserved, because each rebuild regenerates the model. Say this once when starting an iteration loop. The script keeps a timestamped copy of the previous file in `$HOME/work/backups` before every overwrite.
- One object and one plate only. Multi-part or multi-colour models are out of scope for this script.

## 8. Replies
Short and direct. Lead with what changed, include only decisions that matter (design choices, what still needs measuring), state any assumption you made in one line, and give print settings only when asked or on the first print of a design.
