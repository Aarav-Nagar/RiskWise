# RiskWise legal site

Static, self-contained pages for the App Store-required Privacy Policy and Terms URLs.
No build step, no dependencies — three HTML files: `index.html`, `privacy.html`, `terms.html`.

## Before publishing
- Replace `CONTACT_EMAIL_PLACEHOLDER` in `privacy.html` with a real support/contact email.
- Get a final legal review (these are drafts adapted from `docs/PRIVACY_POLICY.md` and `docs/TERMS_AND_DISCLAIMER.md`).

## Fastest free hosting — GitHub Pages
The `RiskWise` repo is already on GitHub. Two options:

**A. Serve this folder from a branch (cleanest URL)**
1. Push a branch (e.g. `gh-pages`) whose root contains these three files, **or** move them to `/docs` on `main`.
2. GitHub → repo **Settings → Pages** → Source: the branch + folder.
3. URLs become:
   - Privacy: `https://<user>.github.io/<repo>/privacy.html`
   - Terms: `https://<user>.github.io/<repo>/terms.html`

**B. Your GitHub Student Pack Namecheap domain**
Point the domain at GitHub Pages (CNAME) for a branded URL like `https://riskwise.<you>.com/privacy.html`.

## Where these URLs go
- **App Store Connect → App Privacy → Privacy Policy URL** → the `privacy.html` URL (required).
- **App Store Connect → App Information → Terms of Use (EULA)** → the `terms.html` URL (or link in the description).
- **In-app**: link both from the Profile screen (recommended, and required for account-based apps).
