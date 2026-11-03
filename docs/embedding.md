# Cooperative embedding

Compile `src/runtime.c` with `DOS_SCENES_EMBEDDED`, large-model real-mode C, and
include `src/dos_scenes.h` in the host. This suppresses the standalone entry
point and exposes `dsBegin`, `dsStep`, `dsEnd`, `dsKey`, `dsGetVolume`, and
scene counters/errors. Do not maintain a separate copy of the renderer.

- `dsBegin(directory)` validates/loads a pack, detects AdLib, enters EGA mode and
  starts the scene clock. It returns 0 on failure and releases partial allocations.
- `dsStep()` services audio and renders when a frame is due. Call frequently
  from the application's foreground loop, between other work.
- `dsKey(key)` consumes `+ - = _ M N` during an active scene. Other keys return 0
  so the host can apply its wake policy.
- `dsEnd()` stops/silences the scene, flushes a pending volume setting, restores
  its previous timer vector/configuration, and releases scene allocations.
- `dsGetVolume()` reports the current master level. `dsFrames`, `dsSceneTicks`,
  `dsAdlib`, `dsError`, and `dsFault` provide diagnostics.

The host must save and restore any text framebuffer, font, palette or cursor
that it wants preserved; `dsEnd` restores video mode, not a host's customized
text contents. The resident frontend implements that preservation for DOS idle
activation. Do not call the renderer or file operations from hardware IRQs.

The runtime expects the standard BIOS PIT configuration on entry, temporarily
programs channel 0and IRQ 0, and chains the former handler at BIOS frequency.
Applications that already own a different PIT schedule need an explicit adapter.
The embedded mode should run only while the host can give the display to a scene.

## mTCP / NETFTP

The mTCP fork keeps its own GPL dashboard and wake policy. Its dependency is a
pinned checkout of https://github.com/bstar/dos-scenes, not a renderer copied
into the FTP source tree. Initialize the submodule before building:

```sh
git submodule update --init --recursive
nix develop path:./nix --command python3 tools/build.py
```

The build compiles this runtime with the same real-mode model as FTPSRV and
links it into the server. `DOS_SCENES_SOURCE` can point to another `src`
directory during development. The server uses the cooperative API, not the TSR.
A client connection or wake key ends the scene before normal FTP interaction;
the server keeps polling packets between scene steps. Volume files remain in
the private scene directory and are not part of engine deployments.

The integration remains GPL with mTCP; the reusable original runtime remains
MIT in this repository. See the integration PR for the pinned source revision.
