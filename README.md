# ParMA — project guide

Website for the ParMA research team at Inria Saclay, CNRS and Université Paris-Saclay.

**Live site:** [parma-inria.github.io](https://parma-inria.github.io/) · **Project:** [GitHub](https://github.com/parma-inria/parma-inria.github.io)

## Which file should I start with?

| I want to change… | Open… |
| --- | --- |
| Home introduction and seminar summary | `content/home.json` |
| Recent papers and HAL settings | `content/publications.json` (updated automatically) |
| Members' names, roles, institutions, personal websites and photographs | `content/team.json` |
| Seminar dates, programme, abstracts and archive | `content/seminar.json` |
| Summary of the next session on the home page | `content/seminar.json` → `sessions` (generated automatically) |
| Email addresses, postal address and contacts | `content/contact.json` |
| Banner titles, introduction paragraphs, menu and footer | `content/site.json` |
| Shared Google Maps location | `content/site.json` → `map` |
| Colours, banner dimensions and page layout | `assets/css/site.css` |
| Banner photograph and logo | `assets/images/` |
| Complete HTML for each page | `pages/home.html`, `team.html`, `seminar.html`, `contact.html` |
| Header, footer, member cards or archive layout | The relevant complete HTML file in `pages/` |
| Member search and mobile menu | `assets/js/site.js` |

For data updates, start with **`content/`**. For page layout and HTML, start with **`pages/`**. Pages in **`public/`** are generated automatically: any changes made there will be overwritten the next time the site is generated.

## Working in VS Code

Open this folder as your project. You only need **Python 3.10 or later**; no npm, additional Python packages or extensions are required.

For the quickest local preview on Windows, double-click `Open local preview.cmd` in this folder. It builds the site and opens your browser. Keep its terminal window open while using the preview; closing it stops the local server. If this project's preview is already running, the launcher reopens it.

The files in `pages/` are editable source documents. To view the rendered site, use the local preview rather than opening those source files directly.

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

For photographs, use one of these options in the member's `photo` field:

- **Remote photograph, preferred:** set `"photo": "https://example.org/photo.jpg"` to the direct HTTPS image address on the member's personal website. Use the image address, rather than the address of the page containing it. The browser loads the photograph directly from that website; the build does not download it.
- **Local copy:** when a website blocks direct image loading or only offers HTTP, save a copy in `assets/images/members/` and set, for example, `"photo": "assets/images/members/firstname-lastname.jpg"`. Supported formats are JPG, JPEG, PNG, WebP and GIF. Replace that file when the photograph needs updating.
- **No photograph:** use `"photo": null` to show the member's initials.

Remote photographs update when the person replaces the image at the same address, once the browser's cached copy expires or is refreshed. If the image address changes, update `photo` in this file. Local copies need to be updated manually. While any photograph loads, or if it cannot be loaded, the card displays the member's initials.

In JSON files, keep the quotation marks and commas: commas separate items, but there must be no comma after the last item in a list. Use `[]` for an empty list.

### Recent publications

The home page displays the three newest unique ParMA records from the linked HAL search, including preprints. The settings and saved cards are in `content/publications.json`. The source uses ParMA structure ID **1184761** and the same `publicationDate_tdate desc` ordering as the full HAL list. Records with a date after today are excluded. HAL affiliation defines the team source, so adding a new author does not require changing a second author list.

GitHub checks HAL every day at **05:17 UTC**, and whenever the site is published. It saves new cards to the repository and records a successful check once a month, so the snapshot stays useful and a monthly successful check records repository activity. The workflow does not create a new commit for an unchanged daily check. GitHub may delay scheduled jobs.

Dates retain HAL's precision: a record containing only a year is shown as a year. The order returned by HAL is preserved, including ties. HAL's search date may represent the publication, writing or deposit date according to the document type; it does not always mean publication in a journal. Preprints without a journal or conference are labelled **Preprint**. Versions and records sharing a DOI count once. The source covers records affiliated with ParMA; a member's paper that omits this affiliation in HAL will not appear automatically.

If HAL is temporarily unavailable or returns fewer than three eligible papers, the previously saved cards remain available. Local builds and previews read this saved JSON and do not need a network connection. To refresh it manually, run `python tools/update_publications.py`.

### Introductions and maps

The paragraph under each page title is edited in `content/site.json` → `pages` → `hero.lead`. The repeated introduction boxes have been removed. The unique, longer home introduction remains in `content/home.json`.

The seminar and contact pages share one Google Maps configuration in `content/site.json` → `map`. Both point to **Building 307, rue Michel Magat, Orsay**. The iframe uses the institute's public Google Maps sharing URL, without an API key. The HTML and map dimensions remain editable in the two page files and shared stylesheet.

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

Archive years are collapsible: click a year to open or close its sessions. Former team members remain visible on the team page.

The build automatically selects the earliest session on or after its date, including planned sessions whose programme has not yet been announced. It derives the calendar and September-to-August academic years from the dates, and groups completed sessions with talks into the archive. The file is arranged with recent dates first for convenience; the build sorts dates itself.

These selections are calculated **when the site is generated**, using that day's date. GitHub's daily workflow regenerates the published site, and every pushed change also rebuilds it. You do not need to move old sessions manually or edit `content/home.json` when the programme changes.

### Changing the banner image and logo

Replace `assets/images/mountains.jpg` with the new photograph. In `assets/css/site.css`, `.hero.hero-home` sets the home banner height and keeps the bottom of the photograph visible. On smaller screens, the photo fits the screen width and sits below the banner text, so the landscape is less cropped.

The original team logo is `assets/images/parma-logo.png`. It is used in the header, footer and browser icon. `.brand-logo` controls its displayed size.

## How are the folders organised?

```text
parma-site/
├── README.md                 ← this guide
├── Open local preview.cmd    ← double-click to preview on Windows
├── pages/                    ← four complete, editable HTML documents
│   ├── home.html
│   ├── team.html
│   ├── seminar.html
│   └── contact.html
├── content/                  ← JSON data and text
├── assets/
│   ├── css/site.css          ← shared styling
│   ├── js/site.js            ← menu, portraits and member search
│   └── images/               ← photograph, team logo and local portraits
├── tools/
│   ├── build.py              ← generates public/
│   ├── check.py              ← checks local files and links
│   ├── preview.py            ← starts the preview
│   └── update_publications.py ← refreshes the three recent HAL papers
├── docs/sources/             ← original imported materials
├── tests/                    ← checks for pages, seminar data and portraits
├── public/                   ← generated site, excluded from Git
├── .vscode/                  ← project tasks and settings
└── .github/workflows/        ← automatic publishing
```

Each file in `pages/` contains the whole document: head, header, banner, main content and footer, including the member cards and seminar archive. There are no separate layouts or partial files. Header and footer changes must be applied to all four pages; styling is shared in `assets/css/site.css`.

JSON values are inserted with `{{ field.path }}`. Repeated items use a loop:

```html
{% for member in section.members %}
<p>{% if member.url %}<a href="{{ member.url }}">{{ member.name }}</a>{% else %}{{ member.name }}{% endif %}</p>
{% endfor %}
```

You can edit the HTML around these placeholders directly. Every loop needs `{% endfor %}` and every condition needs `{% endif %}`. Inserted values are escaped automatically. Python expressions, template includes and raw HTML from JSON are not supported.

The four pages retain the URLs `/`, `/team-members/`, `/francais-gdt-edp-ot-ml/` and `/contact/`. The `/en/` versions are generated from the same content. The build calculates relative links for each route.

The generated descriptive text currently uses Lorem ipsum while the team decides what to write. The home introduction already edited by Mattia and the original scientific abstracts, dates, names and contact details are preserved.

## Publishing a change

In VS Code's **Source Control** panel, review your changes, write a short description, create the commit and use **Push**. When changes are pushed to `main`, GitHub generates the site, checks its links and publishes **only `public/`**. You do not need to upload the generated pages manually.

On GitHub, the **Actions** tab shows the result of the **Pubblica il sito ParMA** workflow (publish the ParMA site). The source in **Settings → Pages** must be **GitHub Actions**. A proposed change on another branch is checked before it is published on `main`.

The local check verifies pages, images and site sections; when you change links to external websites, check them in your browser. GitHub also runs the checks in `tests/` before publishing. These use example data, so you can update the programme freely.

## Original materials and documentation

The migration preserves the scientific texts, personal links and materials from the [original Inria site](https://team.inria.fr/parma/). Their sources are documented in `docs/sources/`; that folder does not supply content to the site. Photographs, the logo and texts remain subject to their original terms of use.

The site uses HTML, CSS, JavaScript and Python's standard library. Publication data is fetched from HAL during publishing. The seminar and contact pages embed Google Maps; no analytics or external fonts are added.

Technical references: [publishing with GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site), [uploading generated pages](https://github.com/actions/upload-pages-artifact), [deploying the artifact](https://github.com/actions/deploy-pages).

Publication source: [HAL search API](https://api.archives-ouvertes.fr/docs/search/). Map location and sharing URL: [IMO directions](https://www.imo.universite-paris-saclay.fr/en/acces/).
