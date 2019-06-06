# Explaining deletion
## Rationale
Sometime, you have bugs. Card or notes are deleted, and you just don't
know why. You can find the notes in the file deleted.txt, at least if
you are lucky, and that the deletion was clean enough to be logged.

However, when you want to know why the problem did occur, you miss two
important facts. The time of the deletion. And its reason.

Furthermore, the same separator (tab) is used for separating the
fields's content, and separating the fields content from the main
column. This does not help readability.

This add-on logs everything in CSV format, which is non-ambiguous (as
long as you know the note type)
## Usage
### All kinds of deletions
When this add-on is installed, when a note is deleted, it will be
logged in deleted_long.txt instead of deleted.txt. The reason will be
logged. Currently, there may be three kinds of reason:

You actually asked to delete a whole not. It can appear in the
  following cases:
* "Deletion of note {id} requested from the reviewer." While reviewing
  card, you pressed on «delete».
* "Deletion of notes {nids} requested from the browser" In the
  browser, you pressed on delete.
* "Temporary note" (i.e. you started to create a note, and then decided
  you don't want to save it)
* "Remove cards/notes from grave, after sync." This may occur during
  synchronization. I'm not sure when it actually occurs.
* "Removing notes {ids} with missing note type" For some reason, you
  had a note and anki does not have any idea how to represent
  it. Instead of telling you something REALLY wrong occured, and
  giving you the data to save it, anki silently delete all of
  this. Pretty bad, isn't it ? I sadly have no solution, it would require a
  big and complicated add-on to fix it. So my best right now is to at
  least let you kow in the deletion file.
* "Note {ids} with no cards" It may occur that a not have no cards
  anymore. For example if you empty all of its fields. Or at least,
  that there are so little fields used that no cards can be
  generated. Once again, instead of letting you correct this error,
  anki silently delete the note. You'll be able to find when this
  happen thanks to this add-on. At least, if you go in the deleted
  file. Sorry that I can't do better.

You may also decide to delete cards, realize that this lead no card
  to some note, and thus deleted the note. It may occur in the
  following cases:

* "Cards {ids} removed because of missing templates." Similar to last
  case, but instead of a whole note missing, a single template of a
  card is missing.
* "Deleting cards {cids} because we delete the model {m}". A model is
  being deleted. You probably was warned that it still had some notes,
  and agreed to have it deleted. Thus here it is.
* "Removing card type {template} from model {m}" Similarly to last
  case, but this case with card type.
* "Removing cards {cids} because its deck {did} is deleted" Once
  again, it's similar, but with deck deletion.
* "Changing notes {nids} from model {oldModel} to {newModel}, leading to deletion of {deleted}" Changing
  the note type of a note is essentially creating a new note and
  deleting the old one. Kind of. Anyway, it leads to card deletion,
  and there it is.



Finally, it may also occur that we have no clue why the deletion
occured. It was probably an add-on request, thus the current add-on
  can't control it. This is thus the best error message that I can
  offer.
* "Card {ids} removed, no card remained, so note also removed." Anki
  was asked to remove cards, but not for any previously listed reason.
* "Removing notes  {ids}" Similarly to last case, this just means that
  we have no informations more precise to give.
## Warning
It is highly probable that this add-on will be incompatible with other
add-ons.  Because it changes a lot of things. Sadly, it seems hard to
do really better. Please let me know whether you find some problem,
with which add-on you have those problem.  It means that this add-on
may be better for debugging purpose than for every day use. I'm not
sur.

In particular it is incompatible with add-ons:
* [Quicker Anki: 802285486](https://ankiweb.net/shared/info/802285486)
* [Database checker/fixer explained, more fixers 1135180054](https://ankiweb.net/shared/info/1135180054)

Please instead use-addon
[777545149](https://ankiweb.net/shared/info/777545149) which merges
those three add-ons


## Internal
This add-on redefine the following methods:
* In `anki.collection`: `_Collection._remNotes`,
  `_Collection.fixIntegrity`, `_Collection.remCards`,
  `remNotes`,
* In `aqt.AddCards`: `AddCards.removeTempNote`,
* In `anki.sync`: `Syncer.remove`,
* In `anki.models`: `ModelManager.rem`,
  `ModelManager.remTemplate`, `_changeCards`
* In `anki.decks`: `DeckManager.rem`
* In `aqt.reviewer`: `Reviewer.onDelet`
* In `aqt.browser`: `Browser._deleteNotes`
* In `aqt.main`: `AnkiQt.BackupThread.onRemNotes`

## Version 2.0
It won't be updated. It add only a single more column, with the
reason. And it's less precise. It also only update
`_Collection._remNotes` and the methods calling it, this
`_Collection._remNotes`, i.e. _Collection.remCards,
`_Collection.fixIntegrity`, `Syncer.remove` and
`AddCards.removeTempNote`.

## Todo
May be allow to use configuration to decide which note to use, which
method to redefine.

## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-note-deletion
Addon number| [12287769](https://ankiweb.net/shared/info/12287769)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
