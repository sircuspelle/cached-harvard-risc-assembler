.data
.org 0x0
A_hi: .word 1
A_lo: .word 4294967295
B_hi: .word 0
B_lo: .word 2

.text
.org 0x0
start:
    lui t0, %hi(A_hi)
    addi t0, t0, %lo(A_hi)
    lw a1, 0(t0)
    lw a0, 4(t0)
    
    lui t0, %hi(B_hi)
    addi t0, t0, %lo(B_hi)
    lw a3, 0(t0)
    lw a2, 4(t0)

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