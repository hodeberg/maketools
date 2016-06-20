#!/usr/bin/env python

'''Converts a GNU make database into a dot graph'''

import argparse
import sys
import re
import textwrap

'''Create a legal dot ID'''
def make_id(s):
    if re.search('[^a-zA-Z0-9_]',s):
        # Need to enclose string in double quotes
        return '"{}"'.format(s)
    else:
        return s


def append_key_value(s, key, value):
    if not value:
        return s
    if s:
        s += ', '
    else:
        s = '['
    s += '{}={}'.format(key, value)
    return s


'''Defines a comma-separated list of key/value pairs
   specifying DOT node attributes'''
def create_attr_list(is_phony):
    attrs = ''
    if is_phony:
        attrs = append_key_value(attrs, 'style', 'dotted')
    # Add more attribute definitions here, later

    # Close the attribute list
    if attrs:
        attrs += ']'
    return attrs


'''Format of rule database:
# Files

[# Not a target]
target: [prerequisite]*
[#  A default, MAKEFILES, or -include/sinclude makefile.]
#  Implicit rule search has [not] been done.
# File has [not] been updated
'''

def convert():
    l = ''
    # Loop until start of files section (or EOF)
    while True:
        l = sys.stdin.readline()
        if (not l) or (l == '# Files\n'):
            break;

    if not l:
        return
    # Process rules until done
    while True:
        # Move forward to the next rule
        while True:
            l = sys.stdin.readline()
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
        t = make_id(target)
        # We do not want .PHONY to show up as a node in the graph
        if target != '.PHONY':
            if prerequisites:
                (order, sep2, order_only) = prerequisites.partition('|')
                for p in order.split():
                    # There may be a stray colon here from a double-colon rule
                    if p != ':':
                        print '{} -> {};'.format(t, make_id(p))
                for p in order_only.split():
                    print t, '->', make_id(p), '[style=dotted];'
        # Read the comments below the rule, and use its info
        # to color the node
        is_phony = False;
        while True:
            l = sys.stdin.readline()
            if l[0] != '#' and l[0] != '\t':
                break;
            if l.startswith('#  Phony target'):
                is_phony = True;
        attrs = create_attr_list(is_phony)
        print '{} {};'.format(t, attrs)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent('''\
           Converts stdin data created by "make -qpR" into dot data on stdout.
               Example: make -qpR | make2dot > db.dot
           The .PHONY node is not present in the output.
           .PHONY nodes are marked with the attribute [style=dotted]
           Edges for order-only dependencies are marked with [style=dotted]'''))
    global args
    args = parser.parse_args()
    print 'digraph make {'
    convert()
    print '}'

if __name__ == "__main__":
    main()
