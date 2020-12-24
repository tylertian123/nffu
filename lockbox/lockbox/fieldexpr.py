import lark
import datetime
import random

_grammar = r"""
?expr: comp

?comp: sum
     | comp ">" sum -> gt
     | comp ">=" sum -> ge
     | comp "<" sum -> lt
     | comp "<=" sum -> le
     | comp "==" sum -> eq
     | comp "!=" sum -> ne
     | comp "||" sum -> or_
     | comp "&&" sum -> and_

?sum: product
    | sum "+" product -> add
    | sum "-" product -> sub

?product: factor 
        | product "*" factor -> mul
        | product "/" factor -> div
        | product "%" factor -> mod

?factor: "-" factor -> neg
       | molecule

?molecule: NAME "(" [expr ("," expr)*] ")" -> func_call
         | atom

?atom: NUMBER -> number
     | STRING -> string
     | "$" NAME -> variable

%import common.CNAME -> NAME
%import common.SIGNED_INT -> NUMBER
%import common.WS_INLINE
%import common._STRING_ESC_INNER

STRING: "'" _STRING_ESC_INNER "'"

%ignore WS_INLINE
"""

@lark.v_args(inline=True)
class FETransformer(lark.Transformer):

    _fe_funcs = {
        "substr": lambda s_in, start, end=None: s_in[start:end],                    # substr(s_in, start[, end]): substring of s_in from start to end (if not provided to end of string)
        "len": len,                                                                 # len(s_in): length of string
        "tok": lambda s_in, s_tok, idx: s_in.split(s_tok)[idx],                     # tok(s_in, s_tok, idx): idx-th part of s_in split by s_tok
        "cap": lambda s_in: s_in.capitalize(),                                      # cap(s_in): s_in capitalized
        "upper": lambda s_in: s_in.upper(),                                         # upper(s_in): s_in uppercased
        "lower": lambda s_in: s_in.lower(),                                         # lower(s_in): s_in lowercased
        "padl": lambda s_in, s_pad, minlen: format(s_in, f"{{{s_pad}>{minlen}}}"),  # padl(s_in, s_pad, minlen): s_in padded with s_pad from the left to make it at least minlen long
        "padr": lambda s_in, s_pad, minlen: format(s_in, f"{{{s_pad}<{minlen}}}"),  # padr(s_in, s_pad, minlen): s_in padded with s_pad from the right to make it at least minlen long
        "if": lambda cond, if_true, if_false: if_true if cond else if_false,        # if(cond, if_true, if_false): if cond is nonzero, return if_true else return if_false

        "str": str,                                                                 # str(x): return x as string (does not work for dates)
        "int": int,                                                                 # int(x): parse x into integer
        "date": datetime.date,                                                      # date(year, month, day): create date from year/month/day ints
        
        "dyear": lambda date: date.year,                                            # dyear(date): get the year from a date
        "dmon": lambda date: date.month,                                            # dmon(date): get the month from a date
        "dday": lambda date: date.day,                                              # dday(date): get the day from a date

        "dadd": lambda date, days: date + datetime.timedelta(days=days),             # dadd(date, offset): add offset days to the date

        "min": min,
        "max": max,
        "unmax": min,
        "random": random.randint
    }

    def __init__(self, context: dict):
        super().__init__()
        self.context = context

    from operator import add, sub, mul, mod, floordiv as div, neg, gt, ge, lt, le, eq, ne

    def string(self, s):
        return s[1:-1].replace("\\'", "'")

    number = int

    or_ = lambda x, y: x or y
    and_ = lambda x, y: x and y
    
    def variable(self, name):
        return self.context[name]

    def func_call(self, name, *args):
        return FETransformer._fe_funcs[name](*args)

_parser = lark.Lark(_grammar, start="expr")

def interpret(text, context: dict):
    """
    Interpret the given text as a field-expression.
    
    `context` should be dictionary of string variables to int/string/date.

    The expected values are currently:
        - $name: student full name
        - $last_name: student last name
        - $first_name: student first name
        - $student_number: student number (string)
        - $today: current date
        - $grade: student grade (integer)
        - $course_code: course code
        - $teacher_name: teacher full name
        - $day_cycle: current school day (1-4) 
    """
    
    return FETransformer(context).transform(_parser.parse(text))
