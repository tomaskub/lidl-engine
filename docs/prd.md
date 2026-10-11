# Lidl Engine product requirements

Status: Accepted on 2026-10-12. All interview decisions through Q41 are settled, and the owner confirmed shared understanding.

This PRD governs first-release product behavior. Where the initial architecture proposal differs, including pagination, use the requirements here.

## 1. Purpose and user

Lidl Engine helps its owner prepare for household shopping by finding relevant Lidl Poland offers for a chosen shopping date and understanding the conditions needed to obtain each advertised deal.

The first release serves one person through a Polish desktop browser interface. It runs in Docker on an always-running Ubuntu server in the household and is accessible only on the local network. Devices on that network can open it without an application login.

The owner should be able to search for a product, narrow the results by category, inspect prices and purchase conditions, and open the original source page. Collection and publication run automatically without requiring the owner to review extracted offers.

## 2. Release scope

Include:

- The first regular `Gazetka` in the most recently discovered Lidl Poland flyer listing.
- Advertised grocery products and product groups with a stated price or purchase benefit, including alcohol, ordinary advertised prices, and category-wide promotions.
- Searchable offers from previously collected flyers, subject to their validity and retained evidence.
- Source images, descriptions, structured extraction, offer reconciliation, uncertainty labels, and source-page inspection.
- Weekly collection, a manual refresh command, bounded retries, persistent progress, and visible collection diagnostics.

Exclude from the first release:

- Processing every listed flyer or specialist catalog.
- Non-grocery merchandise, generic advertisements without a price or benefit, contests, and partner services.
- Mobile presentation, conversational querying, shopping lists, favorites, exports, historical price comparisons, and editing extracted facts.
- Calculating multibuy totals or effective deal prices.
- Mandatory offer review, external notifications, application spending reports, and a hard spending cutoff.

The product presents advertised deals. Flyer coverage does not establish product stock or store-specific availability.

## 3. Source selection and collection

### Current flyer

Preserve listing order and select the first entry presented as `Gazetka`, ignoring surrounding whitespace and letter case, as the PoC does. Do not broaden collection to later flyers.

The latest successful discovery determines the current flyer even when processing is incomplete. A failed discovery preserves the last known selection and displays the failure. Never infer an offer's validity merely from the flyer's position in the listing.

### Schedule and manual execution

- Start collection every Wednesday at 06:00 in `Europe/Warsaw`.
- Target completion by Thursday at 06:00 in that timezone.
- Provide a documented command to refresh manually and recover failed work.
- Prevent simultaneous scheduled and manual runs.
- Use the household timezone for the default shopping date and user-facing collection times.

The completion time is a target. An incomplete or overdue run must not make the browsing application unavailable or imply that collection completed.

### Change detection and reuse

Check source pages for actual content changes on each scheduled or manual run. Reuse completed descriptions and extraction only when their source content and relevant processing configuration still match. A nonempty description alone is insufficient evidence of unchanged source content.

Source revisions must invalidate affected descriptions. A description change must invalidate its dependent structured extraction. Relevant model, prompt, schema, or normalization changes must invalidate the affected results or reprocess retained inputs as appropriate.

### Processing stages

1. Discover and select the flyer.
2. Retrieve its page metadata and preserve source images.
3. Generate Polish descriptions through a configurable OpenRouter image model.
4. Extract structured offers from those descriptions through a separately configurable OpenRouter model.
5. Validate and normalize supported facts, infer dates under section 5, and reconcile offer occurrences.
6. Persist and publish available offers with their source evidence and diagnostics.

Use the two-stage approach described in [ADR 0001](adr/0001-two-stage-flyer-extraction.md). The second stage cannot verify or recover information missing from a description; launch evaluation therefore uses original images as its reference.

## 4. Offer information and categories

Each offer must preserve the following information when supported by its source:

