.data
.org 0x0
prompt_msg: .string "What is your name?\n"
hello_msg:  .string "Hello, "
excl_msg:   .string "!\n"

name_ptr:   .word name_buf
input_done: .word 0
name_buf:   .word 0,0,0,0,0,0,0,0,0,0

.text
.org 0x0
    jal zero, start

.org 0x4
    jal zero, isr

start:
    lui s0, %hi(prompt_msg)
    addi s0, s0, %lo(prompt_msg)
    jal ra, print_string

    ei
wait_input:
    lui t0, %hi(input_done)
    addi t0, t0, %lo(input_done)
    lw t1, 0(t0)
    beq t1, zero, wait_input
    di

    lui s0, %hi(hello_msg)
    addi s0, s0, %lo(hello_msg)
    jal ra, print_string

    lui s0, %hi(name_buf)
    addi s0, s0, %lo(name_buf)
    jal ra, print_string

    lui s0, %hi(excl_msg)
    addi s0, s0, %lo(excl_msg)
    jal ra, print_string

    halt

print_string:
    lw a0, 0(s0)
    beq a0, zero, end_print_string
    out a0, 0
    addi s0, s0, 4
    jal zero, print_string
end_print_string:
    jal zero, 0(ra)

isr:
    in t5, 1
    lui t6, %hi(name_ptr)
    addi t6, t6, %lo(name_ptr)
    lw t4, 0(t6)

    sw t5, 0(t4)
    
    addi t2, zero, 10
    beq t5, t2, isr_finish
    beq t5, zero, isr_finish

    addi t4, t4, 4
    sw t4, 0(t6)
    iret

isr_finish:
    sw zero, 0(t4)
    lui t6, %hi(input_done)
    addi t6, t6, %lo(input_done)
    addi t5, zero, 1
    sw t5, 0(t6)
    iret