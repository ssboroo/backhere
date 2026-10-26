# BackHere 0.5.1 — Workspaces

- Save named Windows workspaces with running application windows, sizes, positions, minimized/maximized state and supported file/URL details.
- Review every window, choose which to restore, cancel between opens, and inspect individual restoration results. Existing windows are preserved; existing matching windows are repositioned without changing their documents/tabs.
- Explorer folder and saved Word/Excel document capture; best-effort active browser URL capture. Unsupported apps retain their executable and window layout.
- Optional local automatic snapshots every five minutes (latest 20 automatic snapshots retained).
- Browser Companion ZIP for Chrome/Edge/Brave/Vivaldi/Opera: export regular HTTP/HTTPS tabs, import them into a captured desktop workspace, or restore pinned/active tabs through the companion. Load-unpacked installation instructions are inside the ZIP.
- Explicitly confirmed Windows Hibernate action for continuing the current Windows memory session, if supported/enabled. Hibernate is not a collection of independently restorable historical RAM snapshots.
- Workspace data included in JSON backups and SQLite recovery snapshots; legacy note backups still import.

## Downloads

Windows 10/11 64-bit: `BackHere-Setup-0.5.1-x64.exe`.
Windows 10 32-bit: `BackHere-Setup-0.5.1-x86.exe`.
Portable ZIPs need no Python installation. SHA256SUMS.txt covers every public artifact.

## Restoration scope

Workspace snapshots do **not** capture application RAM, unsaved text, document edits, browser forms/history, terminals, authenticated sessions, or arbitrary application internals. Saved document paths and sheet names are hints; page/cell/cursor restoration is not guaranteed. Supported apps may recover their own content separately. Browser tabs require the companion for complete exported HTTP/HTTPS tab lists; ordinary capture sees at most the visible active URL. Desktop restore does not apply pinned/active flags; companion restore does. Store sensitive URLs/document paths and backup files privately: they are local plain-text data. No cloud sync or account is required.

New workspace UI is translated in Mongolian and English; other existing app locales currently use English for these new explanations. Existing translations remain available.

Executables/installers are unsigned. Code signing, automatic binary updates and paid licensing are not included. x86 CI runs under WOW64; a separate real 32-bit Windows OS test remains necessary. Both build architectures must pass unit/native tests, UI smoke tests, frozen executable tests and installer/uninstaller tests before publishing. Tests never execute Hibernate.
