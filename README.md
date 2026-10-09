# ParMA — project guide

Website for the ParMA research team at Inria Saclay, CNRS and Université Paris-Saclay.

**Live site:** [parma-inria.github.io](https://parma-inria.github.io/) · **Project:** [GitHub](https://github.com/parma-inria/parma-inria.github.io)

## Which file should I start with?

| I want to change… | Open… |
| --- | --- |
| Home page introduction and research topics | `content/home.json` |
| Members' names, roles, institutions, personal websites and photographs | `content/team.json` |
| Seminar dates, programme, abstracts and archive | `content/seminar.json` |
| Summary of the next session on the home page | `content/seminar.json` → `sessions` (generated automatically) |
| Email addresses, postal address and contacts | `content/contact.json` |
| Banner titles, menu and footer | `content/site.json` |
| Colours, banner dimensions and page layout | `assets/css/site.css` |
| Banner photograph and logo | `assets/images/` |
| A page's HTML structure | `templates/pages/` |
| Shared elements and cards | `templates/partials/` |
| Member search and mobile menu | `assets/js/site.js` |

For everyday updates, start with **`content/`**. Pages in **`public/`** are generated automatically: any changes made there will be overwritten the next time the site is generated.

## Working in VS Code

Open this folder as your project. You only need **Python 3.10 or later**; no npm, additional Python packages or extensions are required.

1. Open the file listed in the table and save your changes.
2. From **Terminal → Run Task**, choose **ParMA: anteprima locale** (local preview).
3. Open [the preview in your browser](http://127.0.0.1:8765/). After saving further changes, refresh the page: the site is regenerated automatically.
4. Before publishing, run **ParMA: controlla il sito** (check the site). This generates the pages and reports any missing local links or images.

To stop the preview, press **Ctrl+C** in its terminal. **Ctrl+Shift+B** runs **ParMA: genera il sito** (generate the site) without opening the browser.

You can also run the same tools from the project terminal:

```sh
python tools/build.py
python tools/check.py
python tools/preview.py
```

If the preview port is already in use, run `python tools/preview.py --port 8770` and open `http://127.0.0.1:8770/`.

## Examples of common changes

### Adding a member or their personal website

In `content/team.json`, find the appropriate group and add an object to its `members` list:

```json
{
  "name": "Firstname Lastname",
  "affiliation": "Inria, CR",
  "url": "https://esempio.fr/",
  "photo": null
}
```

Use `"url": null` if the person has no website. If a URL is provided, their name automatically becomes a clickable link. Groups and members appear in the order used in the file; **Former members** remains visible at all times, using the same format as the other sections.

Set `photo` to the direct HTTPS address of the image on the member's personal website, for example `"photo": "https://example.org/photo.jpg"`. Use the image address, rather than the address of the page containing it. The browser loads portraits directly from those websites; the build does not download or copy them into the project.

If the person replaces the image at the same address, their updated photograph appears on ParMA once the browser's cached copy expires or is refreshed. If the image address changes, update `photo` in this file. Use `"photo": null` when no suitable image is available. While a photograph loads, or if the external website cannot serve it, the card displays the member's initials.

In JSON files, keep the quotation marks and commas: commas separate items, but there must be no comma after the last item in a list. Use `[]` for an empty list.

### Updating the seminar

**Only edit `content/seminar.json`.** It contains the organisers, venue, labels and a single `sessions` list. Each date appears once, using the `YYYY-MM-DD` format. The same entry supplies the programme page, yearly calendar, archive and next-session announcement on the home page.

To add a session, insert an object into `sessions`:

```json
{
  "date": "2027-07-05",
  "room": "3L15",
  "talks": [
    {
      "time": "10:00",
      "speaker": "Firstname Lastname",
      "title": "Presentation title",
      "abstract": [
        "First paragraph of the abstract.",
        "Second paragraph, if needed."
      ]
    }
  ]
}
```

Add another object to `talks` for a second presentation. Keep `abstract` as a list of paragraphs; use `[]` if no abstract has been provided. To reserve a date before the programme is ready, use `"talks": []` in the session. Update that same entry when the speakers are confirmed, rather than adding the date again. An empty `room` omits the room from that session's heading.

The build automatically selects the earliest session on or after its date, including planned sessions whose programme has not yet been announced. It derives the calendar and September-to-August academic years from the dates, and groups completed sessions with talks into the archive. The file is arranged with recent dates first for convenience; the build sorts dates itself.

These selections are calculated **when the site is generated**, using that day's date. The published pages update when you regenerate and publish the site; time passing by itself does not rebuild them. You do not need to move old sessions manually or edit `content/home.json` when the programme changes.

### Changing the banner image and height

Replace `assets/images/mountains.jpg` with the new photograph, keeping the same filename. In `assets/css/site.css`, find the **Banner** section: `.hero-home` controls the home page banner height, while `.hero` controls the banner height on other pages. `background-position` determines which part of the image is shown. Further down, you will find rules for tablets, phones and printing.

## How are the folders organised?

```text
parma-site/
├── README.md                 ← this guide
├── content/                  ← content to update
├── templates/
│   ├── layout.html           ← shared HTML document
│   ├── pages/                ← home, members, seminar and contacts
│   └── partials/             ← menu, banner, footer and cards
├── assets/
│   ├── css/site.css          ← styling
│   ├── js/site.js            ← menu and search
│   └── images/               ← banner, logo and icon
├── tools/
│   ├── build.py              ← generates public/
│   ├── check.py              ← checks local files and links
│   └── preview.py            ← starts the preview
├── docs/sources/             ← sources of imported materials
├── tests/                    ← automatic seminar and portrait checks
├── public/                   ← generated site, excluded from Git
├── .vscode/                  ← project tasks and settings
└── .github/workflows/        ← automatic publishing
```

Templates use placeholders such as `$introduction` and `${prefix}`. The build tool inserts the JSON content and calculates relative paths. Seminar dates and scientific texts come from `content/seminar.json`; the HTML structure is in `templates/pages/` and `templates/partials/`.

The four pages retain the URLs `/`, `/team-members/`, `/francais-gdt-edp-ot-ml/` and `/contact/`. The `/en/` versions are generated from the same content.

## Publishing a change

In VS Code's **Source Control** panel, review your changes, write a short description, create the commit and use **Push**. When changes are pushed to `main`, GitHub generates the site, checks its links and publishes **only `public/`**. You do not need to upload the generated pages manually.

On GitHub, the **Actions** tab shows the result of the **Pubblica il sito ParMA** workflow (publish the ParMA site). The source in **Settings → Pages** must be **GitHub Actions**. A proposed change on another branch is checked before it is published on `main`.

The local check verifies pages, images and site sections; when you change links to external websites, check them in your browser. GitHub also runs the checks in `tests/` before publishing. These use example data, so you can update the programme freely.

## Original materials and documentation

The migration preserves the scientific texts, personal links and materials from the [original Inria site](https://team.inria.fr/parma/). Their sources are documented in `docs/sources/`; that folder does not supply content to the site. Photographs, the logo and texts remain subject to their original terms of use.

The site uses HTML, CSS, JavaScript and Python's standard library. It includes no analytics, external fonts or tracking tools.

Technical references: [publishing with GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site), [uploading generated pages](https://github.com/actions/upload-pages-artifact), [deploying the artifact](https://github.com/actions/deploy-pages).