| Information | Required behavior |
| --- | --- |
| Subject | Polish product or product-group name; distinguish product offers from category-wide offers |
| Product description | Brand, size or pack quantity, variants, and relevant descriptive details |
| Categories | One or more supported categories from the documented taxonomy |
| Promotion terms | Advertised mechanism and the product or quantity receiving the benefit |
| Prices | Source-stated advertised price, regular price, unit price, priced quantity or unit, and currency |
| Discount | Source-stated percentage and its scope, such as the second cheaper item |
| Purchase requirements | Required quantities, paid versus received quantities when stated, Lidl Plus and coupon requirements |
| Limits and deposits | Stated purchase limits, their stated scope, and separate stated deposit information |
| Validity | Original validity wording, normalized bounds, and whether each bound is explicit, inferred, or unknown |
| Evidence | Source-page links and images, source-specific descriptions and terms, and extraction evidence |
| Uncertainty | Unknown details, inference labels, and suspected conflicting variants |

Use all ten categories in [offer-categories.md](offer-categories.md): bakery, alcoholic beverages, non-alcoholic beverages, fruits, vegetables, meats, seafood, dairy, pantry items, and ready made snacks.

Tea and coffee sold for brewing belong to pantry items. Ready-to-drink tea and coffee belong to non-alcoholic beverages. Category-wide offers spanning product types receive multiple category labels without becoming duplicate offers. An eligible offer with an unsupported category remains searchable with a category-unknown label.

## 5. Validity and uncertainty

### Resolving dates

Resolve each bound independently:

1. Use the explicit offer bound when available.
2. Otherwise use the corresponding bound of the advertised flyer period and mark it inferred.
3. Otherwise leave the bound unknown.

Do not overwrite explicit offer dates with the flyer period. Preserve original wording and the basis for each normalized bound. Normalize dates with their applicable year, including ranges crossing New Year. An inconsistent range must be exposed as uncertain rather than silently repaired by overriding explicit source facts.

Examples:

- A flyer valid from 10 through 15 October supplies both missing offer bounds, marked inferred.
- An offer explicitly valid from 12 through 20 October retains that period even when the flyer ends on the 15th.
- An offer explicitly ending on 15 October cannot be asserted valid on 20 October merely because its start remains unknown.

### Selecting offers for a shopping date

The date defaults to today. Search and category filters operate together with these inclusion rules:

| Relationship to selected date | From current flyer | From an older collected flyer |
| --- | --- | --- |
| Explicit or inferred bounds cover the selected day | Include | Include |
| A known bound rules out the selected day | Include with `valid for <validity_date_range>` or the available bound | Exclude |
| A bound remains unknown and no known bound rules out the selected day | Include with validity-unknown label | Include with validity-unknown label while retained |

This preserves the current-flyer exception even for advertisements that have ended or have not started. Retention itself never establishes validity. Inference labels remain visible when inferred dates cover the selected day.

The conflict-context rule in section 6 is an additional display exception: a related older-flyer variant outside the selected day can appear beside a matching variant, with its own validity and a conflict-context label. Its presence does not assert that it applies on that day.

### Unsupported details

Retain eligible offers with unsupported fields explicitly unknown. An unstated coupon or Lidl Plus condition must not become an assertion that the condition is unnecessary. Do not invent prices, discounts, quantities, or conditions.

Date inference is the accepted exception described above. Avoid the PoC's `confirmed` label, which can suggest verification that did not occur. Use factual labels describing unknown information, inferred dates, and source disagreements. These labels do not block publication.

## 6. Price presentation and offer identity

Display each stated price beside its priced quantity or unit and the conditions needed to obtain it. Distinguish ordinary advertised prices from discounts and conditional benefits.

Examples:

- `3,99 zł/szt. przy zakupie 3 szt.; kupon Lidl Plus`.
- A buy-two-receive-three offer shows the stated quantities and terms.
- A second-cheaper-item discount shows its advertised percentage and scope without an invented universal price.
- A stated deposit appears separately from the advertised product price.

The first release presents source-stated amounts, unit prices, and percentages. It does not derive basket totals, effective multibuy prices, or calculated savings percentages.

Merge repeated advertisements when their product or product-group subject, validity, prices, and purchase terms agree. Keep every supporting source occurrence. Product name alone is insufficient for a match.

