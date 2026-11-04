# DOS Scenes

[![DOS build and tests](https://github.com/bstar/dos-scenes/actions/workflows/dos.yml/badge.svg?branch=main)](https://github.com/bstar/dos-scenes/actions/workflows/dos.yml)
[![Latest release](https://img.shields.io/github/v/release/bstar/dos-scenes)](https://github.com/bstar/dos-scenes/releases/latest)

Animated scenes for MS-DOS, with EGA graphics and AdLib OPL2 music. Run them as
a standalone app, an optional TSR screensaver, or inside another application.

<img src="docs/island.gif" width="640" height="400" alt="15-second DOS island animation at twice its native resolution">

## Download and run

Download [DOSSCENE.ZIP](https://github.com/bstar/dos-scenes/releases/latest/download/DOSSCENE.ZIP),
extract it into `C:\SCENES`, and run:

```dos
SCENE C:\SCENES\ISLAND
```

The release includes the island scene, three OPL2 songs with ocean sounds, and
an original Night Coast demo (`SCENE C:\SCENES\DEMO`). No installer or boot changes.
Checksums are included with the [release](https://github.com/bstar/dos-scenes/releases/latest).

The island has moving clouds, a setting moon, subtly twinkling stars,
shooting stars and summit fire, with subtle lights, water, and people walking
through town and up the mountain.

| Key | Action |
|---|---|
| `+` / `-` | Adjust volume; remembered between runs |
| `M` | Mute or restart music |
| `N` | Next song |
| `Esc` | Exit the standalone player |

## TSR screensaver

```dos
SCENETSR C:\SCENES\ISLAND /IDLE=120
```

Ctrl-Alt-S requests activation; `/IDLE=0` selects hotkey-only mode. The TSR waits
for a safe DOS idle point. `/OFF` disables it, `/ON` enables it, and `/STATUS`
shows its state. Reboot removes it; there is no automatic boot installation.

## Requirements

EGA/VGA and enough conventional memory; a 286 or faster is the practical target.
AdLib is optional. No FPU, EMS or XMS is required. `/SLOWOPL` adds extra AdLib
write delay for faster machines. The player was tested on a 386SX-16 with AdLib.

The TSR requires DOS 5+, standard VGA 80x25 text mode and about 102 KiB resident
memory, plus the scene's working memory. It defers during graphics or low-memory
conditions. TSR validation is currently through DOSBox-X.

## Build and extend

```sh
nix develop --command python3 tests/run.py
python3 tools/package.py
```

Or build with Open Watcom 2: `./build.sh --watcom /path/to/watcom`.
See the [scene format](docs/scene-format.md), [authoring guide](docs/authoring.md),
[AdLib timing notes](docs/timing.md) and [embedding API](docs/embedding.md).
[NETFTP](https://github.com/bstar/mTCP) embeds this runtime through a pinned submodule.

## Credits and license

Island artwork: *The Secret of Monkey Island*, Lucasfilm Games (1990).
Concept and presentation: [The Video Game History Foundation stream](https://www.youtube.com/watch?v=ikaqus5_QIg&t=10722s).

The included OPL2 treatments credit Barry Taylor (*Blow the Man Down*) and
Lesley Nelson (*Haul Away, Joe!* and *Homeward Bound*), with added ocean layers.
*Nelson's Blood* remains disabled. See [full credits and source links](scenes/island/CREDITS.md).

The code, tools and original Night Coast demo are [MIT licensed](LICENSE).
The island artwork and musical arrangements retain their original credits.
