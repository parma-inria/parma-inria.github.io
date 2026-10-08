# ParMA website

Static website for the ParMA research team at Inria Saclay, CNRS and Université Paris-Saclay.

Live site: **https://mattiagaratti.github.io/parma-website/**

The site preserves the four public sections of the original Inria website: presentation, team, GdT OT–PDE–ML and contact. Its seminar archive contains 17 sessions and 32 talks. Former members remain visible. Pages and assets use relative links so the repository can be transferred to a different owner.

## Edit the website in VS Code

- `data/site.json`: introduction, research topics, contacts and address.
- `data/members.json`: member names, affiliations, categories and personal websites.
- `content/seminar.html`: complete seminar program and archive. `data/seminar.json` is the structured import retained for reference; edit the HTML fragment for visible changes.
- `assets/site.css`: shared design, banner size and image position.
- `assets/mountains.jpg`: header photograph, copied from the existing ParMA website.
- `scripts/build.py`: generates all pages and the existing English entry points.

After editing content, run:

```sh
python scripts/build.py
```

To preview, run:

```sh
python -m http.server 8765 --bind 127.0.0.1
```

Open **http://127.0.0.1:8765/** in your browser. In VS Code, the included tasks offer both “Build ParMA website” and “Preview ParMA website”. There are no third-party build dependencies.

## Publish changes

Commit the generated HTML together with the source changes and push to `main`. GitHub Pages serves the root of this branch. The `.nojekyll` file preserves the plain HTML/CSS/JavaScript site.

```sh
git add .
git commit -m "Update ParMA website"
git push
```

## Transfer to a ParMA account or organization later

Use the repository's **Settings → General → Danger Zone → Transfer ownership**. GitHub keeps repository history, but the Pages URL changes and the previous Pages address is not automatically redirected. After transferring, check Pages settings and update the local remote:

```sh
git remote set-url origin https://github.com/NEW_OWNER/parma-website.git
```

The source uses relative links, so it works under `NEW_OWNER.github.io/parma-website/`. For the root `NEW_OWNER.github.io`, rename the repository to exactly `NEW_OWNER.github.io`. A custom domain can be configured separately.

## Source and assets

Content and public contact details were migrated from https://team.inria.fr/parma/ on 8 October 2026. Scientific titles, abstracts, dates and personal links were preserved. The site does not use analytics, external fonts or embedded trackers. Image sources are recorded in `data/assets.json`. No new license is granted for existing research content or images.

GitHub documentation: [Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages), [repository transfers](https://docs.github.com/en/repositories/creating-and-managing-repositories/transferring-a-repository).
