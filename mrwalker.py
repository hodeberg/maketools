#!/usr/bin/env python

'''Parses a GNU make database into memory.
   Displays a node's parents and children using python-tk.
   Allows user to traverse the hierarchy.'''

import argparse
import sys
import textwrap
import logging
from Tkinter import *

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



class SelectionWindow:
    def __init__(self, masterWindow, cmdWindow):
        self.win = Listbox(masterWindow, 
                           selectmode=SINGLE,
                           font='Courier')
        self.cmdWin = cmdWindow
        self.win.bind('<Return>', self.handleKey)
               
    def handleKey(self, event):
        l = self.win.get(ACTIVE).split(':')[-1].strip()
        self.update(l, all_targets, all_children)

    def update(self, node, targets, children):
        self.win.delete(0, END)
        parents = children[node] if node in children else []
        (order, order_only, cmds) = targets[node]
        all_lines = parents
        all_lines.append('  ' + node)
        all_lines.extend(['    P: ' + x for x in order])
        all_lines.extend(['    O: ' + x for x in order_only])
        for l in all_lines:
            self.win.insert(END, l)
        target_ix = len(parents)
        self.win.activate(target_ix)
        self.win.see(target_ix)
        self.cmdWin.update(cmds)


class CmdWindow:
    def __init__(self, masterWindow):
        self.win = Text(masterWindow)
        self.win.config(state=DISABLED)

    def update(self, cmds):
        self.win.config(state=NORMAL)
        self.win.delete(1.0, END)
        for l in cmds:
            self.win.insert(END, l)
        self.win.config(state=DISABLED)

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent('''\
           Graphically displays the immediate environment of a make target.
           Allows interactive traversing of the dependency tree.
           For a target, the program will present an indented list.
           First in the list are the nodes that
           this target is a prerequisite to.
           Then the target itself, indented two spaces.
           Finally the target's prerequisites, prepended with either
           P: (normal prerequisite) or O: (order-only prerequisite). 
           If the rule has a set of commands, these are shown in a 
           separate window on the bottom of the screen (if the -c
           option is used).
           To traverse the tree, use:
           * up/down keys to move the cursor to the desired node.
           * pgup/pgdn keys to move one page at a time.
           * home/end keys to move to the beginning/end of the list
           * Enter key to make the selected node the new target.'''))

    parser.add_argument('node')
    parser.add_argument('-f', '--file', action='store',
                        help='make file to parse', required=True)
    parser.add_argument('-l', '--logfile', action='store',
                        help='optional file to store diagnostics in')

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

    hi = 900
    m = PanedWindow(orient=VERTICAL, width=1200, height=hi)
    m.pack(fill=BOTH, expand=1)

    bottom = CmdWindow(m)
    top = SelectionWindow(m, bottom)

    m.add(top.win)
    m.paneconfig(top.win, minsize=hi*0.8)
    m.add(bottom.win)
    top.update(args.node, all_targets, all_children)
    mainloop()
    


if __name__ == "__main__":
    main()
    if args.logfile:
        logging.shutdown()

        