Ordinary and coupon prices for the same product remain different offers. When advertisements appear to describe the same deal but disagree on price or conditions, retain the conflicting variants and their original terms, flag the disagreement, and present those variants adjacent to one another. Do not silently select a winning price.

Apply browsing filters to conflict groups. If any variant would appear under the date, current-flyer, search, and category rules, display the entire retained, source-supported group together. Mark nonmatching variants as conflict context and show each variant's own validity. This can include an older-flyer variant outside the selected day without asserting that it is valid for that day.

Sort conflict groups as units so table sorting does not separate their variants. Superseded occurrences retained solely as audit evidence do not create browsable conflict-context rows.

## 7. Desktop browser behavior

- Use a Polish interface and Polish offer names.
- Search partial product names, brands, and descriptions while ignoring case and Polish diacritics. `losos` must match `łosoś`.
- Provide category and shopping-date controls. A multi-category offer matches each of its supported categories.
- Support sorting by name, category, and validity end date, with alphabetical name order as the default.
- Preserve search, filters, and sorting in URL parameters for direct navigation and bookmarks.
- Render all matching rows without pagination or requiring the user to load another page.
- Keep related conflict-context variants adjacent to the matching row, even when a context variant does not independently match the filters.
- Keep prices, units, purchase terms, validity, and uncertainty legible in the table or its offer details.
- Open retained source-page previews on demand and provide original Lidl source links.
- Show a clear empty state when no offers match, and distinguish it from unavailable or incomplete collection data.

The server filters and sorts stored records and returns the complete set matching the browsing rules. A desktop table is the required launch interface.

## 8. Failures, diagnostics, and evidence lifecycle

### Partial results and recovery

Publish available offers even when some pages fail. A successfully processed page with zero eligible offers is different from a missing or failed page.

Preserve prior data and evidence for failed rereads. Failure must not be treated as a successful empty extraction. Previously collected offers remain browsable under their source and validity rules.

Retry transient failures at most three times per failed processing stage in addition to its initial attempt. Batch-status polling does not count as a retry. Authentication failures stop the run. After retries are exhausted, report the incomplete result and allow recovery through manual refresh or the next Wednesday run.

Persist completed work and pending batch identifiers so interrupted runs resume without unnecessarily repeating paid model work. Keep the browsing application available independently of collection.

### Visible diagnostics

Show:

- The current selected flyer.
- Collection progress or incomplete status.
- Processed versus expected page coverage, such as `111 of 114 pages processed`.
- The last successful collection time, without making a partial result look complete.
- Collection failures and an overdue completion target when applicable.

Keep detailed errors in server logs. No external notification channel is required.

### Retention

Retain collected offers, source images, descriptions, and extraction evidence for 90 days after offer expiry. When expiry remains unknown, use 90 days after the last successful observation in a collected flyer.

Preserve shared source evidence while a retained offer still requires it. Keep retained source previews usable when the original Lidl link is unavailable. Expired offers remain outside the ordinary shopping view except where the current-flyer or selected-date rules include them.

### Successful source replacement

A successful reread replaces the affected page's previous offer occurrences. Obsolete occurrences leave the browsing dataset while their audit evidence remains subject to retention. An offer remains browsable if another retained source occurrence still supports it. Failed rereads preserve previous occurrences.

This distinguishes source withdrawal from expiry and from missing data caused by a processing failure. Retained audit evidence alone does not restore an obsolete offer to browsing or conflict context.

## 9. Deployment and architecture constraints

Follow the shared Python project and separate web and collection processes described in [ideation_summary.md](ideation_summary.md), [tech-stack.md](tech-stack.md), and [repository-structure.md](repository-structure.md):

- Docker and Docker Compose on the household Ubuntu server.
- Flask, Gunicorn, Jinja2, HTMX, HTML, and CSS for the browser application.
- PostgreSQL and psycopg for persistent application data, with versioned SQL migrations.
- HTTPX and BeautifulSoup for source retrieval and HTML discovery, alongside the OpenRouter inference stages.
- Shared domain and persistence modules; collection executes independently of web requests.

