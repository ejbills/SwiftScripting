# Copyright (c) 2015 Majesty Software.

#

# Permission is hereby granted, free of charge, to any person obtaining a copy

# of this software and associated documentation files (the "Software"), to deal

# in the Software without restriction, including without limitation the rights

# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell

# copies of the Software, and to permit persons to whom the Software is

# furnished to do so, subject to the following conditions:

#

# The above copyright notice and this permission notice shall be included in

# all copies or substantial portions of the Software.

#

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR

# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,

# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE

# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER

# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,

# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN

# THE SOFTWARE.

#

# Converts Objective-C interface generated by sdp to a collection of

# Swift protocol definitions.

#

# Sample usage:

#

# sdef /Applications/App.app > App.sdef

# sdp -fh --basename App App.sdef

# sbhc.py App.h

#

# Note that some manual intervention may be required to correct errors in the

# sdef file emitted by the sdef tool.

#



import sys

import struct

import re

import platform

from itertools import chain

from clang.cindex import TranslationUnit, CursorKind, Config, TypeKind



Config.set_library_path("/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib")



# See https://developer.apple.com/library/content/documentation/Swift/Conceptual/Swift_Programming_Language/LexicalStructure.html

PARAMETER_KEYWORDS = ['let', 'var', 'inout']

GENERAL_KEYWORDS = [

    'associatedtype', 'class', 'deinit', 'enum', 'extension',

    'fileprivate', 'func', 'import', 'init', 'inout', 'internal', 'let', 'open',

    'operator', 'private', 'protocol', 'public', 'static', 'struct', 'subscript',

    'typealias', 'var', 'break', 'case', 'continue', 'default', 'defer', 'do', 'else',

    'fallthrough', 'for', 'guard', 'if', 'in', 'repeat', 'return', 'switch', 'where',

    'while', 'as', 'Any', 'catch', 'false', 'is', 'nil', 'rethrows', 'super', 'self',

    'Self', 'throw', 'throws', 'true', 'try', '_'

]



TYPE_DICT = {

    'BOOL': 'Bool',

    'double': 'Double',

    'long': 'Int64',

    'int': 'Int',

    'id': 'Any',

    'SEL': 'Selector',

    'NSArray': '[Any]',

    'NSData': 'Data',

    'NSDate': 'Date',

    'NSDictionary': '[AnyHashable : Any]',

    'NSInteger': 'Int',

    'NSString': 'String',

    'NSURL': 'URL',

}



OBJECT_KINDS = [TypeKind.OBJCID, TypeKind.OBJCOBJECTPOINTER]



BASE_PROTOCOLS = """

@objc public protocol SBObjectProtocol: NSObjectProtocol {

    func get() -> Any!

}

@objc public protocol SBApplicationProtocol: SBObjectProtocol {

    func activate()

    var delegate: SBApplicationDelegate! { get set }

    var isRunning: Bool { get }

}

"""



GENERIC_PATTERN = re.compile(r'(.*)<(.*)>.*')

ALL_CAPS_RE = re.compile('([A-Z]+)($)')

SINGLE_CAP_RE = re.compile('([A-Z])([^A-Z]+.*)')

MULTIPLE_CAPS_RE = re.compile('([A-Z]+)([A-Z]([^0-9]+.*))')

CAPS_TO_DIGIT_RE = re.compile('([A-Z]+)([0-9]+.*)')





def safe_name(name, keywords=PARAMETER_KEYWORDS):

    return f'`{name}`' if name in keywords else name





def arg_name(name, position=0):

    if position > 0:

        return f'{safe_name(name)} {name}' if name.endswith('_') else safe_name(name)

    return f'_ {safe_name(name)}'





def type_for_spelling(spelling):

    obj_type_string = spelling.strip().split(" ")[0]

    return TYPE_DICT.get(obj_type_string, obj_type_string)





def type_for_type(objc_type, as_arg=False):

    generic_match = GENERIC_PATTERN.match(objc_type.spelling)

    if generic_match:

        base_type, generic_parts_str = generic_match.groups()

        opening, closing = {'NSSet': ('Set<', '>')}.get(base_type, ('[', ']'))

        mapped_parts = [type_for_spelling(generic_part.strip()) for generic_part in generic_parts_str.split(",")]

        result_type = opening + " : ".join(mapped_parts) + closing

    else:

        result_type = type_for_spelling(objc_type.spelling)

    return result_type + '!' if as_arg and objc_type.kind in OBJECT_KINDS else result_type





def name_from_path(path):

    return os.path.splitext(os.path.basename(path))[0]





def strip_prefix(prefix, a_string):

    return a_string[len(prefix):] if a_string.startswith(prefix) else a_string





def enum_case(prefix, enum_case):

    stripped_case = strip_prefix(prefix, enum_case)

    converted_enum_case = stripped_case

    for regex in (ALL_CAPS_RE, SINGLE_CAP_RE, CAPS_TO_DIGIT_RE, MULTIPLE_CAPS_RE):

        match = regex.match(stripped_case)

        if match:

            groups = match.groups()

            converted_enum_case = groups[0].lower() + groups[1]

            break

    return safe_name(converted_enum_case, keywords=GENERAL_KEYWORDS)





def cursor_super_entity(cursor):

    tokens = [token.spelling for token in cursor.get_tokens()]

    return tokens[4] if tokens[3] == ":" and len(tokens) > 4 else None





