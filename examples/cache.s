.data
.org 0x0
array:  .word 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
result: .word 0

.text
.org 0x0
_start:
    li t0, array
    li t1, 10
    li t2, 0

sum_loop:
    beqz t1, end_loop
    lw t3, 0(t0)
    add t2, t2, t3
    addi t0, t0, 4
    addi t1, t1, -1
    j sum_loop

end_loop:
    li t0, result
    sw t2, 0(t0)
    halt