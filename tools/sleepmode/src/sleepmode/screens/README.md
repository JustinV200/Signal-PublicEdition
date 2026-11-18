# sleepmode.screens

Turns monitors off and on, and decides which display is the projector.

## Public API

- `ScreenPower(ddc, off_value, settle_s)`:
  - `power_off(monitors) -> list[MonitorResult]` sends DDC/CI power-off (VCP 0xD6) to each monitor. After `settle_s` it reads the power mode back. DDC/CI writes get no reply, so only a monitor that reads back an MCCS off mode (2 to 5) gets `DDC_OFF`. One that refused, switched itself back on, read back anything else, or couldn't be read gets `BLACK_WINDOW` with the reason. It never raises for a monitor.
  - `power_on(monitors) -> {device_name: error}` sends DDC power-on to each. It returns the ones that refused, and never raises for a monitor.
- `ddc`: the real calls, `read_power_mode(hmonitor)` and `set_power_mode(hmonitor, value)`, through dxva2 via ctypes with explicit signatures. They raise `DdcError`, or `ctypes.ArgumentError` for a handle ctypes can't pass. `Ddc` is the protocol fakes implement.
- `split_projector(monitors, name_match) -> (projector | None, others)` follows the whiteboard's rule: a name match, else the first non-primary display.
- `MonitorResult(device_name, friendly_name, method, detail, rect, is_projector)` and the methods `DDC_OFF`, `BLACK_WINDOW`, `NIGHT_SKY`.

## Depends on

`signal_displays` (`Monitor`, `pick_projector`) and the standard library (`ctypes`).