class SBHeaderProcessor:

    swift_file = None



    def __init__(self, file_path):

        self.file_path = file_path

        with open(file_path, 'r') as fid:

            self.lines = fid.readlines()

        self.app_name = name_from_path(file_path)

        self.category_dict = {}



    def line_comment(self, cursor):

        line = self.lines[cursor.location.line - 1]

        parts = line.strip().split('//')

        return f' //{parts[1]}' if len(parts) == 2 else ''



    def emit_enums(self, cursors):

        for cursor in cursors:

            self.emit_line(f'// MARK: {cursor.spelling}')

            self.emit_line(f'@objc public enum {cursor.spelling} : AEKeyword {{')

            for decl in [child for child in cursor.get_children() if child.kind == CursorKind.ENUM_CONSTANT_DECL]:

                self.emit_line(f'    case {enum_case(cursor.spelling, decl.spelling)} = {hex(decl.enum_value)} /* {repr(struct.pack("!i", decl.enum_value))} */')

            self.emit_line('}\n')



    def emit_line(self, line=''):

        self.swift_file.write(line + '\n')



    def emit_property(self, cursor):

        swift_type = type_for_type(cursor.type)

        name = safe_name(cursor.spelling, keywords=GENERAL_KEYWORDS)

        self.emit_line(f'    @objc optional var {name}: {swift_type} {{ get }}{self.line_comment(cursor)}')



    def emit_function(self, cursor):

        func_name = safe_name(cursor.spelling.split(':')[0], keywords=GENERAL_KEYWORDS)

        parameter_cursors = [child for child in cursor.get_children() if child.kind == CursorKind.PARM_DECL]

        parameters = [f'{arg_name(child.spelling, position=parameter_cursors.index(child))}: {type_for_type(child.type, as_arg=True)}' for child in parameter_cursors]

        return_type = [child.type for child in cursor.get_children() if child.kind != CursorKind.PARM_DECL]

        return_string = f' -> {type_for_type(return_type[0])}' if return_type else ''

        self.emit_line(f'    @objc optional func {func_name}({", ".join(parameters)}){return_string}{self.line_comment(cursor)}')



    def emit_protocol(self, cursor):

        protocol_name = cursor.spelling

        self.emit_line(f'// MARK: {protocol_name}')

        cursor_is_interface = cursor.kind == CursorKind.OBJC_INTERFACE_DECL

        super_entity = cursor_super_entity(cursor)

        if cursor_is_interface:

            implemented_protocols = [child.spelling for child in cursor.get_children() if child.kind == CursorKind.OBJC_PROTOCOL_REF]

            super_protocol = super_entity if not super_entity.startswith('SB') else f'{super_entity}Protocol'

            implemented_protocols.insert(0, super_protocol)

            protocols = ", ".join(implemented_protocols)

        else:

            protocols = super_entity

        extends = f': {protocols}' if protocols else ''

        self.emit_line(f'@objc public protocol {protocol_name}{extends} {{')



        property_getters = [child.spelling for child in chain(cursor.get_children(), self.category_dict.get(cursor.spelling, [])) if child.kind == CursorKind.OBJC_PROPERTY_DECL]

        function_list = property_getters

        emitted_properties = []

        implemented_protocols = []

        for child in chain(cursor.get_children(), self.category_dict.get(cursor.spelling, [])):

            if child.kind == CursorKind.OBJC_PROPERTY_DECL and child.spelling not in emitted_properties:

                self.emit_property(child)

                emitted_properties.append(child.spelling)

            elif child.kind == CursorKind.OBJC_INSTANCE_METHOD_DECL and child.spelling not in function_list:

                self.emit_function(child)

                function_list.append(child.spelling)

            elif child.kind == CursorKind.OBJC_PROTOCOL_REF:

                implemented_protocols.append(child.spelling)

        self.emit_line('}')

        if cursor_is_interface:

            extension_class = super_entity if super_entity.startswith('SB') else 'SBObject'

            self.emit_line(f'extension {extension_class}: {protocol_name} {{}}\n')

        else:

            self.emit_line()



    def gather_categories(self, categories):

        for category in categories:

            children = [child for child in category.get_children() if child.kind != CursorKind.OBJC_CLASS_REF]

            class_item = [child for child in category.get_children() if child.kind == CursorKind.OBJC_CLASS_REF][0]

            key = class_item.spelling

            category_items = self.category_dict.get(key, [])

            self.category_dict[key] = category_items + children



    def emit_swift(self):

        cmake_args = ["-ObjC"]

        mac_os_version = float('.'.join(platform.mac_ver()[0].split('.')[:2]))  # poor man's version fetch

        if mac_os_version >= 10.13:

            cmake_args.extend([

                "-I/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/usr/include/",

                "-F/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/System/Library/Frameworks/"

            ])

        translation_unit = TranslationUnit.from_source(self.file_path, args=cmake_args)

        with open(f'{self.app_name}.swift', 'w') as self.swift_file:

            for inclusion in translation_unit.get_includes():

                if inclusion.depth == 1:

                    include = inclusion.include.name

                    self.emit_line(f'import {name_from_path(include)}')

            self.emit_line(BASE_PROTOCOLS)

            cursor = translation_unit.cursor

            local_children = [child for child in cursor.get_children() if child.location.file and child.location.file.name == self.file_path]

            enums = [child for child in local_children if child.kind == CursorKind.ENUM_DECL]

            self.emit_enums(enums)

            for child in [child for child in local_children if child.kind == CursorKind.OBJC_PROTOCOL_DECL]:

                self.emit_protocol(child)

            categories = [child for child in local_children if child.kind == CursorKind.OBJC_CATEGORY_DECL]

            self.gather_categories(categories)

            for child in [child for child in local_children if child.kind == CursorKind.OBJC_INTERFACE_DECL]:

                self.emit_protocol(child)





def main(file_path):

    header_processor = SBHeaderProcessor(file_path)

    header_processor.emit_swift()





if __name__ == '__main__':

    main(sys.argv[1])