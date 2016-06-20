#!/usr/bin/env python

'''Parses a GNU make database into memory.
   Displays a node's parents and children using curses.
   Allows user to traverse the hierarchy.'''

import argparse
import sys
import textwrap
import curses
import logging


'''Format of rule database:
# Files

[# Not a target]
target: [prerequisite]*
[#  A default, MAKEFILES, or -include/sinclude makefile.]
#  Implicit rule search has [not] been done.
# File has [not] been updated
'''

# Lookup from target to prerequisite
all_targets = {}
# Lookup from prerequisite to target
all_children = {}


def add_to_child_list(children, target):
    for c in children:
        if c in all_children:
            # Child already has a parent. Append to existing list
            all_children[c].append(target)
        else:
            # First parent. Create a list
            all_children[c] = [target]


def readOneCmd(line):
    result = []
    noOfCols = 60
    while len(line) > noOfCols:
        result.append(line[:noOfCols-1] + '\\')
        line = line[noOfCols-1:]
    if line[-1] == '\n':
        line = line[:-1]
    result.append(line)
    if not result[-1].strip():
        # Remove the last line if it contains only whitespace
        result = result[:-1]
    return result

def convert(fi):
    logging.debug('Starting to parse')
    l = ''
    # Loop until start of files section (or EOF)
    while True:
        l = fi.readline()
        if (not l) or (l == '# Files\n'):
            break;

    if not l:
        return
    # Process rules until done
    while True:
        # Move forward to the next rule
        while True:
            l = fi.readline()
            if not l:
                # EOF
                break;
            if l[0] == '#':
                continue
            if ':' in l:
                break
        if not l:
            # EOF
            break;
        # Process this rule
        (target, sep, prerequisites) = l.strip().partition(':')
#        logging.debug('Rule: %s', l)
# No, this check does not work. There are double-colon rules.
#        if (target in all_targets):
#            print 'Error: target {} already exists!'.format(target);
#            sys.exit(1);

        # We do not want .PHONY to show up as a node in the graph
        cmds = []
        if target != '.PHONY':
            prereq_list = []
            order_prereq_list = []
            if prerequisites:
                (order, sep2, order_only) = prerequisites.partition('|')
                prereq_list = order.split()
                add_to_child_list(prereq_list, target)
                order_prereq_list = order_only.split()
                add_to_child_list(order_prereq_list, target)

        # Skip the comments below the rule
        while True:
            l = fi.readline()
            if l[0] == '\t':
                # Save this command, we might want to display it
                nextCmd = l.strip()
                if nextCmd:
                    cmds.append(nextCmd)
            if l[0] != '#' and l[0] != '\t':
                # Done with this rule, save and go to next
                if target != '.PHONY':
                    all_targets[target] = (prereq_list, order_prereq_list, cmds)
                break;
    logging.debug('Done parsing')

def find_parents(child):
    if not child in all_children:
        return []
    return all_children[child]


def print_deps(node):
    parents = find_parents(node)
    for p in parents:
        print 'P: {}'.format(p)
    print ' T: {}'.format(node)
    (order, order_only, cmds) = all_targets[node]
    for i in order:
        print '  C: {}'.format(i)
    for i in order_only:
        print '  O: {}'.format(i)



class BaseWindow:
    """Basic window class. Contains:
        * An array of strings to display
        * Size info
        
        Keyword arguments:
        scr : a curses screen object. Its dimensions are
              expected to be the max dimensions the screen
              can expand to, ever.
"""
    FIXED = 0
    BOTTOM = 1
    TOP = 2
    LEAVE_WINDOW = 1
    LEAVE_APP = 2
    SELECT_ITEM = 3

    def __init__(self, scr):
        self.scr = scr
        (max_y, max_x) = scr.getmaxyx()
        self.max_x = max_x
        self.max_y = max_y
        logging.debug('BaseWindow: max_x = %d', max_x)
        logging.debug('BaseWindow: max_y = %d', max_y)
        self.cur_size_y = max_y
        self.adjustMode = self.FIXED
        self.selectEnabled = False
        self.cursor_y = 0
        self.lines = []
        logging.debug('Done creating BaseWindow')

    def enableSelection(self):
        self.selectEnabled = True

    def refreshCursor(self):
        self.scr.move(self.cursor_y, 0)

    def setWinSize(self, newSize):
        assert newSize <= self.max_y
        self.scr.clear()
