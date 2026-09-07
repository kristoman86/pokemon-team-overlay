# v2 test results

## Passed in the authoring environment

- Seven Python tests: live HTTP/SSE integration with separate clients; old-save
  migration and shiny validation; saved-team independence/load/delete/restart;
  nickname/level storage; fainted status and historical death counts; atomic
  concurrent encounter increments; full-backup and team import round trips;
  invalid import preserving the existing file; style input bounds.
- Node tests against JavaScript extracted from the single-file app: base and
  regional shiny URLs, missing shiny handling, base fallback, and exact computed
  dimensions for customized layouts with labels, Nuzlocke stats, and hunt display.
- Python HTTP startup self-test and JavaScript syntax check.
- Browser: expanded UI loaded, Bulbasaur was added with nickname Sprout and
  level 25, and moved from slot 1 to slot 3 through the Move menu; the live overlay
  reflected the move. Later browser actions applied size 96, gap 12, hide-empty,
  labels, and saved QA Team, as verified in the preview server's saved state.

## Not fully verified

The browser connection timed out during the saved-team load confirmation.
Subsequent browser tab operations timed out, so pointer drag-and-drop, the
remaining dialogs, browser file import/export, keyboard counter behavior,
artist-credit UI, and final visual inspection were not fully verified end to
end. Their implementations are included; server-side behavior has automated
coverage as listed above. No synthetic test team is shipped.

The Windows EXE build and GitHub workflow have not run here because a Windows
runner is unavailable. The workflow runs tests and the compiled app's HTTP
self-test before exposing an artifact. No new v2 OBS test has been performed.
