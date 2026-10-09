# VA claims reference library

These are primary-source materials on VA benefits claims, pulled on **2026-10-09** directly from official government sources. Each file links back to the page it came from, so you can verify any passage at the source. The library contains no third-party summaries or secondary commentary.

## What happened to WARMS

WARMS (Web Automated Reference Material System, `benefits.va.gov/warms`) is retired. Every WARMS URL now redirects to **KnowVA**, VA's knowledge base, and the manuals that used to be on WARMS, including M21-1, are published there. The regulations that WARMS used to mirror (38 CFR) are taken here from the eCFR instead.

## Contents

| Folder | What it is | Source | As of |
|---|---|---|---|
| [`m21-1/`](m21-1/README.md) | **M21-1 Adjudication Procedures Manual**: 427 current sections across all 14 parts plus the TOC, and 156 superseded "Historical" sections, labeled separately. These are the procedures VA claims processors follow. | KnowVA public article API | Per-article last-modified dates are in the index |
| [`knowva-related/`](knowva-related/README.md) | 494 KnowVA articles that M21-1 cross-references: 321 court-decision summaries, M21-1 appendices (EP codes, claim labels), and excerpts from M21-5, M27-1, M24, M28C and the Fiduciary Program Manual | KnowVA | Fetched 2026-10-09 |
| `38-cfr/title-38.xml` + [`38-cfr/parts/`](38-cfr/parts) | **38 CFR, the full title**, as raw XML plus one Markdown file per part. The main claims parts are **Part 3** (Adjudication), **Part 4** (Schedule for Rating Disabilities, with all rating tables), **Part 14** (representation and accreditation), **Part 19/20** (Board appeals) and **Part 21** (VR&E/education). | eCFR (ecfr.gov) | eCFR data current to 2026-10-07 |
| `38-usc/` | **38 U.S.C. (Veterans' Benefits)**, the statute itself, as HTML and PDF | govinfo.gov, U.S. Code 2023 edition | 2023 main edition |
| [`va-gov/`](va-gov) | 40 VA.gov public guidance pages: eligibility, how to file, evidence, exams, effective dates, ratings, compensation and SMC rate tables, PACT Act, decision reviews (Supplemental, HLR, Board), legacy appeals, pension, DIC, and accredited representatives | va.gov | Retrieved 2026-10-09 |
| [`forms/`](forms/README.md) | 26 core claim and review forms (526EZ, 0966, 0995, 0996, 10182, 8940, 0781, and others) and 71 public DBQs | vba.va.gov, va.gov, benefits.va.gov | Retrieved 2026-10-09 |

## Which source controls

1. **38 U.S.C.** is the statute, and it binds VA.
2. **38 CFR** is VA's regulations. It has the force of law and binds VA and the Board.
3. **Court decisions** (CAVC, Federal Circuit) interpret both of the above and bind VA. The `knowva-related/` summaries are VA's internal summaries. To cite a case, read the opinion itself.
4. **M21-1** is VA's internal procedure manual. It binds claims processors at the regional offices, but it does **not** bind the Board or the courts, and it cannot override the statute or the regulations.
5. **VA.gov pages and forms** are plain-language guidance and the required filing vehicles.

## Caveats on currency

- **The eCFR** is kept current daily, but it is not the official legal edition. The official edition is the annual CFR on govinfo.gov, and the Federal Register gives the date each change took effect.
- **The 38 U.S.C. text** is the 2023 main edition. `uscode.house.gov`, which has later release points, was down for maintenance when this was pulled. For amendments enacted after the 2023 edition, check https://uscode.house.gov/view.xhtml?path=/prelim@title38.
- **M21-1 changes often.** Check the "Last modified" date in each file's header and compare it with the live KnowVA page.
- **Two linked KnowVA articles** returned 404 at fetch time. Their IDs are 554400000235145 and 554400000081857, and they are listed in `m21-1/index.json` under `skipped`.

## Rebuilding and refreshing

The KnowVA article API is `https://www.knowva.ebenefits.va.gov/system/ws/v11/ss/article/<id>?portalId=554400000001018&usertype=customer`. It returns JSON with the article HTML and metadata. The M21-1 table of contents is article `554400000073398`. The pull started there and followed every link whose topic breadcrumb is "M21-1 Adjudication Procedures Manual".
