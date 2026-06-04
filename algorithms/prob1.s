.data
.org 0x0
result: .word 0
stack:  .word 0,0,0,0,0,0,0,0,0,0,0,0,0,0

.text
.org 0x0
start:
    addi s0, zero, 0
    addi s1, zero, 999
    addi s3, zero, 100

loop_i:
    blt s1, s3, end_loops
    addi s2, s1, 0

loop_j:
    blt s2, s3, next_i    
    mul t0, s1, s2
    
    blt t0, s0, next_i    
    beq t0, s0, next_i    
    
    addi t1, t0, 0        
    addi t2, zero, 0      
    addi t4, zero, 10     

pal_loop:
    beq t1, zero, pal_done
    rem t3, t1, t4
    div t1, t1, t4
    mul t2, t2, t4
    add t2, t2, t3
    jal zero, pal_loop

pal_done:
    bne t0, t2, not_pal   
    addi s0, t0, 0

not_pal:
    addi s2, s2, -1
    jal zero, loop_j

next_i:
    addi s1, s1, -1
    jal zero, loop_i

end_loops:
    addi a0, s0, 0
    jal ra, print_int
    halt

print_int:
    addi t0, a0, 0
    addi t1, zero, 10
    lui t2, %hi(stack)
    addi t2, t2, %lo(stack)
.split_loop:
    rem t3, t0, t1
    div t0, t0, t1
    addi t3, t3, 48
    sw t3, 0(t2)
    addi t2, t2, 4
    bne t0, zero, .split_loop
    
.print_loop:
    addi t2, t2, -4
    lw t3, 0(t2)
    out t3, 0
    lui t4, %hi(stack)
    addi t4, t4, %lo(stack)
    bne t2, t4, .print_loop
    jal zero, 0(ra)