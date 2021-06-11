#
# This source file is part of the EdgeDB open source project.
#
# Copyright 2019-present MagicStack Inc. and the EdgeDB authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


from __future__ import annotations

import click
import collections
import sys

from edb.edgeql.parser.grammar import keywords as eql_keywords
from edb.schema import schema as s_schema
from edb.tools.edb import edbcommands

from edb.server import defines as edgedb_defines

import edgedb


BOOL_LITERALS = {'true', 'false'}
SPECIAL_TYPES = {'array', 'tuple', 'enum'}
NAMES = {'edgeql'}
NAVIGATION = ('.<', '.>', '@', '.')


def die(msg):
    print(f'FATAL: {msg}', file=sys.stderr)
    sys.exit(1)


def gen_grammar_class(name, components):
    code = [f'class {name}:\n']
    for varname, values in components.items():
        code.append(f'    {varname} = (\n')
        code.extend([f'        "{val}",\n' for val in values])
        code.append(f'    )\n')

    return code


def main(names, con):
    code = [
        f'# AUTOGENERATED BY EdgeDB WITH\n'
        f'#     $ edb gen-meta-grammars {" ".join(names)}\n'
        f'\n\n'
        f'from __future__ import annotations\n'
        f'\n\n'
    ]

    # add builtins
    types = set(con.query('''
        WITH
            MODULE schema,
            T := (SELECT Type
                  FILTER Type IS (PseudoType | ScalarType | ObjectType))
        SELECT T.name[5:]
        FILTER T.name LIKE 'std::%' OR T.name LIKE 'cal::%';
    '''))
    types |= SPECIAL_TYPES
    types = sorted(types)

    constraints = sorted(set(con.query(r'''
        WITH
            MODULE schema,
            name := DISTINCT `Constraint`.name
        SELECT cname :=
            re_match(r'(?:std|sys|math)::([a-zA-Z]\w+$)', name)[0];
    ''')))

    fn_builtins = sorted(set(con.query(r'''
        WITH
            MODULE schema,
            name := DISTINCT `Function`.name
        SELECT re_match(r'(?:std|sys|math|cal)::([a-zA-Z]\w+$)', name)[0];
    ''')))

    # add non-word operators
    operators = sorted(set(con.query(r'''
        WITH MODULE schema
        SELECT _ := DISTINCT Operator.name[5:]
        FILTER not re_test(r'^[a-zA-Z ]+$', _)
        ORDER BY _;
    ''')) | {':='})

    for gname in names:
        if gname == 'edgeql':
            code.extend(gen_grammar_class(
                'EdgeQL',
                collections.OrderedDict(
                    reserved_keywords=sorted(
                        eql_keywords.reserved_keywords - BOOL_LITERALS),
                    unreserved_keywords=sorted(
                        eql_keywords.unreserved_keywords - BOOL_LITERALS),
                    bool_literals=sorted(BOOL_LITERALS),
                    type_builtins=types,
                    module_builtins=(
                        sorted((str(m) for m in s_schema.STD_MODULES))),
                    constraint_builtins=constraints,
                    fn_builtins=fn_builtins,
                    operators=operators,
                    navigation=NAVIGATION,
                )
            ))

        code.append('\n\n')

    code = ''.join(code).strip() + '\n'

    print(code, end='')


@edbcommands.command('gen-meta-grammars')
@click.argument('names', required=True, nargs=-1, metavar='NAME...')
def gen_meta_grammars(names):
    """Generate keywords, builtins, operators, etc. which can be used
    for EdgeQL and SDL grammars.

    NAME - at the moment there's only one option 'edgeql'
    """

    if names:
        for name in names:
            if name not in NAMES:
                die(f'{name} is not a valid NAME')

        if len(names) > 2:
            die(f'too many NAMES')

    con = None
    try:
        con = edgedb.connect(user=edgedb_defines.EDGEDB_SUPERUSER,
                             database=edgedb_defines.EDGEDB_SUPERUSER_DB,
                             port=5656)
        main(names, con)
    except Exception as ex:
        die(str(ex))
    finally:
        if con is not None:
            con.close()
