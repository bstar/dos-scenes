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
MIT; the island extraction outputs are external material and stay local.
