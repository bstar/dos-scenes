# OPL2 and clock compatibility

YM3812 writes require recovery time between selecting a register, sending its
data and the next write. The runtime retains six status-port reads after the
address and 36 after data, and additionally checks elapsed PIT channel 0counts.
`/SLOWOPL` doubles both recovery intervals. This changes the AdLib write path,
not the machine's CPU speed.

The runtime's mode 3 PIT counter decrements twice per input clock. Its default
14/68 count guards include margin beyond the card's address/data requirements.
A bounded polling loop disables only the extra clock guard if the counter fails
to advance; status-read delays remain. The detection-timer wait is guarded too.
The clock is latched, not reprogrammed, by each guard check.

IRQ 0at divisor 2131counts scene time and chains the previous BIOS-rate timer.
It performs no OPL writes, allocation, file access or scene rendering. Audio
uses absolute deadlines in the foreground and is serviced between rendering
and copy chunks. BIOS keyboard reads avoid redirected DOS-handle EOF artifacts.
Exit releases melodic and rhythm keys and attenuates every operator.

The resident frontend adds only request/idle bookkeeping to hardware handlers.
Actual scene activation runs from INT 28hon a private stack, with DOS reentrancy
and video-mode checks. It cannot guarantee activation inside a foreground game
that does not yield to DOS. Standard VGA 80×25text is required for its complete
text/font/palette/cursor preservation path.

References:

- [AdLib Music Synthesizer Card Programming Guide](https://franticware.github.io/miscellaneous/adlib-programming-guide.html)
- [Open Watcom interrupt-function documentation](https://open-watcom.github.io/open-watcom-v2-wikidocs/cguide.html)
- [Open Watcom linker documentation](https://open-watcom.github.io/open-watcom-v2-wikidocs/lguide.html)
- [Resident Programs, DOS reentrancy and INT 28h](https://flint.cs.yale.edu/cs422/doc/art-of-asm/pdf/CH18.PDF)

Logs describe intended software register writes and timer measurements. OPL2
registers are write-only; these are not hardware register readbacks or logic
analyzer measurements of the ISA bus. Faster/slower emulator cycle settings
exercise the guards but are not calibrated CPU MHz.