#        self.scr.refresh()
        self.scr.resize(newSize, self.max_x)
        self.cur_size_y = newSize

    def adjustWinSize(self, newSize):
        newSize = min(self.max_y, newSize)
        if self.adjustMode == self.FIXED:
            return
#        if self.cur_size_y == newSize:
#            return
        if not newSize > 0:
            logging.debug('BaseWindow::adjustWinSize: rejecting zero size')
            return
        if self.adjustMode == self.BOTTOM:
            self.scr.resize(newSize, self.max_x)
        elif self.adjustMode == self.TOP:
            (old_pos_y, old_pos_x) = self.scr.getbegyx()
            newPos = old_pos_y - (newSize - self.cur_size_y)
            if newSize < self.cur_size_y:
                # Moving the window downwards; we need to
                # resize (shrink) before moving
                logging.debug('BaseWindow::adjustWinSize: TOP resize(%d, %d)', 
                              newSize, self.max_x)
                self.scr.resize(newSize, self.max_x)
                logging.debug('BaseWindow::adjustWinSize: TOP mvwin(%d, 0)', 
                              newPos)
                self.scr.mvwin(newPos, 0)
            else:
                logging.debug('BaseWindow::adjustWinSize: TOP mvwin(%d, 0)', 
                              newPos)
                self.scr.mvwin(newPos, 0)
                logging.debug('BaseWindow::adjustWinSize: TOP resize(%d, %d)', 
                              newSize, self.max_x)
                self.scr.resize(newSize, self.max_x)

        else:
            assert False
        self.cur_size_y = newSize

    def fillWindow(self):
        for i in range(0, min(self.cur_size_y,len(self.lines))):
            self.writeLine(i, self.lines[i])


    def setBaseContents(self, lines):
        self.lines = lines
        if lines:
            # Avoid using zero-size windows
            self.fillWindow()
            self.scr.refresh()

    def setContents(self, lines):
#        assert len(lines) <= self.cur_size_y
        self.setBaseContents(lines[:self.cur_size_y])

    def handleCursorAboveWindow(self):
        return None

    def handleKeyUp(self):
        logging.debug('BaseWindow::handleKeyUp')
        if self.getCurrentLineIx() > 0:
            self.cursor_y -= 1
            self.refreshCursor()
            self.scr.refresh()
        else:
            return handleCursorAboveWindow()
        return (None, '')

    def handleKeyDown(self):
        logging.debug('BaseWindow::handleKeyDown')
        if self.getCurrentLineIx() < len(self.lines)-1:
            self.cursor_y += 1
            self.refreshCursor()
            self.scr.refresh()
        return (None, '')

    def getCurrentLineIx(self):
        (cursor_y, cursor_x) = self.scr.getyx()
        return cursor_y

    def decodeKey(self, c):
        logging.debug('BaseWindow::decodeKey')
        r = (None, '')
        if c == curses.KEY_UP:
            r = self.handleKeyUp()
        elif c == curses.KEY_DOWN:
            r = self.handleKeyDown()
        elif (c == curses.KEY_ENTER) or (c == 10):
            if self.selectEnabled:
                cursor_y = self.getCurrentLineIx()
                l = self.lines[cursor_y].split(':')[1].strip()
                r = (BaseWindow.SELECT_ITEM, l)
        elif c == ord('q'):
            r = (BaseWindow.LEAVE_APP, '')
        elif c == ord('\t'):
            logging.debug('BaseWindow::decodeKey: got TAB')
            r = (BaseWindow.LEAVE_WINDOW, '')
        else:
            logging.debug('Pressed unknown key: %d', c)
            pass
        return r

    def handleInput(self):
        logging.debug('BaseWindow::handleInput: entry')
        retVal = (None, '')
        while not retVal[0]:
            logging.debug('BaseWindow::handleInput: about to read key')
            key = self.scr.getch()
            logging.debug('BaseWindow::handleInput: read key: %d', key)
            retVal = self.decodeKey(key)
        logging.debug('BaseWindow::handleInput: leaving function')
        return retVal

    def writeLine(self, i, l):
        if len(l) >= self.max_x:
            l = l[:self.max_x - 2] + '*'
