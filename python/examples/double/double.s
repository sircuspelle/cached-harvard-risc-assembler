.data
.org 0x0
array_ptr:   .word args
input_count: .word 0
args:        .word 0, 0, 0, 0

.text
.org 0x0
    jal zero, start

.org 0x4
    jal zero, isr

start:
    ei

wait_input:
    lui t0, %hi(input_count)
    addi t0, t0, %lo(input_count)
    lw t1, 0(t0)
    addi t2, zero, 4
    bne t1, t2, wait_input
    
    di

    lui t0, %hi(args)
    addi t0, t0, %lo(args)
    lw a1, 0(t0)  ; A_hi
    lw a0, 4(t0)  ; A_lo
    lw a3, 8(t0)  ; B_hi
    lw a2, 12(t0) ; B_lo

    add s0, a0, a2
    add s1, a1, a3
    
    bltu s0, a0, carry
    jal zero, done

carry:
    addi s1, s1, 1

done:
    addi a0, s1, 0
    jal ra, print_char 
    addi a0, s0, 0
    jal ra, print_char 
    halt

print_char:
    addi a0, a0, 48
    out a0, 0
    jal zero, 0(ra)

isr:
    in t5, 1
    
    lui t6, %hi(array_ptr)
    addi t6, t6, %lo(array_ptr)
    lw t4, 0(t6)

    sw t5, 0(t4)

    addi t4, t4, 4
    sw t4, 0(t6)

    lui t6, %hi(input_count)
    addi t6, t6, %lo(input_count)
    lw t5, 0(t6)
    addi t5, t5, 1
    sw t5, 0(t6)

    iret