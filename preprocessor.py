#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import sys
import os
import re


def parse_define(tail):
    m = re.match(r'(([^ \(\)]+)(\(.*?\))?)( (.+))?', tail)
    _, dname, args, definition, _ = m.groups()

    if(args):
        args = re.sub(r'\(|\)', '', args)
        args = [s.strip() for s in args.split(',')]
        for i in range(len(args)):
            definition = re.sub(re.compile(args[i]),
                                '\\\\' + str(i), definition)

        defpatrn = '%s\(%s\)' % (dname,
                               ''.join('([^ ,]+),?' for i in range(len(args))))

        return (defpatrn, definition)

    else:
        return (dname, definition)


def r_macro_expander(lines, offset, define_table, define_set,
                     output_lines, scanner):
    """
    create a line buffer of the entire if block, recurse
    down into it. This will require breaking this function
    into a parser which takes scope/prior defs, lineno and
    some other stuff as arguments, but it'll be __way__
    cleaner than anything else I could do.

    When the recursive parser ends and has generated a
    line buffer and a set of replacements, then the replace
    function does the legwork to apply the appropriate
    textual transformations.
    """
    lineno = 0
    while(lineno < len(lines)):
        l = lines[lineno]
        t = None
        s = scanner.scan(l)

        if(not s[0]):
            lineno += 1
            continue

        try:
            t = s[0][0]  # should only be __one__ token
        except:
            print s
            exit(1)

        if t:
            kwrd, val = t

            if(kwrd == 'CODE'):
                output_lines.append(val)

            elif(kwrd == 'INCLUDE'):
                if('<' or '>' in val):
                    # include from STDLIB case...
                    raise NotImplementedError('STDLIB INCLUDE')
                elif('"' in val):
                    # include from local file case...
                    raise NotImplementedError('LOCAL INCLUDE')
                else:
                    # shit is fucked
                    raise Exception('Unknown include syntax')

            elif(kwrd == 'DEFINE'):
                # define case
                m, r = parse_define(val)
                if r:
                    # r is None if there is no definition for a replacement
                    # string. This way symbolic #defines will __never__ get
                    # expressed in the c code even if the name should have
                    # been matched by the expander.
                    define_table.append((m, r))
                define_set.add(m)

            elif(kwrd == 'UNDEF'):
                m, r = parse_define(val + ' (1)')
                l = [i for i in range(len(define_table))
                        if define_table[i][0] == m]
                l = [l[i] - i for i in range(len(l))]
                for i in l:
                    define_table.pop(i)
                define_set.remove(m)

            elif(kwrd == 'ERROR'):
                # @todo - should actually throw an error
                sys.stderr.write('\nError on line %i:\n\t%s' % (lineno, val))
                exit(1)

            elif(kwrd == 'WARNING'):
                sys.stderr.write('\nWarning on line %i:\n\t%s' % (lineno, val))

            elif(kwrd in ['IFDEF', 'IFNDEF']):
                ifcount, i_lineno, lbuf = 1, lineno, []
                lineno += 1

                while ifcount and (lineno < len(lines)):
                    l = lines[lineno]
                    t, s = None, scanner.scan(l)

                    if(not s[0]):
                        lineno += 1
                        continue

                    try:
                        t = s[0][0]  # should only be __one__ token
                    except:
                        print s
                        exit(1)

                    if t:
                        if(t[0] == 'ENDIF'):
                            ifcount -= 1
                        else:
                            lbuf.append(l)
                        lineno += 1

                m, r = parse_define(val + ' (1)')

                if (kwrd == 'IFDEF') and (m not in define_set): continue
                elif(kwrd == 'IFNDEF') and (m in define_set):   continue
                else:
                    # now recurse!
                    r_macro_expander(lbuf, i_lineno, define_table, define_set,
                                     output_lines, scanner)

            elif(kwrd == 'ENDIF'):
                raise SyntaxError('Unopened ENDIF directive')

            else:
                raise SyntaxError('Unknown grammar, this should be impossible')

        lineno += 1
    return output_lines, define_table


def apply_replacements(lines, replace_rules):
    """
    Takes a list of single lines and replacement rule pairs as arguments,
    applies the rules to every line in the lines list.

    This routine is revoltingly inefficient because it has to account for the
    possibility of a macro that expands to other macros
        (/) (°,,°) (/) WOOOOOPwoopwoopwoopwoop
    """
    for i in range(len(lines)):
        line = lines[i]
        times = 0
        while any(map(lambda x: (re.search(x, line) != None),
                      (a[0] for a in replace_rules))):
            if times >= 200:
                raise Exception('Macro repalcement depth exceeded, line %i' % i)
            for p, r in replace_rules:
                lines[i] = re.sub(re.compile(p), r, line)
            times += 1
            line = lines[i]
    return lines


def process(text, targetpath):
    """
    Parses/processes the text passed as the "text" argument expanding macros
    and including files by litteral insertion. Both include syntaxes are
    supported in full (relative and absolute imports).

    Intended processing sequence
    Pass 1 - read __everything__
             builds replacement regexes, evaluates imports

    Pass 2 - executes the replacements on a text litteral basis
    Pass 3 - finds and executes all #if/#endif statements on a while 1 basis
             exiting when there are no more #-prefixed lines in the file.
    Returns.
    """

    scanner = re.Scanner([
        (r' *?#include .+', lambda x, y: ('INCLUDE', y.strip()[9:])),
        (r' *?#define .+',  lambda x, y: ('DEFINE', y.strip()[8:])),
        (r' *?#ifndef .+',  lambda x, y: ('IFNDEF', y.strip()[8:])),
        (r' *?#ifdef .+',   lambda x, y: ('IFDEF', y.strip()[7:])),
        (r' *?#endif',      lambda x, y: (('ENDIF'), '')),
        (r' *?#undef .+',   lambda x, y: ('UNDEF', y.strip()[7:])),
        (r' *?#error .+',   lambda x, y: ('ERROR', y.strip()[7:])),
        (r' *?#pragma .+',  lambda x, y: ('WARNING', y.strip()[8:])),
        (r'.+',             lambda x, y: ('CODE', y))
        ])

    text_lines = text.split('\n')

    output_lines, replacements = r_macro_expander(text_lines, 0, [], set(),
                                                  [], scanner)

    output_lines = apply_replacements(output_lines, replacements)

    return '\n'.join(output_lines)


if __name__ == '__main__':
    print 'Testing define expansion....'
    print '-' * 80
    s = str(open('./preprocessor_tests/test1.c').read())
    print s
    print '-' * 80
    print process(s, '')

    print
    print
    print "Testing define substitution generation...."
    print '-' * 80
    print parse_define('foo(x, y) (x + y)')
    print parse_define('foo (900001)')
