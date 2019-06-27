import oyaml as yaml
import logging
import sys
import re
import os

from riscof.plugins.Template import pluginTemplate
import riscof.constants as constants

logger = logging.getLogger(__name__)


def eval_cond(condition, spec):
    condition = (condition.replace("check", '')).strip()
    if ':=' in condition:
        temp = condition.split(":=")
        keys = temp[0].split(">")
        for key in keys:
            try:
                spec = spec[key]
            except KeyError:
                return False
        if "regex(" in temp[1]:
            exp = temp[1].replace("regex(", "r\"")[:-1] + ("\"")
            x = re.match(eval(exp), spec)
            if x is None:
                return False
            else:
                return True


def eval_macro(macro, spec):
    args = (macro.replace("def ", " -D")).split("=")
    if (">" not in args[1]):
        return [True, str(args[0]) + "=" + str(args[1])]


def get_sign(file, spec):
    isa = spec['ISA']
    with open(file, "r") as k:
        if ('32' in isa):
            sline = lambda x: '{0:x}'.format(x).zfill(8).lower() + '\n'
        elif ('64' in isa):
            sline = lambda x: '{0:x}'.format(x).zfill(16).lower() + '\n'
        elif ('128' in isa):
            sline = lambda x: '{0:x}'.format(x).zfill(32).lower() + '\n'
        sign = ""
        lines = k.read().splitlines()
        code_start = False
        isa = None
        part_number = ''
        i = 0
        count = 0
        include = True
        while i < len(lines):
            line = lines[i]
            i += 1
            line = line.strip()
            if line == "":
                continue
            if (line.startswith("#") or line.startswith("//")):
                continue
            if "RVTEST_ISA" in line:
                isa = (((line.strip()).replace('RVTEST_ISA(\"',
                                               "")).replace("\")", "")).strip()
            if "RVTEST_CASE(" in line:
                include = True
                args = [(temp.strip()).replace("\"", '')
                        for temp in (line.strip()).replace(
                            'RVTEST_CASE_START', '')[1:-1].split(',')]
                while (line.endswith('\\')):
                    line = lines[i]
                    i += 1
                    line = (line.strip()).replace("//", '')
                    args[1] = args[1] + str(
                        (line.replace("\")", '')).replace("//", ''))
                    if ("\")" in line):
                        break
                part_number = args[0]
                conditions = (args[1].replace("//", '')).split(";")
                check = []
                define = []
                for cond in conditions:
                    cond = cond.strip()
                    if (cond.startswith('check')):
                        check.append(cond)
                    elif (cond.startswith('def')):
                        define.append(cond)
                for condition in check:
                    include = include and eval_cond(condition, spec)
                for macro in define:
                    temp = eval_macro(macro, spec)
                    include = temp[0] and include
            if ("RVTEST_SIGUPD") in line and include:
                val = int(
                    re.findall("RVTEST_SIGUPD\(.+?,.+?,.*?0x(.+)\)", line,
                               re.DOTALL)[0], 16)
                sign += sline(val)
                count += 1
        if not count % 4 == 0:
            for i in range(4 - count % 4):
                sign += sline(0)
        return sign


class from_test(pluginTemplate):

    def initialise(self, *args, **kwargs):
        self.home = constants.root
        self.suite = kwargs.get("suite")
        self.work_dir = kwargs.get("work_dir")

    def build(self, isa_yaml, platform_yaml, isa):
        logger.debug(self.name + "Build")
        with open(isa_yaml, "r") as isa_file:
            ispec = yaml.safe_load(isa_file)
        with open(platform_yaml, "r") as pt_file:
            pspec = yaml.safe_load(pt_file)
        self.data = {**ispec, **pspec}

    def simulate(self, file, isa):
        logger.debug(self.name + "Simulate")
        test_dir = os.path.join(self.work_dir,
                                str(file.replace(self.suite, '')[:-2]) + "/")
        with open(os.path.join(test_dir, self.name[:-1] + "_sign"),
                  "w") as signf:
            sign = get_sign(os.path.join(self.home, file), self.data)
            signf.write(sign)
        return os.path.join(test_dir, self.name[:-1] + "_sign")