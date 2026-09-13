# Feather — jury panel guide

Everything the review workspace at `/<code>/jury/review-v2` does, for the people judging a
queue. The rest of Feather — submitting, contest settings, exports — is in
[USER\_GUIDE.md](USER_GUIDE.md).

- [The layout](#the-layout)
- [Deciding](#deciding)
- [Notes](#notes)
- [Reading the article](#reading-the-article)
- [Your queue](#your-queue)
- [The three tabs](#the-three-tabs)
- [Selecting many at once](#selecting-many-at-once)
- [Moving around with the keyboard](#moving-around-with-the-keyboard)
- [On a phone](#on-a-phone)
- [For organizers](#for-organizers)
- [When something looks wrong](#when-something-looks-wrong)

---

## The layout

Three regions, and the whole screen is yours — the site navigation is hidden here.

| Region | What it is |
| --- | --- |
| Queue drawer, left | Your assigned articles. <kbd>Q</kbd> shows or hides it, <kbd>Esc</kbd> closes it. Drag its right edge to resize, or focus the divider and use <kbd>←</kbd> <kbd>→</kbd>; <kbd>Home</kbd> resets the width |
| Article, centre | The rendered entry, with the title and who submitted it above it |
| Decision panel, bottom | The note box, and Accept / Reject / Skip / Delete |

Above the queue sits the strip of counts — total, pending, OK, rejected — and a dot that
means the panel is refreshing itself. It polls every few seconds, so a decision someone else
lands, or an article newly assigned to you, turns up without a reload.

## Deciding

| Key | Action |
| --- | --- |
| <kbd>A</kbd> | Accept — it counts for the submitter |
| <kbd>R</kbd> | Reject — it does not count. Say why in the note |
| <kbd>S</kbd> | Skip — no decision, move on. It stays pending for whoever picks it up |
| <kbd>U</kbd> | Undo, while the toast is still counting down (about two seconds) |

Every key is rebindable: <kbd>?</kbd> opens the shortcut panel, click a key, press the new
one. Rebinds are saved against your wiki username, so they follow you to another browser.

A held key acts once. This is deliberate — a leaned-on Accept key would otherwise tear
through a dozen articles you never saw, and those decisions are not undoable in a batch.

After the toast expires, a decision is still not final: reopen the article from
**Re-review** and decide again. The new decision replaces the old one.

**Delete** is not a decision. It removes the article from the contest entirely, and the
submitter loses it. Reject is what you want unless the submission itself should not exist.

## Notes

<kbd>C</kbd> jumps into the note box. Whatever you write is attached to the decision and
shown to the submitter on their profile, so it is worth a sentence on a reject.

A note written for one article stays with that article. Deciding a whole selection at once
puts the same note on every article in it.

## Reading the article

The centre pane is the entry as it stands right now on bn.wiktionary.org. The title is a
link — it opens the real page in a new tab, which is where you go to check history or
categories.

Beside the title:

| Chip | What it tells you |
| --- | --- |
| by _name_ | Who submitted it to the contest |
| a date | When the page was created on the wiki |
| a padlock | Someone else has it open right now |
| Accepted / Rejected | Your own last decision, when you are looking at something you have judged |

The contest rules — size, references, creation window, authorship — were enforced when the
title was submitted; anything that failed them never reached your queue.

<kbd>W</kbd> splits the pane and shows the raw wikitext beside the rendered entry, with a
Copy button. On a narrow window the two stack; on a phone a Visual / Wikitext switch picks
one at a time. The choice is remembered.

## Your queue

Articles are **assigned**, not raced for. Feather spreads the pending pool across the jury,
avoids pairing anyone with a submitter they have a declared conflict of interest with, and
places the hardest-to-assign articles first, so nobody ends up holding a queue only they can
work. Bans, restrictions and new submissions all re-level it.

Opening an article locks it for 15 minutes so two people cannot decide the same row at once.
The lock lifts when you decide, when you move to another article, or when it runs out. A
padlock chip means someone got there first — you can still read it, and the queue will find
you something else.

The list loads a page at a time and extends itself as you scroll or arrow past the end.
There is nothing to click to load more.

## The three tabs

| Tab | What it holds |
| --- | --- |
| Queue | Pending articles assigned to you |
| Re-review | Everything you have judged, in accepted / rejected / skipped blocks you can collapse |
| Other judges | Organizers only — what everyone else decided, read-only |

The search box filters by title. On **Re-review** it matches the submitter too, so typing a
username pulls up that person's whole batch — the fastest way to revisit one contributor.

## Selecting many at once

Rows behave like files in a file manager, with the mouse or the keyboard.

| Gesture | What happens |
| --- | --- |
| Click a row | Opens it. The selection is untouched |
| Click the checkbox | Selects without opening |
| <kbd>Ctrl</kbd>/<kbd>Cmd</kbd> + click | Same, anywhere on the row |
| <kbd>Shift</kbd> + click | Takes the range from the last row you touched; shift-click back to shrink it |
| <kbd>Space</kbd> | Select or unselect the row you are on |
| <kbd>Ctrl</kbd>/<kbd>Cmd</kbd> + <kbd>A</kbd> | Every row on screen, or clear them if they are all selected |
| <kbd>Esc</kbd> | Clear the selection. Again to close the queue |

The bar that appears at the bottom of the list acts on everything selected — up to 500
articles per action — and the note above the buttons goes on every one of them. Accept and
Reject can be revisited from Re-review; Remove cannot.

## Moving around with the keyboard

| Key | What it does |
| --- | --- |
| <kbd>↑</kbd> <kbd>↓</kbd> | Move through the queue **and open what you land on** — the article and its preview follow you |
| <kbd>PgUp</kbd> <kbd>PgDn</kbd> | Ten rows at a time |
| <kbd>Home</kbd> <kbd>End</kbd> | The ends of the list |
| <kbd>Shift</kbd> + any of those | Drag the selection along with you; coming back toward where you started unselects |
| <kbd>Enter</kbd> | Open the row you are on, without waiting |

The preview opens a beat after you stop moving, not on every keypress, so holding <kbd>↓</kbd>
through fifty rows fetches one article rather than fifty. Shift-arrow is building a
selection, so it leaves the open article alone.

The queue is a listbox as far as a screen reader is concerned: it announces each row as you
arrow onto it, says which rows are selected, and says which article is currently open.
Shortcuts are ignored whenever you are typing in a text field.

## On a phone

The queue and the article are separate screens, switched from the bar at the bottom. The
action row under the note holds Accept, Reject, Skip and Delete. Everything else works the
same; there is simply no room for the queue and the article at once.

## For organizers

The owner sees two extra things: a **view as** picker that shows any jury member's queue
exactly as they see it, and the **Other judges** tab with everyone else's decisions. Both
are read-only in the sense that matters — nothing you do there decides for someone else.

Who is on the jury, who may not judge whose work, and who is banned from the contest are all
set in contest settings, described in [USER\_GUIDE.md](USER_GUIDE.md#running-a-contest).

## When something looks wrong

| What you see | What it means |
| --- | --- |
| "Queue is clear" with articles still in the contest | None of the remaining pending articles are assigned to you. Someone else has them |
| A padlock on most of the queue | Another jury member is working the same list; yours will re-level within a few seconds |
| The counts and the list disagree | The strip polls separately. Reload if it survives a few seconds |
| Preview not available | The entry was deleted or renamed on the wiki after it was submitted. Open the title link to check |
| Your shortcuts are gone | They are saved per wiki username — check you are logged in as yourself |
