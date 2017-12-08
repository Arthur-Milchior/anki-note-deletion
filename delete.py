# -*- coding: utf-8 -*-
#Copyright: Arthur Milchior arthur@milchior.fr
#License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
#Feel free to contribute to this code on https://github.com/Arthur-Milchior/anki-note-deletion
#


from anki.hooks import addHook, remHook
from anki.consts import *
from aqt.main import AnkiQt
from anki.sync import Syncer
from aqt.addcards import AddCards
import re
import signal
import stat
import zipfile
import gc
import time
from threading import Thread

from send2trash import send2trash
from aqt.qt import *
from anki.collection import _Collection
from anki.utils import  isWin, isMac, intTime, splitFields, ids2str
from anki.hooks import runHook, addHook
import aqt
import aqt.progress
import aqt.webview
import aqt.toolbar
import aqt.stats
from aqt.utils import saveGeom, restoreGeom, showInfo, showWarning, \
    restoreState, getOnlyText, askUser, applyStyles, showText, tooltip, \
    openHelp, openLink, checkInvalidFilename, getFile
import sip



def onRemNotes(col, nids, reason=""):
    """Append (id, model id and fields) to the end of deleted.txt
     This is done for each id of nids.        
    This method is added to the hook remNotes; and executed on note deletion.
    """
    path = os.path.join(aqt.mw.pm.profileFolder(), "deleted.txt")
    existed = os.path.exists(path)
    with open(path, "ab") as f:
        if not existed:
            f.write(b"nid\tmid\tfields\n")
        for id, mid, flds in col.db.execute(
                "select id, mid, flds from notes where id in %s" %
            ids2str(nids)):
            fields = splitFields(flds)
            f.write(("\t".join([str(id), str(mid)] + fields+([reason] if reason else []))).encode("utf8"))
            f.write(b"\n")


# addHook("remNotes",onRemNotes)

def _remNotes(col, ids, reason=""):
    "Bulk delete notes by ID. Don't call this directly."
    if not ids:
        return
    strids = ids2str(ids)
    # we need to log these independently of cards, as one side may have
    # more card templates
    onRemNotes(col,ids,reason=reason)
    col._logRem(ids, REM_NOTE)
    col.db.execute("delete from notes where id in %s" % strids)

_Collection._remNotes=_remNotes

def remCards(self, ids, notes=True):
    """Bulk delete cards by ID.
    keyword arguments:
    notes -- whether note without cards should be deleted."""
    if not ids:
        return
    sids = ids2str(ids)
    nids = self.db.list("select nid from cards where id in "+sids)
    # remove cards
    self._logRem(ids, REM_CARD)
    self.db.execute("delete from cards where id in "+sids)
    # then notes
    if not notes:
        return
    nids = self.db.list("""
select id from notes where id in %s and id not in (select nid from cards)""" %
                 ids2str(nids))
    self._remNotes(nids,reason= "_Collection.remCards: There were no card left for this note.")#todo: why delete some cards ?

_Collection.remCards=remCards


