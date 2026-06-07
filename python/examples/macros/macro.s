%define OUT_PORT 0

%macro print_newline
    addi a0, zero, 10
    out a0, OUT_PORT
%endmacro

.data
.org 0x0
my_string: .string "MACRO"

.text
.org 0x0
start:
    lui s0, %hi(my_string)
    addi s0, s0, %lo(my_string)
    
print_loop:
    lw a0, 0(s0)
    beqz a0, end_print
    out a0, OUT_PORT
    addi s0, s0, 4
    j print_loop

end_print:
    print_newline
    halt