#        logging.debug('writeLine: len = %d', len(l))
#        logging.debug('writeLine: line = "%s"', l)
        self.scr.addstr(i, 0, l)


class ScrollingWindow(BaseWindow):
    '''Keeps a constant window size. Allows text to be larger than
       the window, and scrolls to put a subset of the text inside
       the window'''
    def __init__(self, scr):
        BaseWindow.__init__(self, scr)
        self.scroll_y = 0
        logging.debug('Done creating ScrollingWindow')

    def setCursorPos(self, y):
        self.scr.move(y, 0)
        self.cursor_y = y

    def setContents(self, lines):
        self.setBaseContents(lines)


    def fillWindow(self):
        logging.debug('ScrollingWindow::fillWindow: entry')
        part_of_scr = min(self.cur_size_y,len(self.lines)- self.scroll_y)
        logging.debug('ScrollingWindow::fillWindow: part_of_scr = %d', part_of_scr)
        for i in range(0, part_of_scr):
            self.writeLine(i, self.lines[i + self.scroll_y])
        self.refreshCursor()

    def rePaint(self):
            self.scr.clear()
            self.fillWindow()
            self.scr.refresh()

    def handleCursorAboveWindow(self):
        if self.scroll_y > 0:
            self.scroll_y -= 1
            self.rePaint()
        return None

    def handleKeyDown(self):
        logging.debug('ScrollingWindow::handleKeyDown')
        if self.getCurrentLineIx() == (self.cur_size_y-1):
            # Bottom line, we might need to scroll
            lastLineOnScreen = self.cur_size_y + self.scroll_y + 1
            logging.debug('ScrollingWindow::handleKeyDown: lastLine = %d',
                          lastLineOnScreen)
            logging.debug('ScrollingWindow::handleKeyDown: lines = %d',
                          len(self.lines))
            logging.debug('ScrollingWindow::handleKeyDown: scrSize = %d',
                          self.cur_size_y)
            logging.debug('ScrollingWindow::handleKeyDown: scroll = %d',
                          self.scroll_y)
            if lastLineOnScreen < len(self.lines):
                self.scroll_y += 1
                self.rePaint()
        else:
            BaseWindow.handleKeyDown(self)
        return (None, '')

    def handleKeyUp(self):
        logging.debug('ScrollingWindow::handleKeyUp')
        if self.getCurrentLineIx() == 0:
            # Top line, we might need to scroll
            if self.scroll_y > 0:
                self.scroll_y -= 1
                self.rePaint()
        else:
            BaseWindow.handleKeyUp(self)
        return (None, '')

    def handleKeyPgUp(self):
        logging.debug('KEY_PPAGE:')
        if self.scroll_y > 0:
            self.scroll_y -= min(self.scroll_y, self.cur_size_y)
            self.rePaint()

    def handleKeyPgDown(self):
        if (len(self.lines) - self.scroll_y) > self.cur_size_y:
            self.scroll_y += self.cur_size_y
            self.rePaint()


    def handleKeyHome(self):
        self.scroll_y = 0
        self.rePaint()


    def handleKeyEnd(self):
        while (len(self.lines) - self.scroll_y) > self.cur_size_y:
            self.scroll_y += self.cur_size_y
        self.rePaint()

    def decodeKey(self, c):
        r = (None, '')
        if c == curses.KEY_PPAGE:
            self.handleKeyPgUp()
        elif c == curses.KEY_NPAGE:
            self.handleKeyPgDown()
        elif c == curses.KEY_HOME:
            self.handleKeyHome()
        elif c == curses.KEY_END:
            self.handleKeyEnd()
        else:
            r = BaseWindow.decodeKey(self, c)
        return r


class DependencyMgr:
    CMD_SCR_SIZE = 10
    def __init__(self, scr, all_targets, all_children, show_commands):
        self.win = ScrollingWindow(scr)
        self.win.enableSelection()
        self.win.adjustMode = BaseWindow.BOTTOM
        self.all_targets = all_targets
        self.all_children = all_children
        self.show_commands = show_commands
        if show_commands:
            cmd_scr = curses.newwin(self.CMD_SCR_SIZE, self.win.max_x)
            cmd_scr.nodelay(0)
            cmd_scr.keypad(1)
