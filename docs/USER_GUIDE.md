# Feather — user guide

How a Bengali Wiktionary article contest runs in Feather: submitting titles, judging a
queue, and the settings behind both.

A formatted version of this guide is published at
<https://claude.ai/code/artifact/92bf53e7-6499-414a-8a9b-7d2a387786d9>. This file is the
source of truth; update it first.

- [Getting in](#getting-in)
- [The pages](#the-pages)
- [Submitting articles](#submitting-articles)
- [Judging a queue](#judging-a-queue) — summary; the full jury guide is [JURY_GUIDE.md](JURY_GUIDE.md)
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
<kbd>A</kbd> accepts, <kbd>R</kbd> rejects, <kbd>S</kbd> skips, <kbd>C</kbd> is the note
box, <kbd>U</kbd> undoes the decision you just made, and <kbd>?</kbd> lists every key and
lets you rebind it.

Articles are assigned to you rather than raced for, opening one locks it for 15 minutes, and
a selection of rows can be decided in one action.

**[JURY\_GUIDE.md](JURY_GUIDE.md) is the full guide to that screen** — the layout, how the
queue is shared out, the three tabs, bulk
selection, keyboard navigation, and what to do when something looks wrong.

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

Every shortcut in the review workspace, and what it does, is in
[JURY\_GUIDE.md](JURY_GUIDE.md#moving-around-with-the-keyboard). Shortcuts are ignored while
you are typing in a text field, and a held key acts once — except the arrows, which repeat
so you can run down a list.
