import csv
from .debug import debug
from aqt.addcards import AddCards
from aqt.utils import tooltip
from aqt import mw
import datetime
from anki.collection import _Collection
import os
from anki.utils import intTime, ids2str, splitFields
from anki.consts import *

def _remNotes(self, ids, reason=""):
    """Bulk delete notes by ID. Don't call this directly.

    keyword arguments:
    self -- collection"""
    #only difference: adding a reason for deletion, calling onRemNotes
    if not ids:
        return
    strids = ids2str(ids)
    # we need to log these independently of cards, as one side may have
    # more card templates
    mw.onRemNotes(self,ids,reason=reason)# new
    self._logRem(ids, REM_NOTE)
    self.db.execute("delete from notes where id in %s" % strids)

_Collection._remNotes=_remNotes

def removeTempNote(self, note):
    #Only difference: adding a reason for deletion (normally it should not be logged anyway)
    debug("removeTempNote")
    if not note or not note.id:
        return
    # we don't have to worry about cards; just the note
    self.mw.col._remNotes([note.id],reason="Temporary note")
AddCards.removeTempNote=removeTempNote

def remNotes(self, ids, reason=None):
    #only diff: adding a reason for deletion
        debug("remNotes")
        """Removes all cards associated to the notes whose id is in ids"""
        self.remCards(self.db.list("select id from cards where nid in "+
                                   ids2str(ids)), reason=reason or f"Removing notes  {ids}")
_Collection.remNotes=remNotes

from aqt.reviewer import Reviewer
def onDelete(self):
    # only diff: adding a reason for deletion
        debug("onDelete")
        # need to check state because the shortcut is global to the main
        # window
        if self.mw.state != "review" or not self.card:
            return
        self.mw.checkpoint(_("Delete"))
        cnt = len(self.card.note().cards())
        id = self.card.note().id
        self.mw.col.remNotes([id],reason=f"Deletion of note {id} requested from the reviewer.")
        self.mw.reset()
        tooltip(ngettext(
            "Note and its %d card deleted.",
            "Note and its %d cards deleted.",
            cnt) % cnt)
Reviewer.onDelete=onDelete

from aqt.browser import Browser
def _deleteNotes(self):
    # only diff: adding reason
        nids = self.selectedNotes()
        if not nids:
            return
        self.mw.checkpoint(_("Delete Notes"))
        self.model.beginReset()
        # figure out where to place the cursor after the deletion
        curRow = self.form.tableView.selectionModel().currentIndex().row()
        selectedRows = [i.row() for i in
                self.form.tableView.selectionModel().selectedRows()]
        if min(selectedRows) < curRow < max(selectedRows):
            # last selection in middle; place one below last selected item
            move = sum(1 for i in selectedRows if i > curRow)
            newRow = curRow - move
        elif max(selectedRows) <= curRow:
            # last selection at bottom; place one below bottommost selection
            newRow = max(selectedRows) - len(nids) + 1
        else:
            # last selection at top; place one above topmost selection
            newRow = min(selectedRows) - 1
        self.col.remNotes(nids, reason=f"Deletion of notes {nids} requested from the browser")
        self.search()
        if len(self.model.cards):
            newRow = min(newRow, len(self.model.cards) - 1)
            newRow = max(newRow, 0)
            self.model.focusedCard = self.model.cards[newRow]
        self.model.endReset()
        self.mw.requireReset()
        tooltip(ngettext("%d note deleted.", "%d notes deleted.", len(nids)) % len(nids))

Browser._deleteNotes = _deleteNotes

from aqt.main import AnkiQt
def onRemNotes(self, col, nids, reason=""):
        debug("onRemNotes")
        """Append (reason,deletion time id, deletion time readable, id, model id, fields) to the end of deleted_long.txt

        This is done for each id of nids.
        This method is added to the hook remNotes; and executed on note deletion.
        """
        path = os.path.join(self.pm.profileFolder(), "deleted_long.txt")
        existed = os.path.exists(path)
        with open(path, "a") as f:
            if not existed:
                f.write(b"reason\tdeletion time id\thuman deletion time\tid\tmid\tfields\t\n")
            for id, mid, flds in col.db.execute(
                    "select id, mid, flds from notes where id in %s" %
                ids2str(nids)):
                fields = splitFields(flds)
                writer.writerow([reason,str(intTime()),str(datetime.datetime.now()),str(id), str(mid)]+fields)


AnkiQt.onRemNotes = onRemNotes
