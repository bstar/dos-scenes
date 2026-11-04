# Scene pack format

All binary integers are little endian. Canvas coordinates are native320×200
pixels; palette indices are0..15 and transparent sprite pixels are255. DOS
filenames should fit8.3. Runtime files are limited to60,000bytes each.

| File | Format |
|---|---|
| `SCENE.EGA` | Four 8,000-byte planes, plane 0 first;40 bytes per row, MSB left pixel |
| `SCENE.CFG` | ASCII key/value lines; comments start with `#` |
| `PALETTE.BIN` | Sixteen 6-bit EGA palette-register values |
| `SKY.MSK` |8,000 bytes,1 bit/pixel; set bits allow cloud/moon/meteor drawing |
| `CLOUD.BIN` | `<u16 width,u16 height,i16 initial_x,u16 top>` then indexed pixels |
| `CLOUD.MOT` | `<u16 spacing,u16 numerator,u16 denominator,u32 cycle_ticks>` |
| `FIRE.BIN` | `<u16 width,u16 height,u16 frames>` then opaque indexed frames |
| `MOON.BIN` | `<u16 x,u16 y,u16 width,u16 height>` then indexed pixels |
| `TWINKLE.BIN` | `TWK1`, u16 count, then 12-byte star dimming records |
| `STAR1.BIN`, `STAR2.BIN` | Meteor sequence, described below |
| `PLAYLIST.CFG` | One local8.3 OPL filename per line; `#` disables a line |
| `*.OPL` | Repeated `<u16 delay_before_write,u8 register,u8 value>` |
| `DETAILS.BIN` | Lights, individual walking routes, and water ripples |

An optional `TWINKLE.BIN` contains up to 64 records:
`<u16 x,y,period,phase,duration,u8 original_color,dim_color>`. A point changes
only when `(ticks+phase)%period < duration`, its clean background has the
specified original color, and it belongs to `SKY.MSK`. Coordinates and colors
are validated; duration must be positive and shorter than the period. Twinkles
render before the moon, clouds and meteors, preserving their occlusion. Without
this file, the sky is unchanged. The island briefly switches 12 larger stars and 8 small cyan pinpoints to
sampled local sky colors, then restores their original pixels. Larger stars
blink for about 0.34 seconds and smaller stars for about 0.26 seconds. A shuffled
eight-second schedule gives each star a separate slot: only one star blinks
at a time. Center and halo records share a phase. The palette registers are unchanged.


The clean background must contain the sky beneath the moon. Clouds render after
the moon and are clipped by `SKY.MSK`; terrain occludes both. Animation uses
elapsed scene ticks rather than rendered frame count, except sprite-frame fire.
The nominal audio/scene clock is1193182/2131 Hz, approximately 559.916 Hz.

`SCENE.CFG` accepts `NAME`, `FIRE_X`, `FIRE_Y`, `FRAME_TICKS`, `MOON_SECONDS`,
`MOON_DX`, and `MOON_DY`. Defaults are a 40-tick frame interval, fire at0,0, and
a 3600-second moon arc with displacement88,80. The moon uses a 33-sample projected
quarter-circle lookup table; it stops drawing after that interval, rather than
wrapping. `MOON_SECONDS` accepts1..86400. The interval uses nominal560Hz ticks,
so the default is approximately one hour on the actual PIT rate.

Meteor headers are `<u16 count,u16 period_ticks,u16 phase_ticks>`. Each frame is
`<i16 x,i16 y,u16 width,u16 height,u16 hold_ticks>` followed by indexed pixels.
At most 64 frames per sequence are accepted.

## Detail records

`tools/scene_format.py` provides a serializer. The header is ASCII `DSD1`, then
three u16 counts: lights, routes, ripples. Bounds are128 lights, 32 routes and 128 ripples.
Missing details/music/sprite files simply omit those optional effects.

Each 12-byte light is `<u16 x,y,period,phase,dim_duration,u8 color,reserved>`.
It replaces one pixel when `(ticks+phase)%period < dim_duration`; otherwise the
clean background remains. Different periods/phases avoid synchronized blinking.

Each route starts with 16 bytes:

```
u16 point_count, step_ticks, offscreen_pause_steps, initial_phase,
    direction_salt, two_pixel_cutoff_y
u8  body_color, head_color
u16 allowed_background_palette_mask
```

It is followed by `point_count` pairs of `<u16 x,u16 y>`. Each route is one
person. Adjacent points should be no more than one native pixel apart. After a
one-way trip the person disappears for the specified pause; a mixed journey
counter chooses the starting endpoint for the next trip. Consecutive journeys
may use the same direction. Initial phases can place people throughout a scene.
Below the cutoff, the point is a single head pixel; above it, the point anchors
the feet and the head is one pixel higher. The palette mask controls independent
body-pixel occlusion against the clean background. For example, mask 3 allows
only original palette 0/1, preserving bright building detail in front of walkers.

Each 18-byte ripple is `<u16 x,y,width,step_ticks,phase,period,duty_period,
active_steps,u8 color_a,color_b>`. It moves one pixel through the registered row,
only swapping the two allowed background colors during active duty phases.

## Audio and settings

An OPL file contains delay-before-write YM3812 events, with no MIDI parser on
DOS. EOF moves to the next enabled playlist entry; the final entry wraps.
Up to 16 streams are preloaded. Validate streams and explicitly release melodic
and rhythm keys at the end. `tools/convert_furnace.py` exports a local Furnace
OPL2 performance through VGM and appends a clean release interval.

`VOLUME.CFG` is a single ASCII integer0..32. It is created by the runtime only
after a volume adjustment. `VOLUME.BAK` and `VOLSET.TMP` are reserved companion
files. Do not include a user's setting when packaging or updating a scene.