def fixIntegrity(self):
    "Fix possible problems and rebuild caches."
    problems = []
    self.save()
    oldSize = os.stat(self.path)[stat.ST_SIZE]
    if self.db.scalar("pragma integrity_check") != "ok":
        return (_("Collection is corrupt. Please see the manual."), False)
    # note types with a missing model
    ids = self.db.list("""
select id from notes where mid not in """ + ids2str(self.models.ids()))
    if ids:
        problems.append(
            ngettext("Deleted %d note with missing note type.",
                     "Deleted %d notes with missing note type.", len(ids))
                     % len(ids))
        self.remNotes(ids, reason="_Collection.fixIntegrity: Note with a missing note type")
    # for each model
    for m in self.models.all():
        for t in m['tmpls']:
            if t['did'] == "None":
                t['did'] = None
                problems.append(_("Fixed AnkiDroid deck override bug."))
                self.models.save(m)
        if m['type'] == MODEL_STD:
            # model with missing req specification
            if 'req' not in m:
                self.models._updateRequired(m)
                problems.append(_("Fixed note type: %s") % m['name'])
            # cards with invalid ordinal
            ids = self.db.list("""
select id from cards where ord not in %s and nid in (
select id from notes where mid = ?)""" %
                               ids2str([t['ord'] for t in m['tmpls']]),
                               m['id'])
            if ids:
                problems.append(
                    ngettext("Deleted %d card with missing template.",
                             "Deleted %d cards with missing template.",
                             len(ids)) % len(ids))
                self.remCards(ids)
        # notes with invalid field count
        ids = []
        for id, flds in self.db.execute(
                "select id, flds from notes where mid = ?", m['id']):
            if (flds.count("\x1f") + 1) != len(m['flds']):
                ids.append(id)
        if ids:
            problems.append(
                ngettext("Deleted %d note with wrong field count.",
                         "Deleted %d notes with wrong field count.",
                         len(ids)) % len(ids))
            self.remNotes(ids, reason="_Collection.fixIntegrity: Wrong field count")
    # delete any notes with missing cards
    ids = self.db.list("""
select id from notes where id not in (select distinct nid from cards)""")
    if ids:
        cnt = len(ids)
        problems.append(
            ngettext("Deleted %d note with no cards.",
                     "Deleted %d notes with no cards.", cnt) % cnt)
        self._remNotes(ids, reason="_Collection.fixIntegrity: No cards for this note")
    # cards with missing notes
    ids = self.db.list("""
select id from cards where nid not in (select id from notes)""")
    if ids:
        cnt = len(ids)
        problems.append(
            ngettext("Deleted %d card with missing note.",
                     "Deleted %d cards with missing note.", cnt) % cnt)
        self.remCards(ids)
    # cards with odue set when it shouldn't be
    ids = self.db.list("""
select id from cards where odue > 0 and (type=1 or queue=2) and not odid""")
    if ids:
        cnt = len(ids)
        problems.append(
            ngettext("Fixed %d card with invalid properties.",
                     "Fixed %d cards with invalid properties.", cnt) % cnt)
        self.db.execute("update cards set odue=0 where id in "+
            ids2str(ids))
    # cards with odid set when not in a dyn deck
    dids = [id for id in self.decks.allIds() if not self.decks.isDyn(id)]
    ids = self.db.list("""
select id from cards where odid > 0 and did in %s""" % ids2str(dids))
    if ids:
        cnt = len(ids)
        problems.append(
            ngettext("Fixed %d card with invalid properties.",
                     "Fixed %d cards with invalid properties.", cnt) % cnt)
        self.db.execute("update cards set odid=0, odue=0 where id in "+
            ids2str(ids))
    # tags
    self.tags.registerNotes()
    # field cache
    for m in self.models.all():
        self.updateFieldCache(self.models.nids(m))
    # new cards can't have a due position > 32 bits
    self.db.execute("""
update cards set due = 1000000, mod = ?, usn = ? where due > 1000000
and queue = 0""", intTime(), self.usn())
    # new card position
    self.conf['nextPos'] = self.db.scalar(
        "select max(due)+1 from cards where type = 0") or 0
    # reviews should have a reasonable due #
    ids = self.db.list(
        "select id from cards where queue = 2 and due > 100000")
    if ids:
        problems.append("Reviews had incorrect due date.")
        self.db.execute(
            "update cards set due = ?, ivl = 1, mod = ?, usn = ? where id in %s"
            % ids2str(ids), self.sched.today, intTime(), self.usn())
    # and finally, optimize
    self.optimize()
    newSize = os.stat(self.path)[stat.ST_SIZE]
    txt = _("Database rebuilt and optimized.")
    ok = not problems
    problems.append(txt)
    # if any problems were found, force a full sync
    if not ok:
        self.modSchema(check=False)
    self.save()
    return ("\n".join(problems), ok)

_Collection.fixIntegrity = fixIntegrity



def syncRemove(self,graves):
        # pretend to be the server so we don't set usn = -1
        wasServer = self.col.server
        self.col.server = True
        # notes first, so we don't end up with duplicate graves
        self.col._remNotes(graves['notes'],reason="Syncer.remove: Remove from grave")
        # then cards
        self.col.remCards(graves['cards'], notes=False)
        # and decks
        for oid in graves['decks']:
            self.col.decks.rem(oid, childrenToo=False)
        self.col.server = wasServer

Syncer.remove=syncRemove

def removeTempNote(self,note):
        if not note or not note.id:
            return
        # we don't have to worry about cards; just the note
        self.mw.col._remNotes([note.id],  reason="AddCards.removeTempNote: Temporary note")
    
AddCards.removeTempNote = removeTempNote
