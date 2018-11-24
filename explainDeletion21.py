# -*- coding: utf-8 -*-
# Copyright: Arthur Milchior arthur@milchior.fr
# encoding: utf8
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
# Feel free to contribute to this code on https://github.com/Arthur-Milchior/anki-note-deletion
# Add-on number 12287769 https://ankiweb.net/shared/info/12287769

from anki.collection import _Collection
from anki.utils import intTime
import datetime

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

from aqt.addcards import AddCards
def removeTempNote(self, note):
    if not note or not note.id:
        return
    # we don't have to worry about cards; just the note
    self.mw.col._remNotes([note.id],reason="Temporary note")
AddCards.removeTempNote=removeTempNote

from anki.sync import Syncer
def remove(self, graves):
        # pretend to be the server so we don't set usn = -1
        self.col.server = True

        # notes first, so we don't end up with duplicate graves
        self.col._remNotes(graves['notes'],reason=f"Remove notes {graves['notes']} from grave after sync")
        # then cards
        self.col.remCards(graves['cards'], notes=False,reason=f"Remove cards {graves['cards']} from grave, after sync.")
        # and decks
        for oid in graves['decks']:
            self.col.decks.rem(oid, childrenToo=False)

        self.col.server = False
Syncer.remove=remove

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
            self.remNotes(ids,reason=f"Removing notes {ids} with missing note type")
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
                    self.remCards(ids, reason=f"Cards {ids} removed because of missing templates.")
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
                self.remNotes(ids,f"Deleted notes {ids} with wrong field count")
        # delete any notes with missing cards
        ids = self.db.list("""
select id from notes where id not in (select distinct nid from cards)""")
        if ids:
            cnt = len(ids)
            problems.append(
                ngettext("Deleted %d note with no cards.",
                         "Deleted %d notes with no cards.", cnt) % cnt)
            self._remNotes(ids,reason=f"Note {ids} with no cards")
        # cards with missing notes
        ids = self.db.list("""
select id from cards where nid not in (select id from notes)""")
        if ids:
            cnt = len(ids)
            problems.append(
                ngettext("Deleted %d card with missing note.",
                         "Deleted %d cards with missing note.", cnt) % cnt)
            self.remCards(ids,"Cards {ids} removed because of missing notes.")
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
and type = 0""", intTime(), self.usn())
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
_Collection.fixIntegrity=fixIntegrity


def remCards(self, ids, notes=True, reason=None):
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
        self._remNotes(nids, reason=reason or f"Card {ids} removed, no card remained, so note also removed.")
_Collection.remCards=remCards

from anki.models import ModelManager
def rem(self, m):
        "Delete model, and all its cards/notes."
        self.col.modSchema(check=True)
        current = self.current()['id'] == m['id']
        # delete notes/cards
        cids=self.col.db.list("""
select id from cards where nid in (select id from notes where mid = ?)""",
                                           m['id'])
        self.col.remCards(cids, reason=f"Deleting cards {cids} because we delete the model {m}")
        # then the model
        del self.models[str(m['id'])]
        self.save()
        # GUI should ensure last model is not deleted
        if current:
            self.setCurrent(list(self.models.values())[0])
ModelManager.rem = rem

def remTemplate(self, m, template):
        "False if removing template would leave orphan notes."
        assert len(m['tmpls']) > 1
        # find cards using this template
        ord = m['tmpls'].index(template)
        cids = self.col.db.list("""
select c.id from cards c, notes f where c.nid=f.id and mid = ? and ord = ?""",
                                 m['id'], ord)
        # all notes with this template must have at least two cards, or we
        # could end up creating orphaned notes
        if self.col.db.scalar("""
select nid, count() from cards where
nid in (select nid from cards where id in %s)
group by nid
having count() < 2
limit 1""" % ids2str(cids)):
            return False
        # ok to proceed; remove cards
        self.col.modSchema(check=True)
        self.col.remCards(cids,reason=f"Removing card type {template} from model {m}")
        # shift ordinals
        self.col.db.execute("""
