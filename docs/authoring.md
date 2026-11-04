# Adding a scene

Start with `tools/make_demo.py`: it generates a complete original background,
mask, crescent moon, cloud, detail table and OPL motif without external media.
Use `tools/scene_format.py` to encode planar pixels and detail records.

1. Put a clean320×200background in `SCENE.EGA` and define a16-entry EGA palette.
2. Mark only sky pixels in `SKY.MSK`; terrain and structures should stay clear.
3. Add optional cloud, fire, moon and meteor files with their local origins.
4. Trace walking routes in native pixels. Keep feet on ground; use the palette
   mask to put bright foreground details in front of individual body pixels.
5. Add independent, slow light phases and narrow water rows. Prefer sparse
   motion over redrawing large dithered regions.
6. Add only music you are entitled to use to `PLAYLIST.CFG`, preserving credits.
7. Test with `SCENE directory /AT=seconds /FRAMES=4 /DUMP` at early and late
   times. Then test the resident lifecycle and the host embedding separately.

Keep licensing/provenance with each pack. Code licensing does not replace a
scene's artwork or music terms. Generated assets from the original demo are
MIT; the bundled island artwork and musical arrangements keep the credits
listed in `scenes/island/CREDITS.md`. Raw game, video and MIDI inputs stay local.

## README animation

After building with the verified SDK, run:

```sh
nix develop .#preview --command python3 tools/record_preview.py
```

This records 15 seconds of the actual DOS renderer, samples its native planar
pages, and writes a losslessly optimized 320x200 GIF to
`build/preview/ISLAND.GIF`. It checks decoded GIF pixels and the exact duration.
`docs/island.gif` is a browser-compatible animated GIF with lossless nearest-
neighbor pixel doubling to 640x400. Every 2x2 block is checked against the native
frame. This avoids SVG embedded-animation inconsistencies and GitHub stripping
pixel-scaling CSS. No image quantization or lossy GIF compression is applied.
