# Settings menu sprint

**Status:** Proposed; documentation only. Implementation is not authorized yet.

## Goal

Add a Settings dialog accessible from the existing top-left dropdown, with a
shortcut manager and a recursive image-search toggle. Recursive search remains
enabled by default, preserving current behavior.

## Current implementation

- `src/plumpick/cull/cull_window.py` builds the top-left menu. On Windows it
  opens from the title-bar icon; other platforms use the Files menu.
- Keyboard bindings and clickable status-bar hints are defined separately in
  that window and are currently hardcoded.
- `src/plumpick/cull/library.py` always scans recursively. The library deliberately
  has no Qt dependencies.
- Recent folders and commit preferences already use `QSettings`.
- `src/plumpick/app/app.py` handles opening paths and activates an existing
  window when the requested folder is already open.

## Proposed user experience

### Entry point and dialog

- Add **Settings…** to the existing top-left dropdown.
- Use a dialog styled consistently with the application's theme.
- Provide **General** and **Shortcuts** tabs.
- Provide **OK**, **Cancel**, and **Restore defaults** controls.
- Stage edits locally: OK validates, saves, and applies them; Cancel discards
  edits, including any staged restoration of defaults.

### General: recursive image search

- Checkbox: **Include images in subfolders**.
- Default: enabled, including when no preference has been saved.
- Disabled: scan only images directly inside the opened folder.
- Persist the preference as an application-level setting, not in a folder's
  `.plumpick.json` session.
- Use the preference for every new library opened through folder selection,
  recent folders, drag-and-drop, or command-line paths (including image files).
- Preserve existing scan safety limits, ordering, and directory exclusions.

**Recommended behavior, pending approval:** changing this setting affects the
next folder opened, without rescanning existing windows. Explain this in the
dialog. Existing windows retain their images, marks, cursor, and undo history.
Opening a folder already open continues to activate its existing window rather
than rescanning it; close and reopen that window to use the new scan preference.

Session handling needs a regression check: a non-recursive scan must not cause
unintended loss of saved decisions for subfolder images. Decide how to preserve
out-of-scope marks before implementation; changing scan scope must not silently
erase those decisions on the next save.

### Shortcuts

- List next image, previous image, approve and advance, delete and advance,
  clear mark, toggle zoom, undo, redo, and commit.
- Support adding, replacing, and removing bindings, including multiple bindings
  per action and leaving an action unbound.
- Preserve the current runtime bindings as defaults, including navigation
  aliases and platform-standard undo/redo bindings.
- Detect conflicting bindings and prevent saving until they are resolved.
  Account for duplicate and prefix-ambiguous key sequences.
- Persist bindings by stable action identifiers, independently of display labels.
- Apply saved bindings to all active culling windows without restarting.
- Refresh visible shortcut hints alongside bindings so hints never advertise
  stale keys. Preserve clickable controls for actions that have no binding.
- Leave existing mouse controls unchanged.
- Ensure shortcut recording does not trigger culling actions underneath the
  settings dialog.

## Implementation plan

1. **Preferences:** add a shared application-preferences module using the
   existing `QSettings` organization/application. Define defaults, validation,
   persistence, and a settings-change notification for open windows. Allow
   isolated settings stores in tests.
2. **Shortcut registry:** centralize action identifiers, labels, default key
   sequences, and binding validation. Replace hardcoded bindings and drive
   shortcut hints from this registry. Dispose of old shortcuts when rebinding
   so repeated edits do not accumulate handlers.
3. **Settings dialog:** add a separate UI module for staged edits, shortcut
   capture, conflict feedback, defaults, and save/cancel behavior. Connect it
   to the existing menu.
4. **Scanning:** add an explicit recursive argument to `scan_folder`,
   `Library.from_folder`, and `Library.from_path`, defaulting to true for
   compatibility. Pass the application preference from the opening flow;
   keep `QSettings` and other Qt concerns outside the library.
5. **Regression checks and documentation:** test the behavior below and update
   user-facing instructions when the feature is actually implemented.

Proposed module responsibilities (final names may follow implementation style):

- `src/plumpick/app/preferences.py`: preference defaults and persistence.
- `src/plumpick/app/shortcuts.py`: shared shortcut definitions and validation.
- `src/plumpick/app/settings_dialog.py`: settings UI.
- Existing app, window, and library modules: integration only.

## Acceptance criteria and verification

- Settings is reachable through the existing top-left menu.
- A clean settings store yields current shortcut defaults and recursive search on.
- Preferences survive restarting; Cancel writes nothing.
- Restore defaults is staged and can be cancelled.
- Shortcut conflicts block saving with useful feedback.
- Saving a rebind removes the old binding, enables the new one, and updates
  hints in every open culling window; repeated saves do not duplicate actions.
- Shortcut capture does not navigate, mark, or commit images.
- Non-recursive scans exclude subfolder images; recursive scans retain existing
  ordering, exclusions, and safety behavior.
- All opening routes pass the scan preference, while opening an image still
  selects that image.
- Changing scan scope does not silently discard previously saved subfolder marks.
- Existing mouse controls, commit behavior, and regression tests remain intact.
- Automated tests use temporary preference stores rather than real user settings.
- Manually check menu access, dialog theme, shortcut editing, and window updates.

## Out of scope

- Implementing the feature as part of this documentation change.
- Automatic rescanning of active windows or background scanning.
- Mouse remapping, global OS shortcuts, or per-folder shortcut profiles.
- Broader redesign of the welcome screen, menus, or culling workflow.

## Decisions pending implementation approval

- Confirm the recommended next-open-only scan behavior.
- Choose a session-preservation strategy for marks outside the active scan scope.
- Confirm shortcut recording scope (single key combinations versus multi-step
  sequences) and how unbound actions appear in the compact status-bar hints.
