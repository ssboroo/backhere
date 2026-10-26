# BackHere product and download website

English/Mongolian static site. App UI supports 12 languages.

Local preview: `python -m http.server 8080 --directory website`.

Public installers, portable ZIPs, checksums and brand kit live in GitHub Releases. Links are pinned to v0.4.0, not short-lived workflow artifacts. Privacy and limitations are disclosed on the website. No analytics, account creation or payment collection.

When releasing a new app version, update download URLs and version copy together only after the release assets exist. The `.openai/hosting.json` used by the hosting checkout is intentionally separate from the Windows repository root.
