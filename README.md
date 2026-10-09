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
| Complete HTML for each page | `pages/home.html`, `team.html`, `seminar.html`, `contact.html` |
| Header, footer, member cards or archive layout | The relevant complete HTML file in `pages/` |
| Member search and mobile menu | `assets/js/site.js` |

For data updates, start with **`content/`**. For page layout and HTML, start with **`pages/`**. Pages in **`public/`** are generated automatically: any changes made there will be overwritten the next time the site is generated.

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

For photographs, use one of these options in the member's `photo` field:

- **Remote photograph, preferred:** set `"photo": "https://example.org/photo.jpg"` to the direct HTTPS image address on the member's personal website. Use the image address, rather than the address of the page containing it. The browser loads the photograph directly from that website; the build does not download it.
- **Local copy:** when a website blocks direct image loading or only offers HTTP, save a copy in `assets/images/members/` and set, for example, `"photo": "assets/images/members/firstname-lastname.jpg"`. Supported formats are JPG, JPEG, PNG, WebP and GIF. Replace that file when the photograph needs updating.
- **No photograph:** use `"photo": null` to show the member's initials.

Remote photographs update when the person replaces the image at the same address, once the browser's cached copy expires or is refreshed. If the image address changes, update `photo` in this file. Local copies need to be updated manually. While any photograph loads, or if it cannot be loaded, the card displays the member's initials.

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

Archive years are collapsible: click a year to open or close its sessions. Former team members remain visible on the team page.

The build automatically selects the earliest session on or after its date, including planned sessions whose programme has not yet been announced. It derives the calendar and September-to-August academic years from the dates, and groups completed sessions with talks into the archive. The file is arranged with recent dates first for convenience; the build sorts dates itself.

These selections are calculated **when the site is generated**, using that day's date. The published pages update when you regenerate and publish the site; time passing by itself does not rebuild them. You do not need to move old sessions manually or edit `content/home.json` when the programme changes.

### Changing the banner image and logo

Replace `assets/images/mountains.jpg` with the new photograph. In `assets/css/site.css`, `.hero.hero-home` sets the home banner height and keeps the bottom of the photograph visible. On smaller screens, the photo fits the screen width and sits below the banner text, so the landscape is less cropped.

The original team logo is `assets/images/parma-logo.png`. It is used in the header, footer and browser icon. `.brand-logo` controls its displayed size.

## How are the folders organised?

```text
parma-site/
├── README.md                 ← this guide
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
│   └── preview.py            ← starts the preview
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

The site uses HTML, CSS, JavaScript and Python's standard library. It includes no analytics, external fonts or tracking tools.

Technical references: [publishing with GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site), [uploading generated pages](https://github.com/actions/upload-pages-artifact), [deploying the artifact](https://github.com/actions/deploy-pages).
