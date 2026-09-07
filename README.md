# Pokémon Team Overlay v2

A free, locally run Pokémon portrait controller and transparent six-slot OBS
overlay. The entire app is contained in **pokemon_team.py**.

## Features

- Search the live SpriteCollab catalog by name or National Dex number.
- Choose base, regional, or alternate forms using repository form numbers.
- Enable **Shiny** for the selected Pokémon and form.
- Add, update, and clear six team slots.
- Instantly update an open OBS overlay through Server-Sent Events.
- Choose vertical, grid, or horizontal layouts.
- Save the team locally across restarts.
- Automatically choose another port if the default port is occupied.

## New in v2

- **Saved teams:** save up to 30 named teams and switch between them. Each is a
  snapshot including appearance, Nuzlocke stats, and hunt progress. Save again
  to update it; loading replaces unsaved changes in the active team.
- **Reordering:** drag a portrait onto another slot to swap. The Move menu also
  works with a keyboard or touch. Empty slots remain valid destinations.
- **Styling:** frame/tile colors, portrait size (40–240 px), spacing (0–40 px),
  hide-empty mode, and optional nickname/level labels. Click Apply styling.
- **Nicknames/levels:** enter an optional nickname and level, or click a slot's
  Edit button. Nicknames support 24 characters; levels support 1–100.
- **Nuzlocke:** enable the stats display; track deaths and badges; mark slots
  fainted to gray them out. A newly fainted Pokémon adds one death only while
  tracking is enabled. Reviving does not erase historical deaths.
- **Shiny hunting:** use the editor to set a target; count encounters with +1,
  −1, or H/Space/E. **The controller must be focused** and focus must be outside
  form controls. This is not a system-wide hotkey. Setting a new target resets
  the count; the target and counter can be shown in the overlay.
- **Import/export:** export the active team to share, or export a full backup
  with all saved teams. Import validates before saving. A team import preserves
  your saved teams; a full backup import replaces them. Older raw save files
  can also be imported. Maximum upload size: 500 KB.
- **Artist credits:** open Portrait artist credits and load the contributor
  records for the active team and hunt target. Named contributors are resolved
  from SpriteCollab's directory when available. Missing records remain linked.
- **Windows executable build:** run BUILD-WINDOWS.bat on Windows, or use the
  included GitHub Actions workflow. The resulting PokemonTeam.exe launches
  without Python installed on the recipient's computer. **The executable has
  not been built in this package; see WINDOWS-BUILD.md.**

## Updating from v1

Stop older app instances, copy your `pokemon-team-data.json` somewhere safe,
and replace the Python file in the same folder. Existing teams are supported.
Refresh the controller and **refresh the OBS Browser Source cache** so both
load the new JavaScript. Use the exact current URL printed by the server.

## Download and run

1. Choose **Code → Download ZIP** on this repository and extract it.
2. Install [Python](https://www.python.org/downloads/) 3.9 or newer if needed.
3. On Windows, double-click **START-WINDOWS.bat**. Alternatively, open a terminal
   in the extracted folder and run:

```sh
python pokemon_team.py
```

On macOS/Linux, use `python3 pokemon_team.py` if needed. You can also download
only `pokemon_team.py` using GitHub's **Download raw file** button and run it.
No pip packages, Node, API keys, account setup, or paid service are needed.
Internet access is required for uncached portraits and the repository catalog.

The controller opens automatically. Keep the terminal running. Copy the exact
**Controller** and **OBS URL** printed there. The default port is 8765, but it
may switch to 8766 or another free port. Avoid old bookmarked URLs after a change.

## OBS setup

1. Add a **Browser Source**, leaving **Local file** unchecked.
2. Paste the **OBS URL** printed by the app.
3. Set dimensions to match the layout selected in the controller:

| Layout | Width | Height |
| --- | ---: | ---: |
| Vertical | 88 | 528 |
| Grid | 264 | 176 |
| Horizontal | 528 | 88 |

The table above applies to default styling with no labels or counters. With
custom styling, hidden slots, Nuzlocke stats, or a hunt, use the dimensions
printed in the controller instead. They can change when your team changes.

The background is transparent; no chroma key is needed. Changing the layout
updates its content, but you must change OBS source dimensions yourself.
Controller and OBS must run on the same computer. Do not enter the file path
of the Python script into OBS.

Try Dex **52**, form **1**, to add Alolan Meowth. Try Dex **58**, form **1**, for
Hisuian Growlithe. Tick **Shiny** before adding to use its shiny portrait.
If that shiny portrait is unavailable, the existing team is preserved.
Shiny selection is saved per slot and synced to OBS. Existing saves load as
non-shiny by default. Blank or zero means base form. Missing explicit forms leave
the existing team unchanged. Form numbers are specific to SpriteCollab.

## Why there is a local server

OBS and a normal browser do not share localStorage or BroadcastChannel storage.
The included Python server synchronizes both using an HTTP API and live events.
It binds only to 127.0.0.1. This is not a public server or a multiplayer service.

GitHub stores and distributes this app. **GitHub Pages cannot run its Python
server**: it is [static hosting](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages).
Publishing this repository does not produce a hosted live controller.

## Troubleshooting

- **Port warning:** the app selected another port. Use the newly printed URLs.
- **Empty response:** stop older copies, restart, and read the startup checks.
- **Missing portraits:** check internet access and the Dex/form combination.
- **favicon.ico 404:** harmless; it only concerns the browser-tab icon.
- **Cannot save:** keep the app in a folder you can write to.
- **Python command missing:** install Python or try `py -3` on Windows.

Run a standalone local HTTP check:

```sh
python pokemon_team.py --self-test
```

Prevent automatic browser opening:

```sh
python pokemon_team.py --no-browser
```

For bug reports, include your OS, Python version, error text, and reproduction
steps. Remove personal folder paths and private information before posting logs.

## Saved data

The app creates `pokemon-team-data.json` beside the script. Back it up to retain
your team. Stop the app before moving that file to reset the team. It is excluded
by `.gitignore`; do not upload personal save files through GitHub's web uploader.
No downloaded art, personal team data, or credentials are bundled here.

## Development and verification

HTML, CSS, JavaScript, and server code live in `pokemon_team.py`. The `ASSETS`
dictionary contains the browser files. Edit those strings to change the interface.

```sh
python -m unittest -v
python pokemon_team.py --self-test
```

Automated tests cover independent live-event clients, persistence, concurrent
slot updates, clearing, invalid input, and foreign-origin rejection. Chrome tests
previously verified catalog search, base/regional portraits, cross-tab updates,
missing forms, reload, and layout dimensions. The user confirmed Windows startup,
page loading, and live-event connection after the port fix. OBS itself has not
been directly tested by the developer in this environment.

## License and artwork

Application code: [MIT](LICENSE), free to use and modify.
Artwork: separate SpriteCollab terms, including attribution and non-commercial
restrictions. See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) before streaming.
This is an unofficial fan project.

## v2 validation

See [TEST-RESULTS.md](TEST-RESULTS.md) for automated coverage and the remaining
browser/Windows testing limitations.
