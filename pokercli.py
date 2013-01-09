#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.

"""
I found this copyright notice, next in the same repository where a copy of the original file was.
I made minor changes to this file.

Olaf Gladis olaf@pokermania.de

Copyright (c) 2001-2006
Allen Short
Andrew Bennetts
Apple Computer, Inc.
Benjamin Bruheim
Bob Ippolito
Canonical Limited
Christopher Armstrong
David Reid
Donovan Preston
Eric Mangold
Itamar Shtull-Trauring
James Knight
Jason A. Mobarak
Jonathan Lange
Jonathan D. Simms
Jp Calderone
J_Hermann
Kevin Turner
Mary Gardiner
Matthew Lefkowitz
Massachusetts Institute of Technology
Moshe Zadka
Paul Swartz
Pavel Pergamenshchik
Ralph Meijer
Sean Riley
Travis B. Hartwell
  
Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


This is an example of integrating curses with the twisted underlying    
select loop. Most of what is in this is insignificant -- the main piece 
of interest is the 'CursesStdIO' class.                                 

This class acts as file-descriptor 0, and is scheduled with the twisted
select loop via reactor.addReader (once the curses class extends it
of course). When there is input waiting doRead is called, and any
input-oriented curses calls (ie. getch()) should be executed within this
block.

Remember to call nodelay(1) in curses, to make getch() non-blocking.
"""

# System Imports
import curses
import curses.wrapper

# Twisted imports
from twisted.internet import reactor
# from twisted.python import log

from pokerprotocol import PokerFactory

class TextTooLongError(Exception):
    pass


class CursesStdIO:
    """fake fd to be registered as a reader with the twisted reactor.
       Curses classes needing input should extend this"""

    def fileno(self):
        """ We want to select on FD 0 """
        return 0

    def doRead(self):
        """called when input is ready"""

    def logPrefix(self): return 'CursesClient'


class Screen(CursesStdIO):
    def __init__(self, stdscr, protocol=None):
        self.timer = 0
        self.statusText = "TEST CURSES APP -"
        self.searchText = ''
        self.stdscr = stdscr
        self._logfn = ""
        if self._logfn:
            open(self._logfn, "w").close()

        # set screen attributes
        self.stdscr.nodelay(1) # this is used to make input calls non-blocking
        curses.cbreak()
        self.stdscr.keypad(1)
        curses.curs_set(2)

        self.rows, self.cols = self.stdscr.getmaxyx()
        self.lines = []

        curses.start_color()

        # create color pair's 1 and 2
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_YELLOW)

        self.paintStatus(self.statusText)
        self._p = protocol

    def connectionLost(self, reason):
        self.close()

    def _log_into_file(self, text):
        if self._logfn:
            with open(self._logfn, "a") as fd:
                fd.write(text+'\n')
        
    def addLine(self, text):
        """ add a line to the internal list of lines"""
        self._log_into_file(text)
        self.lines.append(text)
        self.redisplayLines()
        self._pos_cursor()

    def redisplayLines(self):
        return self._redisplayLines()
        self.paintDebug()
    def _redisplayLines(self):
        """ method for redisplaying lines 
            based on internal list of lines """

        self.stdscr.clear()
        self.paintStatus(self.statusText)
        i = 0
        index = len(self.lines) - 1
        while i < (self.rows - 3) and index >= 0:
            self.stdscr.addstr(self.rows - 3 - i, 0, self.lines[index][:self.cols], 
                               curses.color_pair(2))
            i += 1
            index -= 1
        self.paintDebug()
        self.stdscr.refresh()
        self._pos_cursor()

    def paintDebug(self):
        # import rpdb2; rpdb2.start_embedded_debugger("haha")
        if not self._p:
            return
        lines = self._p.getDebugLines()
        i = 0
        index = len(lines) - 1
        self.stdscr.addstr(0, max(self.cols-70, 1), "%-70s" % "Debug:", 
                               curses.color_pair(3))
        while i < (self.rows - 3) and index >= 0:
            self.stdscr.addstr(i+1, max(self.cols-70, 1), "%-70s" % lines[index][:70], 
                               curses.color_pair(3))
            i += 1
            index -= 1
        self.stdscr.refresh()

    def paintStatus(self, text):
        if len(text) > self.cols: raise TextTooLongError
        self.stdscr.addstr(self.rows-2,0,text + ' ' * (self.cols-len(text)), 
                           curses.color_pair(1))
        # move cursor to input line
        self._pos_cursor()

    def executeCmd(self, cmd):
        self.addLine(cmd)

    def doRead(self):
        """ Input is ready! """
        curses.noecho()
        self.timer = self.timer + 1
        c = self.stdscr.getch() # read a character

        if c == curses.KEY_BACKSPACE:
            self.searchText = self.searchText[:-1]
        elif c == ord('\t'):
            #TODO tab completion
            self.paintDebug()
            return
        elif c in (curses.KEY_MOUSE, curses.KEY_SF, curses.KEY_SR):
            return
        elif c in (curses.KEY_UP, curses.KEY_DOWN):
            return
        elif c == curses.KEY_ENTER or c == 10:
            if len(self.searchText) == 0: return
            self.executeCmd(self.searchText)
            self.stdscr.refresh()
            self.searchText = ''
        elif 0 <= c <= 255:
            if len(self.searchText) == self.cols-2: return
            try:
                self.searchText = self.searchText + chr(c)
            except:
                self.addLine(">>> %r " % c)
        else:
            self.addLine(">>> %r " % c)
            return

        self.stdscr.addstr(self.rows-1, 0, 
                           self.searchText + (' ' * (
                           self.cols-len(self.searchText)-2)))
        
        self.paintStatus(self.statusText + ' %d' % len(self.searchText))
        self.stdscr.refresh()
        curses.echo()

    def _pos_cursor(self):
        self.stdscr.move(self.rows-1, len(self.searchText))

    def close(self):
        """ clean up """

        curses.nocbreak()
        self.stdscr.keypad(0)
        curses.echo()
        curses.endwin()

if __name__ == '__main__':
    import locale
    locale.setlocale(locale.LC_ALL,"")
    stdscr = curses.initscr() # initialize curses
    screen = Screen(stdscr)   # create Screen object
    stdscr.refresh()
    def logItG(self, astr, prefix=" [D] "):
        screen.addLine(prefix + str(astr))
    pokerFactory = PokerFactory(screen, msgpokerurl="http://poker.pokermania.de/")
    reactor.addReader(screen) # add screen object as a reader to the reactor
    reactor.connectTCP("poker.pokermania.de",19380,pokerFactory) # connect to pokernetwork
    reactor.run() # have fun!
    screen.close()