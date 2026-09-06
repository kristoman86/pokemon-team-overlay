# Pokémon Team Overlay

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
