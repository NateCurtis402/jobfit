# Decisions

Product and design calls, with the reason. These are the answers to "why did you
build it that way" in an interview — written by Nero, not generated after the fact.

## 1. Duplicate detection uses the job text, not the board's job id
The same job appears on several boards with a different id each time. Hashing
lowercased title + company + the first 500 characters of the description makes
the *job* the identity, so one role cannot be counted twice in the corpus or in
the evals. Cost: two genuinely different postings with identical title, company
and opening paragraph collapse into one. Accepted.

## 2. Resume scoring keeps the best-matching section, not the average
A resume is not one topic. Nero's is mostly Marine logistics with a Python/SQL
skills block near the end. Averaging the whole document makes every posting look
"mostly logistics", which buries exactly the matches worth seeing. Taking the
maximum over sections lets a strong skills match win on its own. Cost: a posting
can rank high on one section while the rest of the resume is irrelevant — which
is what `matched_terms` is shown for, so the ranking is explainable.

## 3. Skills matter more than longevity — do not hard-filter on experience
Open question Nero raised: a job that matches the skills but asks for more years
than he has should not be thrown out. Many "5+ years" lines are wishlists, and a
logistics veteran with shipped Python work is a legitimate candidate for them.
Decision: never filter a posting out of the results for seniority. Show it, and
let the score and the posting text speak. If experience weighting is added later,
it must be a visible adjustment (like `rank_by=hybrid`), not a silent filter.

## 4. Semantic-only vs hybrid is measured, not argued
`rank_by="semantic"` is the baseline; `rank_by="hybrid"` adds a small bonus per
skill shared between resume and posting. Both stay in the code so M3 can report
which one actually ranks better against hand labels. No tuning by taste.

## 5. The corpus is snapshotted and committed; live fetching is opt-in
A demo that needs the network breaks on someone else's laptop, and job boards
change or block feeds without notice. `make refresh` re-fetches; the committed
snapshot keeps `make ingest` reproducible.

## 6. Honest corpus limits
The two keyless feeds are remote-only. Nothing in this repo claims Omaha
coverage yet — that needs Adzuna (or USAJobs for federal roles), both of which
require a key Nero signs up for himself. Anywhere results are shown, the
coverage gap is stated.
