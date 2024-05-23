# THE SOFTWARE.

#

# Creates a Swift source file containing an enum encompassing the scripting

# class names for the SDEF file specified on the command line.

#

# Sample usage:

#

# sbsc.py App.sdef

#



import os

import string

import sys

from sbhc import enum_case





def transform(name_string):

    name_string = name_string.replace('"', '')

    name_string = name_string.replace('-', ' ')

    name_string = string.capwords(name_string).replace(' ', '')

    return enum_case('', name_string)





def name_from_path(path):

    last_part = os.path.basename(path)

    return os.path.splitext(last_part)[0]





def extract_cases(xpath, keyword):

    command_template = f"xmllint --xpath '{xpath}' {{}} 2>/dev/null"

    with os.popen(command_template.format(sys.argv[1])) as pipe:

        raw_names = pipe.read()

    separator = f"{keyword}="

    names = set()

    for raw_name in raw_names.strip().split(separator):

        if raw_name.strip():

            names.add(raw_name.strip())

    return names





if __name__ == "__main__":

    enum_name = f'{name_from_path(sys.argv[1])}Scripting'

    with open(f'{enum_name}.swift', 'w') as out_file:

        out_file.write(f'public enum {enum_name}: String {{\n')

        names = extract_cases("//suite/class/@name", "name")

        names = names.union(extract_cases("//suite/class-extension/@extends", "extends"))

        names = sorted(names)

        for name in names:

            out_file.write(f' case {transform(name)} = "{name}"\n')

        out_file.write('}\n')