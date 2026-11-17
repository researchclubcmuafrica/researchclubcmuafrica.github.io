# Guide for volunteers: keeping the deadline tracker up to date

The tracker (`tracker.html`) and the workshops page (`workshops.html`) show deadlines from
`data/deadlines.json`. A GitHub Action rebuilds that file every day at 05:00 Kigali time.

| Kind of item | How it gets on the page |
|---|---|
| Conferences, workshops on OpenReview, community talks (Python events), most summer schools | Automatically, every day |
| Items from the ACL (Association for Computational Linguistics) member portal | The daily job puts them in a **review list**; a volunteer approves them |
| Student suggestions (the "Suggest an opportunity" form) | A volunteer types them in |
| African summer schools, fellowships and anything else | A volunteer adds them by hand |

You only edit YAML files (plain text). You can do it on github.com: open the file, click the
pencil icon, make the change, and click **Commit changes**. The page updates within a few minutes.

## The files you edit

| File | What it is | On the page? |
|---|---|---|
| `data/review/pending.yaml` | Review list: items waiting for a check | No |
| `data/manual/approved.yaml` | Items you have checked and approved | Yes |
| `data/manual/summer-schools.yaml` | African summer schools kept by hand | Yes |
| `data/manual/workshops.yaml` | Workshops not on OpenReview | Yes |
| `data/african_venues.yml` | African conferences kept by hand | Yes |
| `data/full_names.yml` | Full names for short conference names | Yes |

## 1. Check the review list (once a week)

Open `data/review/pending.yaml`. Each item looks like this:

```yaml
- title: Seventh Workshop on Language Technology for Equality, Diversity and Inclusion
  year: 2027
  type: Workshop
  submission_type: Paper
  deadline: '2027-02-05 23:59:59'
  timezone: AoE
  place: San Francisco, United States
  field:
  - Natural Language Processing
  link: https://www.aclweb.org/portal/content/seventh-workshop-language-technology-equality-diversity-and-inclusion
  source: ACL member portal
  source_link: https://www.aclweb.org/portal/content/seventh-workshop-language-technology-equality-diversity-and-inclusion
  found: '2026-11-16'
  start: '2027-06-01'
  end: '2027-06-01'
```

For each item:

1. **Open the official page.** The `link` goes to the ACL portal page; it has a "Website" line
   with the official page.
2. **Check it is useful** for our students (a real call for papers, applications or talks, not
   an advert) and **not already on the tracker** (search the tracker page).
3. **Fix the fields:**
   - `link`: replace it with the official website.
   - `deadline` and `timezone`: the portal gives only a date, so the time is set to 23:59 AoE
     (Anywhere on Earth). If the official page gives another time or time zone, write that.
   - `type`: Conference, Workshop, Summer school, Community talk or Fellowship.
   - `title`: a short name (for example "LTEDI"), and add `full_name:` with the full name,
     acronyms spelled out.
   - If it is held in Africa or is about Africa, add `africa: true`.
   - If it is a workshop of a conference, add `parent:` (for example `parent: NAACL 2027`).
4. **Approve it:** cut the whole item from `pending.yaml` and paste it at the end of
   `data/manual/approved.yaml` (remove the `[]` line there if it is the first item).
   Keep `source_link`: the daily job uses it to know the item was approved.
5. **Turn it down** instead: add the line `  reject: true` to the item and leave it in
   `pending.yaml`. If you delete it, the daily job adds it again the next day. Turned-down
   items are removed automatically once their deadline has passed.

The daily job also removes items whose deadline has passed, and items you approved.
It rewrites `pending.yaml`, so comments you write inside items are not kept; use `note:` instead.

## 2. Add student suggestions

Suggestions from the "Suggest an opportunity" form arrive in the form's Google Sheet.

1. Open the link the student gave and check it as above.
2. Add it to `data/manual/approved.yaml` with the same fields
   (`source: Student suggestion`). See the example at the top of that file.
3. Mark the row in the sheet as done.

## 3. Keep the hand-kept summer schools current

Items in `data/manual/summer-schools.yaml` can show:

- **Check date**: we could not confirm a date (`check_date: true`). When the official site
  announces one, write the `deadline`, `start`, `end` and `place`, and delete `check_date: true`.
- **Check next year's date**: a yearly event (`recurring: yearly`) whose deadline has passed.
  Change `year` to the next year and write the new dates when they are announced
  (or set `deadline: TBA` and `check_date: true` until then).

Only write dates you have confirmed on the official site.

## 4. Writing dates

- Deadline: `'2027-02-05 23:59:59'` (with quotes), or `TBA` if not announced.
- Time zone: `AoE` (Anywhere on Earth, the usual one for papers), `UTC`, `Africa/Kigali`,
  `Europe/London`, and so on. The page shows every deadline in Kigali time.
- Event dates: `start: 2027-06-01` and `end: 2027-06-03`. If unknown, leave them out and
  write `date: To be announced`.

## 5. If something looks wrong

- Check the latest run in the **Actions** tab of the repository (workflow "Update conference
  deadlines"). Its log shows how many items came from each source.
- If a source fails, the page keeps that source's last good data, so the page should never
  go empty.
- A YAML mistake (for example a missing space after `-`) makes the daily job fail. The log
  names the file and line. Fix it and the next run works again.