update cards set ord = ord - 1, usn = ?, mod = ?
 where nid in (select id from notes where mid = ?) and ord > ?""",
                             self.col.usn(), intTime(), m['id'], ord)
        m['tmpls'].remove(template)
        self._updateTemplOrds(m)
        self.save(m)
        return True
ModelManager.remTemplate=remTemplate

def _changeCards(self, nids, oldModel, newModel, map):
        """Change the note whose ids are nid to the model newModel, reorder
        fields according to map. Write the change in the database
        
        Remove the cards mapped to nothing

        If the source is a cloze, it is (currently?) mapped to the
        card of same order in newModel, independtly of map.

        keyword arguments:
        nids -- the list of id of notes to change
        oldModel -- the soruce model of the notes
        newmodel -- the model of destination of the notes
        map -- the dictionnary sending to each card 'ord of the old model a card'ord of the new model or to None
        """
        d = []
        deleted = []
        for (cid, ord) in self.col.db.execute(
            "select id, ord from cards where nid in "+ids2str(nids)):
            # if the src model is a cloze, we ignore the map, as the gui
            # doesn't currently support mapping them
            if oldModel['type'] == MODEL_CLOZE:
                new = ord
                if newModel['type'] != MODEL_CLOZE:
                    # if we're mapping to a regular note, we need to check if
                    # the destination ord is valid
                    if len(newModel['tmpls']) <= ord:
                        new = None
            else:
                # mapping from a regular note, so the map should be valid
                new = map[ord]
            if new is not None:
                d.append(dict(
                    cid=cid,new=new,u=self.col.usn(),m=intTime()))
            else:
                deleted.append(cid)
        self.col.db.executemany(
            "update cards set ord=:new,usn=:u,mod=:m where id=:cid",
            d)
        self.col.remCards(deleted,reason=f"Changing notes {nids} from model {oldModel} to {newModel}, leading to deletion of {deleted}")

ModelManager._changeCards=_changeCards

def remNotes(self, ids, reason=None):
        """Removes all cards associated to the notes whose id is in ids"""
        self.remCards(self.db.list("select id from cards where nid in "+
                                   ids2str(ids)), reason=reason or f"Removing notes  {ids}")
_Collection.remNotes=remNotes

from anki.decks import DeckManager
def rem(self, did, cardsToo=False, childrenToo=True):
        """Remove the deck whose id is did.

        Does not delete the default deck, but rename it.

        Log the removal, even if the deck does not exists, assuming it
        is not default.

        Keyword arguments:
        cardsToo -- if set to true, delete its card.
        ChildrenToo -- if set to false,
        """
        if str(did) == '1':
            # we won't allow the default deck to be deleted, but if it's a
            # child of an existing deck then it needs to be renamed
            deck = self.get(did)
            if '::' in deck['name']:
                base = deck['name'].split("::")[-1]
                suffix = ""
                while True:
                    # find an unused name
                    name = base + suffix
                    if not self.byName(name):
                        deck['name'] = name
                        self.save(deck)
                        break
                    suffix += "1"
            return
        # log the removal regardless of whether we have the deck or not
        self.col._logRem([did], REM_DECK)
        # do nothing else if doesn't exist
        if not str(did) in self.decks:
            return
        deck = self.get(did)
        if deck['dyn']:
            # deleting a cramming deck returns cards to their previous deck
            # rather than deleting the cards
            self.col.sched.emptyDyn(did)
            if childrenToo:
                for name, id in self.children(did):
                    self.rem(id, cardsToo)
        else:
            # delete children first
            if childrenToo:
                # we don't want to delete children when syncing
                for name, id in self.children(did):
                    self.rem(id, cardsToo)
            # delete cards too?
            if cardsToo:
                # don't use cids(), as we want cards in cram decks too
                cids = self.col.db.list(
                    "select id from cards where did=? or odid=?", did, did)
                self.col.remCards(cids,reason=f"Removing cards {cids} because its deck {did} is deleted")
        # delete the deck and add a grave (it seems no grave is added)
        del self.decks[str(did)]
        # ensure we have an active deck.
        if did in self.active():
            self.select(int(list(self.decks.keys())[0]))
        self.save()
DeckManager.rem=rem

from aqt.reviewer import Reviewer
def onDelete(self):
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
def onRemNotes(self, col, nids,reason=""):
        """Append (reason,deletion time id, deletion time readable, id, model id, fields) to the end of deleted_long.txt

        This is done for each id of nids.        
        This method is added to the hook remNotes; and executed on note deletion.
        """
        path = os.path.join(self.pm.profileFolder(), "deleted_long.txt")
        existed = os.path.exists(path)
        with open(path, "ab") as f:
            if not existed:
                f.write(b"reason\tdeletion time id\thuman deletion time\tid\tmid\tfields\t\n")
            for id, mid, flds in col.db.execute(
                    "select id, mid, flds from notes where id in %s" %
                ids2str(nids)):
                fields = splitFields(flds)
                f.write(("\t".join([reason,intTime(),datetime.datetime.now(),str(id), str(mid)] + fields)).encode("utf8"))
                f.write(b"\n")

AnkiQt.BackupThread.onRemNotes = onRemNotes
