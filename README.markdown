# Py-DCPU-C #
This is a simple C compiler which builds DCPU-16 bytecode from a subset of
ANSI C. 

It currently Py-DCPU-16 supports the following features of C:
```
 - Recursion
 - Pointers
 - Flow control (if/while/for)
 - Heap allocated strings
 - local variables
 - Global variables
```
Notably, the following features are lacking:
```
 - Error handling: invalud code causes compiler crashes with no errors.
 - Any type checking what-so-ever.
 - Structs.
 - Function pointers.
 - Stack arrays.
 - Built-in library
 - Preprocessor
 - Inline assembly
```
Parsing is done through the pycparser (http://code.google.com/p/pycparser/).

## Usage ##
python compiler.py [-n] [-d] [-o outputfile] inputfile

where
   -n disables optimizations
   -d print debugging information about the compilation
   -o outfile writes the output to the given file 

The output is the instructions, as base-16 encoded words separated by spaces.

When running any file, the return from main is placed in register I.


## Example ##

```C
int main() {
  int a = 2;
  int b = 3;
  return a+b;
}
```

After running the output through a disassembler, here is what we get:

```dasm16
0x0000:
    JSR 0x04                     ; Jump to the main method
0x0004:
    SET PC, 0x02                 ; Loop here forever
    SUB SP, 0x03                 ; Make space for our variables
    SET J, SP                    ; Copy the stack pointer over to J
    SET [J], 0x02                ; Push 2 on to the stack
    SET [0x01 + J], 0x03         ; Push 3 on to the stack
    SET [0x02 + J], [J]          ; Move 2 to the result location
    ADD [0x02 + J], [0x01 + J]   ; Do the addition with 3
    ADD SP, 0x03                 ; Start tearing down the satck
    SET I, [0x02 + J]            ; Copy the return value
    SET PC, POP                  ; Return to the top
    ADD SP, 0x03                 ; Inserted in case we got here
    SET PC, POP                  ; Inserted in case we got here
```

More examples are over in the Examples folder if you want to check 'em out