Use persistent storage for database data, retained source files, and processing checkpoints. Container recreation must preserve these. Document startup, manual refresh, scheduling, configuration, and database plus evidence backup and restoration as required by the architecture proposal.

Keep secrets in server-side configuration excluded from version control. Browser access remains local; it must not expose model credentials or database credentials. The PoC's NocoDB catalog is replaced by the application database and browser interface.

Expected model processing cost is 2–3 PLN per ordinary week, based on the owner's practice runs. This is an operating expectation, not a measured guarantee or a hard limit. The owner monitors spending in OpenRouter. No application cost-reporting feature is required.

## 10. Launch acceptance criteria

### Extraction evaluation

Perform a one-time evaluation against original flyer images using at least 100 eligible offers. Include ordinary prices, category-wide deals, multibuys, coupons, deposits, differing validity ranges, and the brewing versus ready-to-drink category distinction.

| Measure | Required result |
| --- | --- |
| Eligible-offer recall | At least 90% of source-eligible offers captured |
| Price accuracy | At least 95% of expected source-stated price facts captured correctly, including amounts, units, discount scope, and stated deposits |
| Date accuracy | At least 95% of expected date facts and applicable inference outcomes represented correctly |
| Purchase-condition accuracy | At least 95% of expected source-stated conditions captured correctly |
| Category accuracy | At least 95% of evaluated offers assigned the correct supported category set |

Count omitted source-stated information as an error. Score the price, date, and purchase-condition measures separately. Missing printed conditions cannot be hidden by labeling them unknown. Correct unknowns apply where the source itself provides no supported value.

For captured offers, each fact measure compares correctly captured reference facts with the total expected reference facts plus any unsupported extra assertions. An incorrect value is an error for that fact; an omitted source-stated fact is also an error. Wholly missed offers count against recall. Freeze the reference annotations before scoring model output.

Evaluate inferred dates against the agreed precedence and fallback rule and their labels; the presence of an inference label does not independently prove that an advertisement truly applies on that date. Assess distinct offers for recall and retain repeated advertisements as evidence rather than counting them as extra captured deals.

These checks establish the launch baseline. Scheduled publication does not require weekly human review.

### Functional and operational checks

- Polish and diacritic-insensitive search, category filters, date inclusion rules, URL state, and all supported sorts behave as specified.
- Agreeing advertisements merge with complete source links; conflicting variants remain adjacent and do not acquire a selected winning price.
- Filtering a conflict group retains its source-supported variants with context labels and individual validity, including related older variants outside the selected date.
- Unknown, partially known, explicit, and inferred validity follow section 5, including the current-flyer exception.
- Unchanged inputs reuse completed work; changed page images invalidate dependent descriptions and extraction.
- Partial runs publish available offers and expose accurate coverage; failed rereads preserve prior results.
- Successful rereads retire obsolete occurrences while preserving audit evidence; offers with another retained supporting occurrence remain browsable.
- Reruns do not duplicate offers or occurrences, and interrupted processing resumes its saved progress and existing batch.
- Wednesday scheduling uses `Europe/Warsaw`, manual execution is documented, and runs cannot overlap.
- Container recreation preserves application data and source previews.
- Source previews load when opened.
- Initial table loading, searching, filtering, and sorting complete within two seconds over the household network, evaluated with up to 1,000 matching rows and no pagination.

These are requirements for implementation verification. They have not been measured or demonstrated by this documentation work. The existing PoC artifacts are not an independently verified accuracy benchmark.

## 11. Confirmation

All interview questions Q1–Q41 are resolved. The owner confirmed on 2026-10-12 that this PRD captures the shared understanding. The PRD is accepted as the first-release product specification.

## References

- [Glossary](../GLOSSARY.md)
- [Interview and PoC discovery notes](prd-discovery.md)
- [Offer categories](offer-categories.md)
- [Two-stage extraction ADR](adr/0001-two-stage-flyer-extraction.md)
- [Initial architecture proposal](ideation_summary.md)
- [Tech stack](tech-stack.md)
- [Repository structure](repository-structure.md)
