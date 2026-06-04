.data
.org 0x0
prompt:       .string "What is your name?\n"
greeting:     .string "Hello, "
buffer:       .word 0, 0, 0, 0, 0, 0, 0, 0
buffer_ptr:   .word buffer
ready_flag:   .word 0

%macro li reg, val
    lui reg, %hi(val)
    addi reg, reg, %lo(val)
%endmacro

%macro print_string str_addr_reg
    mv t0, str_addr_reg
.print_loop:
    lb t1, 0(t0)
    beqz t1, .print_end
    out t1, 0
    addi t0, t0, 1
    j .print_loop
.print_end:
%endmacro

.text
.org 0x0000
    j _start

.org 0x0004
    j _isr_input

_start:
    li sp, 0x1000

    li a0, prompt
    print_string a0

    ei
wait_loop:
    li t0, ready_flag
    lw t1, 0(t0)
    beqz t1, wait_loop
    di

    li a0, greeting
    print_string a0

    li a0, buffer
    print_string a0

    halt

_isr_input:
    in t2, 1
    
    li t3, buffer_ptr
    lw t4, 0(t3)
    
    addi t5, zero, 10
    beq t2, t5, .input_done
    
    sb t2, 0(t4)
    addi t4, t4, 1
    sw t4, 0(t3)
    j .isr_exit

.input_done:
    sb zero, 0(t4)
    li t3, ready_flag
    addi t4, zero, 1
    sw t4, 0(t3)

.isr_exit:
    iret