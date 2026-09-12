# Feather — user guide

How a Bengali Wiktionary article contest runs in Feather: submitting titles, judging a
queue, and the settings behind both.

A formatted version of this guide is published at
<https://claude.ai/code/artifact/92bf53e7-6499-414a-8a9b-7d2a387786d9>. This file is the
source of truth; update it first.

- [Getting in](#getting-in)
- [The pages](#the-pages)
- [Submitting articles](#submitting-articles)
- [Judging a queue](#judging-a-queue)
- [Selecting many at once](#selecting-many-at-once)
- [Running a contest](#running-a-contest)
- [Reference](#reference)

---

## Getting in

Feather signs you in with your Wikimedia account — the same one you edit with. There is no
separate password and no account to create.

| Role | How you get it | What it opens |
| --- | --- | --- |
| Participant | Anyone signed in | Submit your articles, follow the log, results and your own profile |
| Jury | Assigned per contest by the organizer | A review queue of articles assigned to you, and the decisions on them |
| Organizer | The tool's owner account | Contest settings, jury, exports, integrity checks, everyone's queue |

Jury and organizer accounts also carry participant rights, so a jury member can submit and
be judged like anyone else — subject to the self-review setting.

---

## The pages

Each contest has a short code, and every page for that contest hangs off it.

| Address | Page | Who |
| --- | --- | --- |
| `/` | Every contest, open or finished | Everyone |
| `/<code>` | Dashboard — rules, dates, counts, submissions by user | Everyone |
| `/<code>/submit` | Submit article titles | Participant |
| `/<code>/jury/review-v2` | The review workspace | Jury |
| `/<code>/jury` | Jury progress — who has judged how much (alias `/progress`) | Everyone |
| `/<code>/log` | Activity log — every submission and decision, newest first | Everyone |
| `/<code>/stats` | Submissions and judgments per day | Everyone |
| `/<code>/result` | Standings | Everyone |
| `/<code>/user/<name>` | One person's contest record, with the comments they were given | Everyone |
| `/<code>/config` | Contest settings, jury, restrictions, exports | Organizer |
| `/<code>/admin-special` | Pending articles missing `ব্যুৎপত্তি` or `উচ্চারণ` sections | Organizer |
| `/admin` | All contests, backups, tool-wide numbers | Organizer |

---

## Submitting articles

1. Open `/<code>/submit`.
2. Press **Fetch Articles**. Feather reads the Wiktionary database and lists every
   mainspace page you created inside the contest's date window, so you do not have to
   remember them or copy them out of your contributions.
3. Tick the ones you are entering — or paste titles yourself, one per line.
4. Submit. Every title is checked against the contest rules as it arrives.

A title that fails a rule is kept on your record as **validation failed** with the reason
attached, and is not passed to a jury. Fix the article on the wiki and submit it again.

### What is checked

| Rule | What it means |
| --- | --- |
| Creator | The page was created by you (organizers can waive this per contest) |
| Date window | Created between the contest's start and end dates |
| Minimum size | At least the contest's byte count |
| Minimum words | At least the contest's word count |
| References | At least the contest's number of citations |
| No redirects | A redirect page does not count as an entry |
| No disambiguation | Disambiguation pages do not count |
| Main namespace | Namespace 0 only — no Talk, User or Appendix pages |

**Submitting for someone else.** Jury members and organizers can enter a title on behalf of
another participant, and can bypass the rule checks when a case warrants it — useful for an
article the checker cannot read correctly, or an entry agreed off-wiki.

---

## Judging a queue

The workspace at `/<code>/jury/review-v2` is one article at a time, full screen, with the
queue tucked away until you call it. Press <kbd>Q</kbd> to show or hide the queue;
<kbd>Esc</kbd> closes it.

### Deciding

- <kbd>A</kbd> accept, <kbd>R</kbd> reject, <kbd>S</kbd> skip — skip records no decision and
  moves you on.
- <kbd>C</kbd> jumps into the comment box. Whatever you write is attached to the decision
  and shown to the submitter on their profile.
- <kbd>U</kbd> undoes the decision you just made. The toast counts down about two seconds —
  after that, reopen the article from **Re-review** and decide again.
- <kbd>W</kbd> shows the raw wikitext beside the rendered article.
- <kbd>?</kbd> opens the shortcut panel. Every key there is rebindable and saved for your
  wiki username, not the browser.

### Your queue

Articles are assigned to you rather than raced for. Feather balances the pending pool across
the jury — taking conflict-of-interest pairs into account, and giving the hardest-to-place
articles their juries first — so nobody is left with a queue of work only they can do.

Opening an article locks it for 15 minutes, so two jury members cannot land decisions on the
same row at once. The lock lifts when you decide, move on, or the time runs out.

### The three tabs

| Tab | What it holds |
| --- | --- |
| Queue | Pending articles assigned to you |
| Re-review | Everything you have judged, in accepted and rejected blocks you can collapse |
| Other judges | Organizer only — decisions made by everyone else, read-only |

The search box above the tabs filters by title. On **Re-review** it also matches the
submitter, so typing a username pulls up everything of theirs you have judged — the fastest
way to revisit one person's batch. The list extends itself as you scroll; there is nothing
to click to load more.

---

## Selecting many at once

Rows can be selected the same way as files in a file manager, and the same way with the
keyboard. A selection can then be accepted, rejected or removed in one action, with a single
comment applied to all of it.

| Gesture | What happens |
| --- | --- |
| Click a row | Opens that article. The selection is untouched |
| Click the checkbox | Selects the row without opening it |
| <kbd>Ctrl</kbd>/<kbd>Cmd</kbd> + click | Same, anywhere on the row |
| <kbd>Shift</kbd> + click | Takes the range from the last row you touched. Shift-click back toward it to shrink the range |
| <kbd>↑</kbd> <kbd>↓</kbd> | Move through the list. <kbd>Home</kbd> and <kbd>End</kbd> jump to the ends |
| <kbd>Shift</kbd> + <kbd>↑</kbd> <kbd>↓</kbd> | Drag the selection along with you; coming back toward where you started unselects |
| <kbd>Space</kbd> | Select or unselect the row you are on |
| <kbd>Ctrl</kbd>/<kbd>Cmd</kbd> + <kbd>A</kbd> | Every row on screen, or clear them if they are all selected |
| <kbd>Enter</kbd> | Open the row you are on |
| <kbd>Esc</kbd> | Clear the selection. Press it again to close the queue |

**Bulk decisions are real decisions.** Accept, Reject and Remove act on everything selected
— up to 500 articles per action — and the comment box above the buttons goes on every one of
them. Remove takes articles out of the contest entirely; accept and reject can be changed
later from Re-review.

---

## Running a contest

### Setting the rules

A contest carries its name, its start and end dates, and the rules every submission is
measured against: minimum bytes, words and references, whether redirects and disambiguation
pages count, whether entries must be in the main namespace, and whether the submitter must
be the page creator. Two more settings shape the work: whether jury members may review their
own articles, and whether a talk-page template is posted for submissions.

### Jury and fairness

- **Assign or remove jury members** by wiki username, per contest.
- **Restrictions** pair a jury member with a submitter they must not judge. Feather keeps
  those pairs out of each other's queues when it assigns work.
- **Redistribute** re-plans the whole pending pool at once and tells you how many articles
  changed hands. Use it after adding a jury member or a restriction, when queues have
  drifted apart.
- **Hide a submitter** to take their remaining entries out of the judging panel. Decisions
  already made on their articles are kept and still count — hiding retires the rest of the
  work, it does not undo the work already done.

### Checking the contest against the wiki

An **integrity check** re-reads submitted articles as the wiki stands today and flags four
things: the page is gone, it has become a redirect, it has fallen below the size rule, or
its creator is no longer who it was. It is a report — it changes no article's status, and
nothing is decided for you.

### Talk-page templates

When the contest posts a template on each entry's talk page, the jobs run in the background
and the queue page shows what is done, what is waiting and what failed with its error.
Failed jobs can be retried, and submissions made before the queue existed can be backfilled
— with a dry run that reports exactly what a real run would do.

### Getting the data out

- **CSV** and **JSON** for spreadsheets and scripts, in summary or detailed form.
- **Wikitable** for pasting results straight onto a wiki page.
- **Database backup**, on demand, from the admin dashboard.

### Reading the log

The activity log is the whole contest in one list, newest first, filterable by status, by
submitter and by a search on the title. It is the place to answer "what happened to this
article" — every decision, with its comment and its judge.

---

## Reference

### What a status means

| Status | Meaning |
| --- | --- |
| `pending` | Accepted into the contest, waiting for a jury decision |
| `accepted` | A jury member counted it |
| `rejected` | A jury member did not count it; the comment says why |
| `skipped` | A jury member passed on it. No decision, still pending for someone |
| `validation_failed` | Did not meet the contest rules at submission. Never reaches a jury |

### Keyboard, at a glance

| Key | Action |
| --- | --- |
| <kbd>A</kbd> <kbd>R</kbd> <kbd>S</kbd> | Accept, reject, skip |
| <kbd>C</kbd> | Comment box |
| <kbd>U</kbd> | Undo the last decision, within about two seconds |
| <kbd>W</kbd> | Raw wikitext |
| <kbd>Q</kbd> | Show or hide the queue |
| <kbd>?</kbd> | Shortcut panel — rebind any of these |
| <kbd>↑</kbd> <kbd>↓</kbd> <kbd>Home</kbd> <kbd>End</kbd> | Move through the queue |
| <kbd>Shift</kbd> + arrows | Select as you move |
| <kbd>Space</kbd> | Select or unselect the current row |
| <kbd>Enter</kbd> | Open the current row |
| <kbd>Esc</kbd> | Leave the comment box, clear a selection, close the queue |

Shortcuts are ignored while you are typing in a text field, and a held key acts once —
except the arrows, which repeat so you can run down a list.
