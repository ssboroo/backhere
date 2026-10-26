# BackHere 0.4.0

Return to your files, pages and next steps with a small native Windows app.

- Unified bookmark/return logo across the app, tray, installer and website.
- Native light, dark and system themes; 12 languages.
- Global shortcut, best-effort browser/Explorer/Office capture and manual fallback.
- Local SQLite notes; JSON export/import and seven daily recovery snapshots.
- Single instance, optional Windows startup and system tray.
- Separate Windows x64 and x86 installers and portable builds, with SHA256 hashes.

## Downloads

- Windows 10/11 64-bit: use `BackHere-Setup-0.4.0-x64.exe`.
- Windows 10 32-bit: use `BackHere-Setup-0.4.0-x86.exe`.
- Portable ZIPs include a standalone executable and instructions; no Python installation required.

The installers and executables are not publisher-signed. Windows may display an unknown-publisher warning. Automatic capture depends on the source application's UI/COM support; manual entry remains available. Native document positions are reminders rather than guaranteed cell/page restoration. x86 runs were verified on 64-bit Windows using WOW64; a separate real 32-bit OS test remains necessary.

Both architectures pass core/native API tests, UI and theme tests, packaged-executable self-tests, installer tests and uninstall tests before these release files are published. Code signing, automatic binary updates and paid licensing are not included in this version.
