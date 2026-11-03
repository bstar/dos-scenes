# Island pack

This pack reproduces the animated presentation used as the project's first
reference scene. See [CREDITS.md](CREDITS.md) for the video concept, original game,
all MIDI arrangers and source links. The ready-to-run assets and three OPL2
tracks are included under `pack/`. The original game files, video clips, MIDI
inputs and Furnace projects are not included.

Build the included pack:

```sh
python3 tools/pack_island.py
```

To regenerate it from your own locally extracted source assets:

```sh
python3 tools/pack_island.py --assets /path/to/extracted-assets
```

It writes `build/scenes/island`, including a clean background, dynamic moon,
foreground mask, fire/cloud/meteor sprites, walking routes and the three enabled
OPL2 tracks. Copy that directory to DOS and run `SCENE C:\SCENES\ISLAND`.
The existing volume file is not packaged or overwritten.

## Rebuilding local source assets

The extraction scripts work only on your own files and write ignored local
`assets/` and `research/` directories. They do not fetch or distribute game
media. The game extractor supports the English DOS EGA data edition identified
by its index hash. It can read an ordinary game directory:

```sh
python3 tools/extract_assets.py --game-dir /path/to/your/game --output assets
```

It can also use `mtype` from mtools to read a disk image:

```sh
python3 tools/extract_assets.py --image /path/to/your/disk.img \
  --offset YOUR_PARTITION_OFFSET --mtype mtype --output assets
```

The expected in-image directory is `GAMES/ADV/MONKEY/CGA`; use `--game-path` for your own layout. The EGA game data, not the directory name,
determines compatibility.

Cloud and meteor recovery use two local 1920×1080reference clips from the supplied
stream: the opening0–3minutes and17–20minutes. Preserve the native 5×pixel grid;
re-encoding or downscaling loses source dither. The source artwork is registered
at video origin160,40. Install NumPy and OpenCV on the host, then run:

```sh
python3 tools/recover_cloud_hd.py opening-1080p.mp4 minute17-1080p.mp4
python3 tools/extract_moon.py opening-1080p.mp4
python3 tools/prepare_effects.py
```

The runtime pack uses `ORIGINAL.EGA` as its clean `SCENE.EGA`; the moving moon is
composited separately, so no moon is left behind in the original sky. Cloud,
terrain and meteor recovery inputs remain local. The scene's original code/data definition is in
`details.json`; it supplies lights, routes and water motion to the generic engine.

For music, retain the original arrangement credits and source terms. Edit your
local OPL2 performances in Furnace, then export each project:

```sh
python3 tools/convert_furnace.py local-song.fur --output assets/SONG2.OPL
```

Use a different `--vgm` output for each project if retaining export metadata.
The three enabled files are `SONG2.OPL`, `SONG3.OPL`, `SONG4.OPL`. The historical
opening `INTRO.OPL`/Nelson's Blood remains disabled and is not required by the pack.

The optional `add_ocean_furnace.py` and `add_ocean_bed.py` tools preserve source
blocks and write separate Furnace232 projects with the original OPL2 surf and
steady-noise patches. They target the documented local project layout and reject
unsupported versions/arrangements. They contain no third-party song files or
General MIDI bank. Keep the original input project and its arrangement credits.
