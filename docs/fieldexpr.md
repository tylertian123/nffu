# Field Expressions

NFFU supports a very limited expression syntax in form definitions.

The language has three data types: `int`, `str` and `date` which are all that we need to provide inputs to google forms.
There is technically a `bool` type too, but it cannot be created without using the comparison operators.

## Literals

Two literals exist: integer and string.

Integers can be signed and are specified in base 10:

```
1
-2
3
```

Strings are specified with single quotes. Newlines/escapes other than escaping the `'` are not supported.

```
'asdf'
'boop123'
't\'s thing'
```

There is an additional "literal-like" function for creating `date`s:

```
date(2003, 12, 31)
```

## Operators

The language does process order-of-operations for arithmetic, but not for logical comparisons.

The supported operators are:

```
+, -, /, *, % -- arithmetic

>, >=, <, <=, ==, !=, ||, && -- logical
```

Unary `-` is also supported.

Addition on strings is concatenation.


## Functions

There are a variety of built-in functions. This list may be out of date, for a complete reference see `lockbox/lockbox/fieldexpr.py`.

### String manipulation

- `substr(s_in, start[, end])`

   Return the substring of `s_in` from `start` to `end` (if not provided to end of string.)

- `len(s_in)`

   Length of string `s_in`.

- `tok(s_in, s_tok, idx)`

   Return the `idx`-th part of `s_in` split by `s_tok`.

- `cap(s_in)`

   Return `s_in` capitalized.

- `upper(s_in)`

   Return `s_in` uppercased.

- `lower(s_in)`

   Return `s_in` lowercased.

- `padl(s_in, s_pad, minlen)`

   Return `s_in` padded with `s_pad` from the left to make it at least `minlen` long.

- `padr(s_in, s_pad, minlen)`

   Return `s_in` padded with `s_pad` from the right to make it at least `minlen` long.

### Type conversion

- `str(x)`

   Return `x` as string (does not work for dates.)

- `int(x)`

   Parse `x` into integer (converts booleans into 0-1.)

- `date(year, month, day)`

   Create date from year/month/day `int`s.

### Date handling
                                                                                                  
- `dyear(date)`

   Get the year from a date.

- `dmon(date)`

   Get the month from a date.

- `dday(date)`

   Get the day from a date.

                                                                                                    
- `dadd(date, offset)`

   Add `offset` days to the date.

### Utility

- `if(cond, if_true, if_false)`

   If `cond` is nonzero (or a true boolean value), return `if_true` else return `if_false`.

- `min(a, b)`
   
   Return the minimum of `a` and `b`.

- `max(a, b)`

   Return the maximum of `a` and `b`.

- `random(a, b)`
   
   Return a random integer between `a` and `b` inclusive.

## Variables

Various variables, accessible with the syntax `$variable_name`, are available:

- `$name`: student full name
- `$last_name`: student last name
- `$first_name`: student first name
- `$student_number`: student number (string)
- `$today`: current date
- `$grade`: student grade (integer)
- `$course_code`: course code
- `$teacher_name`: teacher full name
- `$day_cycle`: current school day (1-4) 

## Expected outputs

For `text` and `long-text` fields, the expected result is a `str`.

For `multiple-choice`, `dropdown` and `checkbox` fields, the expected result is an `int` corresponding to the 0-based
index of which option to select.

For `date` fields, the expected result is a `date`.

## Examples

```
substr($first_name, 0, 4)

str(dday(dadd($today, 3))) + '-test'

$grade - 9
```
