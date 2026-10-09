# Migration sources

This folder records the sources of materials imported from the [ParMA Inria website](https://team.inria.fr/parma/) on 8 October 2026.

- `assets.json`: the sources of the banner photograph and logo used on the site.
- `member-portraits.json`: a reference catalogue of personal pages, portrait sources and available credits. It records remote images and local copies; the editable `photo` values are in `content/team.json`.
- `seminar-original.json`: a structured copy of the programme at the time of migration, preserved as a historical reference. Leave this original snapshot unchanged when updating the programme.

These files **do not generate the pages**. To update seminar dates, talks and abstracts, edit `content/seminar.json`. To change member portraits, edit `photo` in `content/team.json`:

- Prefer a direct HTTPS image address from the person's website. It loads remotely and follows updates made at that same address, subject to browser caching.
- If the website blocks direct loading or only serves HTTP, use a local copy in `assets/images/members/`, with a value such as `"assets/images/members/firstname-lastname.jpg"`. Local copies must be replaced manually when the photograph changes.
- Use `null` if no photograph is available; the member's initials will appear.

Keep the original source and any credits in `member-portraits.json` when adding a local copy. To change the banner photograph or logo, use `assets/images/`.

The original materials retain their terms of use. The migration does not assign a new licence to scientific texts, photographs or the logo.
