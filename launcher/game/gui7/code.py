# Copyright 2004-2016 Tom Rothamel <pytom@bishoujo.us>
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os
import codecs
import re
import math


class CodeGenerator(object):
    """
    This is used to generate and update the GUI code.
    """

    def __init__(self, parameters, overwrite):
        """
        Generates or updates gui.rpy.
        """

        self.p = parameters
        self.overwrite = overwrite


    def load_template(self, filename):

        target = os.path.join(self.p.prefix, filename)

        if os.path.exists(target) and not self.overwrite:
            template = self.target
        else:
            template = os.path.join(self.p.template, filename)

        with codecs.open(template, "r", "utf-8") as f:
            self.lines = [ i.rstrip() for i in f ]

    def remove_scale(self):

        def scale(m):
            original = int(m.group(1))
            scaled = int(math.ceil(original * self.p.scale))
            return str(scaled)


        lines = [ ]

        for l in self.lines:
            l = re.sub(r'gui.scale\((.*?)\)', scale, l)
            lines.append(l)

        self.lines = lines

    def update_size(self):

        gui_init = "gui.init({}, {})".format(self.p.width, self.p.height)

        lines = [ ]

        for l in self.lines:
            l = re.sub(r'gui.init\(.*?\)', gui_init, l)
            lines.append(l)

        self.lines = lines


    def update_defines(self):
        """
        Replaces define statements in gui.rpy.
        """

        lines = [ ]

        replacements = {
            'gui.ACCENT_COLOR' : repr(self.p.accent_color.hexcode),
            'gui.HOVER_COLOR' : repr(self.p.hover_color.hexcode),
            }


        for l in self.lines:

            m = re.match('^(\s*)define (.*?) =', l)

            if m:
                indent = m.group(1)
                variable = m.group(2)

                if variable in replacements:
                    l = "{}define {} = {}".format(indent, variable, replacements[variable])

            lines.append(l)

        self.lines = lines

    def write_target(self, filename):

        target = os.path.join(self.p.prefix, filename)

        if os.path.exists(target):
            backup = 1

            while True:

                bfn = "{}.{}.bak".format(target, backup)

                if not os.path.exists(bfn):
                    break

                backup += 1

            os.rename(target, bfn)

        with codecs.open(target, "w", "utf-8") as f:
            for l in self.lines:
                f.write(l + "\r\n")

    def translate_strings(self):

        lines = [ ]

        for l in self.lines:
            lines.append(l)

        self.lines = lines

    def generate_gui(self):
        self.load_template("gui.rpy")

        self.remove_scale()
        self.update_size()
        self.update_defines()

        if self.overwrite:
            self.translate_strings()

        self.write_target("gui.rpy")