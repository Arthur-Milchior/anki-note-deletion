# -*- coding: utf-8 -*-
# Copyright: Arthur Milchior arthur@milchior.fr
# encoding: utf8
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
# Feel free to contribute to this code on https://github.com/Arthur-Milchior/anki-note-deletion
# Add-on number 12287769 https://ankiweb.net/shared/info/12287769
import sys
if (sys.version_info > (3, 0)):
     # Python 3 code in this block
    from . import explainDeletion21
else:
     # Python 2 code in this block
    from . import explainDeletion20