#            self.cmd_win = BaseWindow(cmd_scr)
            self.cmd_win = ScrollingWindow(cmd_scr)
            self.cmd_win.adjustMode = BaseWindow.TOP
            self.cmd_win.scr.mvwin(self.win.max_y-self.CMD_SCR_SIZE, 0)
            self.win.setWinSize(self.win.cur_size_y - self.CMD_SCR_SIZE)
        logging.info('Done creating DependencyMgr')
        

    def find_parents(self, child):
        if not child in self.all_children:
            return []
        return self.all_children[child]


    def updateWinContent(self, node):
        parents = self.find_parents(node)
        (order, order_only, cmds) = self.all_targets[node]
        all_lines = ['U: ' + x for x in parents]
        all_lines.append(' T: ' + node)
        all_lines.extend(['  P: ' + x for x in order])
        all_lines.extend(['  O: ' + x for x in order_only])
        newSize = self.win.max_y
        if self.show_commands:
            cmdWinSize = min(len(cmds), self.CMD_SCR_SIZE)
            newSize -= cmdWinSize
            self.cmd_win.adjustWinSize(cmdWinSize)
            self.cmd_win.setContents(cmds)
        self.win.setWinSize(newSize)
        self.win.setCursorPos(len(parents))
        self.win.setContents(all_lines)
        
    def handleInput(self):
        inputWindow = self.win
        while 1:     
            (status, str) = inputWindow.handleInput()
        
            if status == BaseWindow.SELECT_ITEM:
                # We have a new target. Recalculate window size and content
                logging.info('Mgr: new target %s', str)
                self.updateWinContent(str)
            elif status == BaseWindow.LEAVE_APP:
                break
            elif status == BaseWindow.LEAVE_WINDOW:
                logging.debug('ScrollingWindow::handleInput: got TAB')
                # Switch cursor to other window
                if inputWindow == self.win:
                    logging.info('Mgr: switching to cmd_win')
                    inputWindow = self.cmd_win
                else:
                    logging.info('Mgr: switching to target_win')
                    inputWindow = self.win
                inputWindow.refreshCursor()


def curses_app2(scr, init_node, show_commands):
    scr.nodelay(0)
    handler = DependencyMgr(scr, all_targets, all_children, 
                            show_commands)
    handler.updateWinContent(init_node)
    logging.info('App: About to handle input')
    handler.handleInput()


               


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent('''\
           Graphically displays the immediate environment of a make target.
           Allows interactive traversing of the dependency tree.
           For a target, the program will present an indented list.
           First in the list, prependend with U:, are the nodes that
           this target is a prerequisite to.
           Then, prepended with T:, the target itself.
           Finally the target's prerequisites, prepended with either
           P: (normal prerequisite) or O: (order-only prerequisite). 
           If the rule has a set of commands, these are shown in a 
           separate window on the bottom of the screen (if the -c
           option is used).
           To traverse the tree, use:
           * up/down keys to move the cursor to the desired node.
           * pgup/pgdn keys to move one page at a time.
           * home/end keys to move to the beginning/end of the list
           * Enter key to make the selected node the new target.
           * TAB key to switch between the tree window and the
             command list window.'''))
    parser.add_argument('node')
    parser.add_argument('-f', '--file', action='store',
                        help='make file to parse', required=True)
    parser.add_argument('-l', '--logfile', action='store',
                        help='optional file to store diagnostics in')
    parser.add_argument('-c', '--commands', action='store_true',
                        default=False,
                        help='Show commands in a separate window')

    global args
    args = parser.parse_args()

    if args.logfile:
        logging.basicConfig(filename=args.logfile, level=logging.DEBUG)

    if not args.file:
        print 'You must specify a file to parse!'
        sys.exit(1)


    with open(args.file, 'r') as fi:
        print 'Opening file ' + args.file
        print 'Parsing make database. This may take a while.\n'
        convert(fi)
    if not args.node in all_targets:
        print 'Error: target {} not in any rule'.format(args.node)
        sys.exit(1)

    curses.wrapper(curses_app2, args.node, args.commands)

if __name__ == "__main__":
    main()
    if args.logfile:
        logging.shutdown()
