.data
.org 0x0
array_ptr:  .word array
input_done: .word 0
stack:      .word 0,0,0,0,0,0,0,0,0,0,0
array:      .word 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0

.text
.org 0x0
    jal zero, start

.org 0x4
    jal zero, isr

start:
    ei
    
wait_input:
    lui t0, %hi(input_done)
    addi t0, t0, %lo(input_done)
    lw t1, 0(t0)
    beq t1, zero, wait_input
    di

    lui s0, %hi(array)
    addi s0, s0, %lo(array)

outer_loop:
    addi s1, zero, 0
    addi s2, s0, 0

inner_loop:
    lw t0, 0(s2)
    beq t0, zero, check_swapped
    
    lw t1, 4(s2)
    beq t1, zero, check_swapped
    
    ble t0, t1, no_swap
    
    sw t1, 0(s2)
    sw t0, 4(s2)
    addi s1, zero, 1

no_swap:
    addi s2, s2, 4
    jal zero, inner_loop

check_swapped:
    bne s1, zero, outer_loop

    addi s2, s0, 0
    
print_array:
    lw a0, 0(s2)
    beq a0, zero, end_sort
    jal ra, print_int
    
    addi t5, zero, 32
    out t5, 0
    
    addi s2, s2, 4
    jal zero, print_array

end_sort:
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

isr:
    in t5, 1
    
    lui t6, %hi(array_ptr)
    addi t6, t6, %lo(array_ptr)
    lw t4, 0(t6)    
    
    sw t5, 0(t4)    

    beq t5, zero, isr_done 

    addi t4, t4, 4  
    sw t4, 0(t6)    

    iret

isr_done:
    lui t6, %hi(input_done)
    addi t6, t6, %lo(input_done)
    addi t5, zero, 1
    sw t5, 0(t6)
    iret
