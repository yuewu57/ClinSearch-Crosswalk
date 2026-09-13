# Public launch: ClinSearch-CrossWalk

Prepared 11 September 2026. This is a release-preparation guide, not confirmation
that a public repository, hosted app or monitoring service is already live.

## 1. Approve and test the release

Review `docs/licensing.md`. Confirm rights-holder approval, contributor credits,
third-party permissions and hosting terms before publishing. The source licence
does not revoke prior Apache grants. A public Git repository exposes its history;
therefore keep the existing development repository private and publish an
approved clean snapshot in a separate repository.

Run `python -m pip install -r requirements-dev.txt`, then `pytest` and
`ruff check .`. Before the paper release, record/freeze the tested dependency
versions, conversion ruleset, MeSH cache and benchmark inputs. No conversion
engine changes are part of this release-preparation update.

## 2. Create the public source repository from a clean snapshot

Proposed public repository: `yuewu57/ClinSearch-CrossWalk`. The new UI and citation links
use that destination; it is not automatically created by this change. Choose
another name only after updating those links consistently.

From the existing Windows PowerShell clone, fetch and export the review branch:

```powershell
git fetch origin
if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }
$ref = "origin/release/public-platform-v1-YW-11092026"
$archive = Join-Path (Split-Path (Get-Location) -Parent) "ClinSearch_CrossWalk_source_v1_YW_11092026.zip"
$dest = Join-Path (Split-Path (Get-Location) -Parent) "ClinSearch-CrossWalk"
if (Test-Path $archive) { throw "Archive already exists; choose a new versioned filename" }
if (Test-Path $dest) { throw "Destination already exists; do not overwrite it" }
git archive --format=zip --output=$archive $ref
if ($LASTEXITCODE -ne 0) { throw "git archive failed" }
Expand-Archive -LiteralPath $archive -DestinationPath $dest
Set-Location $dest
```

The archive contains tracked files, not `.git` history. Review all files before
uploading: this does NOT remove sensitive files still tracked in the selected
version. Review examples/data and third-party notices. Brand image files in
`assets/brand/` may be omitted from the public snapshot; the new UI and tests do
not need them. Keep the normative v20 base and approved v21 delta documentation.
Do not delete historic notices applicable to any third-party materials.

Create an EMPTY GitHub repository named `ClinSearch-CrossWalk` under `yuewu57`, initially
private for the final review. Do not auto-create a README or choose another licence.
Then, in the new local directory:

```powershell
git init -b main
if ($LASTEXITCODE -ne 0) { throw "git init failed" }
git add .
git commit -m "Prepare ClinSearch-CrossWalk public research release"
if ($LASTEXITCODE -ne 0) { throw "git commit failed" }
git remote add origin https://github.com/yuewu57/ClinSearch-Crosswalk.git
git push -u origin main
if ($LASTEXITCODE -ne 0) { throw "git push failed" }
```

After approval, use the NEW repository's Settings → General → Danger Zone →
Change repository visibility → Public. Do not expose the development repository
or its old Git history as part of this step. A clean initial commit does not cancel
any rights already granted to recipients of an older Apache-licensed version.

## 3. Deploy the converter for free

Sign in at https://share.streamlit.io using GitHub. Review and accept the hosting
terms yourself, particularly section 6.2 of https://streamlit.io/terms-of-use.
The provider receives a separate content licence; a project non-commercial
notice does not override it. This decision is important for commercial-use control.

Choose Create app → Yup, I have an app, then:

| Setting | Value |
| --- | --- |
| Repository | yuewu57/ClinSearch-CrossWalk |
| Branch | main |
| Main file path | web/app.py |
| Advanced settings → Python version | 3.12 |
| App URL | Request clinsearch-crosswalk, subject to availability |

Deploy. No API key is needed for the existing default MeSH lookup. Do not put
passwords or API keys in source code. Open the resulting REAL app URL in a
signed-out browser. Verify Sharing → This app is public and searchable.

Test a small pasted strategy, an RTF fixture, an invalid input, warnings and
all downloads. Check server logs for errors. The two large logos should not
appear; author/affiliation/citation information remains in About.

The proposed address `https://clinsearch-crosswalk.streamlit.app` is not reserved by
this guide. Use the address actually issued to you.

## 4. Configure the optional project page

In the NEW public GitHub repository, select Settings → Secrets and variables →
Actions → Variables → New repository variable. These settings are not secrets:

| Variable | Value |
| --- | --- |
| APP_URL | Actual deployed HTTPS .streamlit.app URL |
| PUBLIC_RELEASE_APPROVED | true, only after the release checks |
| MONITORING_ENABLED | false initially |
| MONITORING_POLICY_CONFIRMED | false initially |

Choose Settings → Pages → Build and deployment → Source → GitHub Actions.
Then Actions → Publish project page → Run workflow → main. The workflow builds
only `site/`, injects APP_URL and reads the software/ruleset versions from source.
It does not publish the repository root or the brand images. No launch URL is
invented when APP_URL is unset; the launch button stays disabled.

The expected project URL, after successful publication, is
https://yuewu57.github.io/ClinSearch-CrossWalk/ . Verify the actual deployment URL.
This page links to the separately hosted Python app; GitHub Pages itself cannot
run the Python converter.

## 5. Optional eight-hour availability check

Only activate this after confirming the provider permits your automated checks.
No permission or guaranteed keep-awake effect is established by this guide.
Set `MONITORING_POLICY_CONFIRMED=true`, then `MONITORING_ENABLED=true`.
Both must be the lowercase string `true`; APP_URL must also be set.

In Actions → App availability → Run workflow, run once manually from main.
Success means the real title, strategy input and enabled Convert button appeared,
not merely an HTTP 200 response. No strategy is submitted. The checker does NOT
click a wake-up prompt, bypass authentication or challenge pages, or guarantee
that Streamlit resets its inactivity timer. Sleeping/unavailable apps fail the
check so you can open the app manually and investigate.

The configured schedule is 00:17, 08:17 and 16:17 UTC (01:17, 09:17 and 17:17
in the UK while British Summer Time applies). GitHub schedules are best-effort;
runs can be delayed or dropped, and public-repository schedules are disabled
after 60 days without repository activity. To stop checks, set
MONITORING_ENABLED=false or disable the App availability workflow.

Configure your GitHub account's Actions email notifications and verify that a
manual failed test reaches the intended recipient; this change does not configure
notification preferences or promise email delivery. Standard runners are free for
public repositories; private repositories have plan-dependent allowances.

## 6. Paper release

Replace provisional collective authorship with the approved contributor/author
metadata. Create a tested release tag and add the true date and archive DOI to
CITATION.cff. Archive the exact paper version with Zenodo and cite that version,
not just the evolving main branch. Do not invent a paper DOI before one exists.

## Official documentation checked

- Deployment: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- Sharing: https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app
- Hibernation/resources: https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app
- Hosting terms: https://streamlit.io/terms-of-use
- GitHub schedules: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- Pages workflow: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- Software archiving: https://docs.github.com/en/repositories/archiving-a-github-repository/referencing-and-citing-content
