# Publish your first CLO MCP release on GitHub

You have two things to publish:

1. **The repository:** the readable project files, such as the README and Python code.
2. **The release:** a named version with a post and downloadable files.

Uploading only a ZIP into the repository does not give visitors a browsable code project. Put the individual project files in the repository; attach the ZIP to the release.

## Part 1 — Get ready

Create a GitHub account and install [GitHub Desktop](https://desktop.github.com/). Sign in to the same account in Desktop and your browser. Choose the name/email you want associated with commits; if you prefer privacy, use the no-reply email provided in your GitHub email settings.

Use the prepared **clo3d-mcp repository folder**, not your whole CLO workspace. It already contains the MIT license you selected, README, guides, tests, and workflow. Your garment projects, personal reference photos, Blender code, virtual environment, and runtime logs are excluded from the release archive.

If you are working from a ZIP downloaded later, extract it first. ZIPs do not include the hidden `.git` history folder. Create a local repository in that extracted folder through Desktop if it prompts you to do so. Do not select a license template that replaces the supplied MIT license.

## Part 2 — Add and publish the repository

1. In GitHub Desktop choose **File > Add Local Repository**.
2. Choose the prepared `clo3d-mcp` folder and click **Add Repository**.
3. Review the changed files. There should be code/docs and `.github` configuration, not garment files, `.venv`, logs, or credentials.
4. Enter the commit summary **Prepare CLO MCP alpha release** and commit to `main`. A commit records a local version; it has not uploaded the project yet.
5. Click **Publish repository**. Name it `clo3d-mcp` and use this description: **Experimental local MCP integration for CLO garment workflows on macOS.**
6. To share publicly, deselect **Keep this code private**, then publish to your personal account.
7. Choose **Repository > View on GitHub** and verify the README renders.

These controls follow GitHub's guides for [adding a local repository](https://docs.github.com/en/desktop/adding-and-cloning-repositories/adding-a-repository-from-your-local-computer-to-github-desktop) and [publishing an existing project](https://docs.github.com/en/desktop/adding-and-cloning-repositories/adding-an-existing-project-to-github-using-github-desktop).

## Part 3 — Check the public page

The front page should show a rendered README, an MIT license, and the code folders. Open a few files to make sure they are readable. If it shows only an archive file, you uploaded the archive instead of the project contents.

The repository's **Actions** tab contains the included package checks after a push. Wait for them to finish. A green run means the automated checks in that workflow passed; it does not prove CLO is crash-free. If a run is red, read the failed step and fix it before publishing the release. No account tokens are needed by the included read-only CI workflow.

Suggested topics for the repository's About area: `clo3d`, `mcp`, `fashion-tech`, `garment-design`, `python`, `macos`.

The accompanying validation record explicitly leaves fresh launch of the revised bridge unverified. For the first distribution, keep the **alpha/pre-release** designation and do not present the package as production-stable. Ideally perform a fresh-session bridge check on a disposable CLO project before announcing wider availability, and record the actual result.

## Part 4 — Create the release

1. On the repository page, open **Releases > Draft a new release**.
2. Choose a new tag named **v0.1.0-alpha.1**, targeting `main` after your final commit and checks.
3. Set the title to **CLO MCP v0.1.0-alpha.1 — Local AI-assisted garment workflows**.
4. Copy the contents of `docs/RELEASE_POST.md` into the description. In the pasted post, change the relative link `(VALIDATION.md)` to the full URL of that file in your repository (open the file on GitHub and copy its address).
5. Attach the prepared ZIP, `.whl`, `.tar.gz`, and `SHA256SUMS.txt` from the release-assets folder. Do not attach the `.venv` folder or your garment projects.
6. Select **This is a pre-release**. Save a draft to review, then click **Publish release** when ready.

The release UI and pre-release option are documented in [GitHub's release guide](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository).

## Which files belong where?

| File / folder | Use |
| --- | --- |
| `README.md`, `src/`, `bridge/`, `docs/`, tests, `.github/` | Commit as repository files |
| `LICENSE` | Keep at the repository root |
| `docs/RELEASE_POST.md` | Copy its text into the release description |
| `clo3d-mcp-v0.1.0-alpha.1.zip` | Beginner-friendly release download |
| `clo3d_mcp-0.1.0a1-py3-none-any.whl` | Python package release download |
| `clo3d_mcp-0.1.0a1.tar.gz` | Python source distribution download |
| `SHA256SUMS.txt` | Checksums for the attached files |
| `.venv/`, logs, `.zprj`, `.fbx`, `.blend`, personal config | Keep off GitHub |

## Part 5 — Announce it

Share the actual release URL after publication. You can reuse the opening paragraphs from the release post for a shorter announcement and link readers to the full post. Avoid claiming official affiliation, universal compatibility, perfect fit, or that all crashes are fixed.

If you add screenshots or a video, use material you are allowed to publish. A useful demo shows the prompt, CLO before/after, and the actual result. There is no need to include a private garment project or vendor avatar in the download to demonstrate the tool.

## Part 6 — Publish an update later

Edit and test the source, update the version and changelog, then commit and push in Desktop. Create a new tag/release for the next version. Rebuild the downloadable assets from that exact version; never attach an old ZIP to a newer tag. Keep older releases available so testers can report exactly what they used.

The repository does not auto-publish to PyPI, create releases, or upload files. CI only checks the code. You control the public publishing steps.
