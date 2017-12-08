delete.txt (in your profile folder) now contains a fourth column stating the reason for the card's deletion. Which method called for the deletion, and why it did it. This is particularly useful when "check database" state that some notes where removed. Now you can now exactly which one.

#Developer's note
This add-on redefine every methods calling _Collection._remNotes, hence it may be incompatible with addon redefining: _Collection.remCards, _Collection.fixIntegrity, Syncer.remove and AddCards.removeTempNote


It also redefines
_Collection._remNotes


Finally, the hook "remNote" is not called anymore when a note is removed
