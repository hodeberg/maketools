#!/usr/bin/env python

'''extracts dependencies to a node from a dot graph'''

import os
import subprocess
import argparse

def filter(node, direction, mode, depth):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    gvpr_file = os.path.join(script_dir, 'deps.gvpr')
    cmd_args = ['gvpr',
                '-a', '{} {} {} {}'.format(node,
                                           direction,
                                           mode,
                                           str(depth)),
                '-f', gvpr_file]
    p = subprocess.Popen(cmd_args)
    out, err = p.communicate()

def main():
    usage = '''A filter which produces a subgraph containing the recursive
               targets or prerequisites of a make target.
               The filter makes use of the gvpr command internally.'''
    parser = argparse.ArgumentParser(description=usage)
    parser.add_argument('node')
    parser.add_argument('-r', '--reverse', action='store_true',
                        help='traverse graph backwards')
    parser.add_argument('-i', '--indent', action='store_true',
                        help='print indented list of dependencies, instead of a dot graph')
    parser.add_argument('-d', '--depth', type=int,
                        default=0,
                        help='number of levels to descend.')
    args = parser.parse_args()
    if args.reverse:
        direction = 'up'
    else:
        direction = 'down'
    if args.indent:
        mode = 'indent'
    else:
        mode = 'graph'
    filter(args.node, direction, mode, args.depth)

if __name__ == "__main__":
    main()
