# ParMA — project guide

Website for the ParMA research team at Inria Saclay, CNRS and Université Paris-Saclay.
Use **ParMA** for the team's name in every language.

**Live site:** [parma-inria.github.io](https://parma-inria.github.io/) · **Project:** [GitHub](https://github.com/parma-inria/parma-inria.github.io)

**Edit English once.** Update text and data in `content/`, page structure in `pages/`, and shared styles in `assets/css/site.css`. French and Italian are generated automatically when you push your changes. You do not need to maintain separate pages for each language. Use the optional `content/glossary.json` for preferred translations of recurring terms.

Generated pages and translation caches are hidden in VS Code so the Explorer shows the files you edit. Preview your changes, run the site check, then commit and push.

## Which file should I start with?

| I want to change… | Open… |
| --- | --- |
| Home introduction | `content/home.json` |
| Recent papers and HAL settings | `content/publications.json` (updated automatically) |
| Members' names, roles, institutions, personal websites and photographs | `content/team.json` |
| Seminar dates, programme, abstracts and archive | `content/seminar.json` |
| Summary of the next session on the home page | `content/seminar.json` → `sessions` (generated automatically) |
| Email addresses, postal address and contacts | `content/contact.json` |
| Software, examples and material links | `content/resources.json` |
| Banner titles, introduction paragraphs, menu and footer | `content/site.json` |
| Shared Google Maps location | `content/site.json` → `map` |
| Colours, banner dimensions and page layout | `assets/css/site.css` |
| Banner photograph and logo | `assets/images/` |
| Complete HTML for each page | `pages/home.html`, `team.html`, `seminar.html`, `resources.html`, `contact.html` |
| Header, footer, member cards or archive layout | The relevant complete HTML file in `pages/` |
| Member search and mobile menu | `assets/js/site.js` |
| Languages | Edit the same English JSON and HTML sources; translations are automatic |
| Preferred translations of recurring terms | `content/glossary.json` |

For data updates, start with **`content/`**. For page layout and HTML, start with **`pages/`**. Pages in **`public/`** are generated automatically: any changes made there will be overwritten the next time the site is generated.

## Working in VS Code

Open this folder as your project. Local builds and previews only need **Python 3.10 or later**; no npm, additional Python packages or extensions are required. GitHub installs the translation tools on its own runner.

For the quickest local preview, double-click the launcher for your computer:

- **Windows:** `Open local preview.cmd`.
- **macOS:** `Open local preview.command`.

Both launchers build the site and open the default browser. Keep the terminal window open while using the preview; closing it stops the local server. If this project's preview is already running, the launcher reopens it. Press **Ctrl+C** in the terminal to stop it.

The Mac launcher needs Python 3.10 or later. It checks `python3` on your PATH and the standard Homebrew/Python installation locations. If Python is missing, it displays the official download address. No additional Python packages are needed.

If the Mac file loses its executable permission after being copied or downloaded, open Terminal in the project folder and run this once:

```sh
chmod +x "Open local preview.command"
```

Then double-click it again. Keep the launcher in the project folder alongside `content/`, `pages/` and `tools/`. For the manual commands below, use `python3` on macOS.

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

### Resources page

The Resources page uses one panel per resource. Edit **`content/resources.json`**: top-level `items` are independent resources, and each resource's `materials` contains its documentation, examples or tutorials. SDot's examples gallery belongs inside SDot. Image URLs load directly from the original site; the build does not download them.

To add a resource, append another object to `items`, with a different lowercase `id`. Use `summary_lines: []` when no feature list is needed and `materials: []` when there are no nested links yet. For example:

```json
{
  "id": "another-resource",
  "name": "Resource name",
  "kind": "Software library",
  "description": "Short description.",
  "summary_lines": [],
  "url": "https://example.org/",
  "link_label": "Visit the resource",
  "materials": []
}
```

Nested materials have their own `id`, `title`, `description`, `url`, `link_label` and `images` list. Each image has a `url` and a visible `caption`. Write descriptions, features, captions and link labels in English; they are translated automatically. Resource names, IDs and URLs remain unchanged. The complete page markup is in `pages/resources.html`, and its banner text is in `content/site.json` → `pages` → `resources`.

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
  "calendar_id": "gdt-2027-07-05",
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

### Calendar subscriptions

The seminar calendar has a **Follow all sessions** button and a calendar button beside every date. Visitors subscribe to the whole seminar or to one session. The same feeds serve all three languages; scientific titles and the programme retain their original text.

On iPhone and iPad, both kinds of button open the native Calendar subscription prompt. The browser keeps the provider chooser available as a fallback. Google Calendar's mobile app cannot add a new URL subscription: subscribe once using a computer browser, then display that calendar in the mobile app. This applies to Google Calendar on both Android and iOS.

**Keep each session's `calendar_id` unchanged**, even when you change its date. Give a new session a new unique ID, for example `gdt-2027-07-05`. This permanent ID keeps both the event and its subscription link stable when a session is rescheduled. Edit only `content/seminar.json`; published changes automatically update the feeds.

The `calendar` object sets the default hours, **10:00–12:00 in Europe/Paris**, including summer time. A session can override them with `"start_time": "14:00"` and `"end_time": "16:00"`. Historical afternoon sessions without confirmed end times use `"all_day": true`; their original talk times remain in the event description. Set `"cancelled": true` to cancel a session while retaining it in the site's date list. Deleting a session also sends a cancellation to existing calendar subscribers.

Reminder settings are also in `content/seminar.json`, under `calendar.reminders`: `friday_time` is **09:00** on the Friday strictly before the session, and `event_day_time` is **07:00** on the session date, both in Paris local time. Reminders follow date changes automatically, including across daylight-saving changes. `from_date` is **2026-11-04**, so archived dates before this activation date receive no new alerts. Cancelled sessions have no alerts. Set `reminders` to `null` to disable supplied reminders.

The feeds supply two display alerts per eligible event. Subscribers must enable alerts for the subscribed calendar in their own application; an application may ignore supplied alerts. These reminders do not send email or give the site access to subscribers' accounts.

GitHub records event revisions in the generated `content/calendar-state.json`; do not edit or delete this snapshot. It keeps unchanged events stable and retains cancelled subscriptions. The main feed is `https://parma-inria.github.io/calendar/gdt-ot-pde-ml.ics`; individual feeds use `/calendar/sessions/<calendar_id>.ics`. Local previews generate the same files without accessing any calendar account.

Visitors must **subscribe**, rather than download and import an event once, to receive updates. The chooser opens Apple Calendar / Outlook through a subscription link and provides a copyable URL for other applications. In Google Calendar on a computer, choose **Other calendars → From URL**; in Outlook on the web, choose **Add calendar → Subscribe from web**. Refresh timing belongs to the calendar application and can take several hours or longer than a day. See the [Google](https://support.google.com/calendar/answer/37100?hl=en), [Apple](https://support.apple.com/guide/calendar/subscribe-to-calendars-icl1022/mac) and [Microsoft](https://support.microsoft.com/en-us/outlook/import-or-subscribe-to-a-calendar-in-outlook-com-or-outlook-on-the-web) instructions.

### Seminar archive

Archive years are collapsible: click a year to open or close its sessions. Former team members remain visible on the team page.

The home page and the seminar's **Next Session** section show the same date: the first session on or after today, even if its programme is still being prepared. Only this one future programme is displayed. Later dates stay in the calendar; their programme details remain in the JSON and appear automatically when their date becomes the next session. Adding speakers to December or March does not replace an earlier upcoming November date. A programme enters the collapsible archive only on the day after its date, grouped by academic year. The order of entries in the JSON does not affect this selection.

These views are calculated **when the site is generated**. Today's date determines the next session, past programmes and the September-to-August academic year. GitHub's daily workflow regenerates the published site, and every pushed change also rebuilds it. You do not need to move old sessions manually or edit `content/home.json` when the programme changes.

### Changing the banner image and logo

Replace `assets/images/mountains.jpg` with the new photograph. In `assets/css/site.css`, `.hero.hero-home` sets the home banner height and keeps the bottom of the photograph visible. On smaller screens, the photo fits the screen width and sits below the banner text, so the landscape is less cropped.

The original team logo is `assets/images/parma-logo.png`. It remains complete in the header and footer; `.brand-logo` controls its displayed size. The browser icon uses only the round mark: `assets/images/favicon.svg`, with `favicon.png` as a compatible fallback.

## Three languages, one editable source

There are **five editable HTML pages**, shared by all languages. Write text in English in `content/` or `pages/`; GitHub translates new or changed text into French and Italian when you push. The **EN / FR / IT** links open the equivalent page in the selected language. English uses the root URLs, French uses `/fr/`, Italian uses `/it/`, and `/en/` remains an English alias.

### Optional terminology glossary

Use `content/glossary.json` only when you want a preferred translation for a recurring term. Each entry gives its English, French and Italian wording. Ordinary text still belongs in the English content or HTML files; you do not need to add every sentence to the glossary.

```json
[
  {
    "en": "optimal transport",
    "fr": "transport optimal",
    "it": "trasporto ottimo"
  }
]
```

To add a term, add another object to the list. Keep the `en`, `fr` and `it` keys and write the wording you want in each language.

### Previewing and publishing translations

Local previews use saved translations without installing translation packages or downloading models. After you change English text, that new text may temporarily appear in English in the French and Italian previews. Push your changes to generate its translations, then pull the latest GitHub changes to update your local preview.

Generated snapshots are stored in `content/translations/fr.json` and `it.json`. Previously reviewed wording is preserved in the machine-managed `tools/translation-memory.json`: it applies while the English source is unchanged, and new English text is translated automatically. **These files require no manual maintenance** and are hidden in VS Code. Maintain English text and the optional small glossary instead.

Publication titles and seminar talk titles stay in their original language, including archived talks. Names, email addresses, URLs, identifiers, dates, software names and protected mathematical notation stay intact. Historical abstracts already supplied in French and Lorem ipsum placeholders also remain unchanged.

For HTML edits, interface text and the `aria-label`, `title` and `placeholder` attributes are collected automatically for translation. Use `translate="no"` on an element to preserve its contents in their original language. When a sentence mixes template placeholders with prose, keep the sentence in JSON and insert its placeholder into HTML.

No API key, translation account or subscription is needed. To check saved translation completeness without running a model, use `python tools/update_translations.py --check`. If translation fails during publication, deployment stops and the live site remains available.

## How are the folders organised?

```text
parma-site/
├── README.md                 ← this guide
├── Open local preview.cmd    ← double-click to preview on Windows
├── pages/                    ← five complete, editable HTML documents
│   ├── home.html
│   ├── team.html
│   ├── seminar.html
│   ├── resources.html
│   └── contact.html
├── content/                  ← editable English JSON data and text
│   ├── glossary.json         ← optional EN / FR / IT terminology
│   └── translations/         ← generated snapshots, hidden in VS Code
├── assets/
│   ├── css/site.css          ← shared styling
│   ├── js/site.js            ← menu, portraits and member search
│   └── images/               ← photograph, team logo and local portraits
├── tools/
│   ├── build.py              ← generates public/
│   ├── check.py              ← checks local files and links
│   ├── preview.py            ← starts the preview
│   ├── update_publications.py ← refreshes the three recent HAL papers
│   ├── update_translations.py ← refreshes French and Italian on GitHub
│   ├── translation-memory.json ← preserved reviewed wording, no manual edits
│   └── translation-requirements.txt ← GitHub-only translation packages
├── docs/sources/             ← original imported materials
├── tests/                    ← checks for pages, seminar data and portraits
├── public/                   ← generated site, hidden in VS Code and excluded from Git
├── .vscode/                  ← project tasks and settings
└── .github/workflows/        ← automatic publishing
```

Each file in `pages/` contains the whole document: head, header, banner, main content and footer, including the member cards and seminar archive. There are no separate layouts or partial files. Header and footer changes must be applied to all five pages; styling is shared in `assets/css/site.css`. Generated CSS and JavaScript links include a version based on the file contents, so browsers load updated files after edits. Keep editing the same source files; the version is calculated automatically.

JSON values are inserted with `{{ field.path }}`. Repeated items use a loop:

```html
{% for member in section.members %}
<p>{% if member.url %}<a href="{{ member.url }}">{{ member.name }}</a>{% else %}{{ member.name }}{% endif %}</p>
{% endfor %}
```

You can edit the HTML around these placeholders directly. Every loop needs `{% endfor %}` and every condition needs `{% endif %}`. Inserted values are escaped automatically. Python expressions, template includes and raw HTML from JSON are not supported.

The seminar starts with the nearest upcoming session and a chronological academic-year agenda. The next date links to its programme, even while it is being prepared, and past programmes open inside the archive. Later dates stay visible without links or programme details. The agenda is beside the programme on desktop and below it on mobile. Dates, states and archive links all come from `content/seminar.json`; no calendar needs to be updated separately.

The five English pages use the URLs `/`, `/team-members/`, `/gdt-ot-pde-ml/`, `/resources/` and `/contact/`. Each has a French `/fr/` route, an Italian `/it/` route and an English `/en/` alias. All 20 generated pages share the same five HTML source files. The build calculates relative links for each route and keeps page navigation in the chosen language.

The generated descriptive text currently uses Lorem ipsum while the team decides what to write. The home introduction already edited by Mattia and the original scientific abstracts, dates, names and contact details are preserved.

## Publishing a change

In VS Code's **Source Control** panel, review your changes, write a short description, create the commit and use **Push**. When changes are pushed to `main`, GitHub generates the site, checks its links and publishes **only `public/`**. You do not need to upload the generated pages manually.

On GitHub, the **Actions** tab shows the result of the **Pubblica il sito ParMA** workflow (publish the ParMA site). The source in **Settings → Pages** must be **GitHub Actions**. A proposed change on another branch is checked before it is published on `main`.

The local check verifies all language routes, images and site sections. It also requires external website links to open in a new tab with protective `rel` attributes; when you change their destinations, check them in your browser. GitHub also runs the checks in `tests/` before publishing. These use example data, so you can update the programme freely.

## Original materials and documentation

The migration preserves the scientific texts, personal links and materials from the [original Inria site](https://team.inria.fr/parma/). Their sources are documented in `docs/sources/`; that folder does not supply content to the site. Photographs, the logo and texts remain subject to their original terms of use.

Local rendering uses HTML, CSS, JavaScript and Python's standard library. Publication data is fetched from HAL and automatic translations run on GitHub during publishing. The seminar and contact pages embed Google Maps; no analytics or external fonts are added.

Technical references: [publishing with GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site), [uploading generated pages](https://github.com/actions/upload-pages-artifact), [deploying the artifact](https://github.com/actions/deploy-pages).

Publication source: [HAL search API](https://api.archives-ouvertes.fr/docs/search/). Map location and sharing URL: [IMO directions](https://www.imo.universite-paris-saclay.fr/en/acces/).

Translation models: [English to French](https://huggingface.co/Helsinki-NLP/opus-mt-en-fr) and [English to Italian](https://huggingface.co/Helsinki-NLP/opus-mt-en-it), distributed under Apache 2.0. The exact model revisions and package versions are recorded in `tools/update_translations.py` and `tools/translation-requirements.txt`.
