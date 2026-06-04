.data
.org 0x0
prompt:  .word 87, 104, 97, 116, 63, 32, 0   
greet:   .word 72, 105, 44, 32, 0            
buffer:  .word 0, 0, 0, 0, 0, 0, 0, 0        
ptr:     .word buffer                        
flag:    .word 0                             

.text
.org 0x0000
    jal zero, start

.org 0x0004
    jal zero, isr

start:
    lui a0, %hi(prompt)
    addi a0, a0, %lo(prompt)
    jal ra, print_str

    ei
wait_loop:
    lui t0, %hi(flag)
    addi t0, t0, %lo(flag)
    lw t1, 0(t0)                                
    beq t1, zero, wait_loop          

    di
    
    lui a0, %hi(greet)
    addi a0, a0, %lo(greet)
    jal ra, print_str
    
    lui a0, %hi(buffer)
    addi a0, a0, %lo(buffer)
    jal ra, print_str

    halt

print_str:
    addi t0, a0, 0                                   
.print_loop:
    lw t1, 0(t0)                                     
    beq t1, zero, .print_end         
    out t1, 0                                        
    addi t0, t0, 4                                   
    jal zero, .print_loop
.print_end:
    jalr zero, 0(ra)                                  

isr:
    in t2, 1                                         
    
    addi t5, zero, 10
    beq t2, t5, .input_done

    lui t3, %hi(ptr)
    addi t3, t3, %lo(ptr)
    lw t4, 0(t3)                                     
    
    sw t2, 0(t4)                                     
    addi t4, t4, 4                                   
    sw t4, 0(t3)                                     
    iret                                             

.input_done:
    lui t3, %hi(ptr)
    addi t3, t3, %lo(ptr)
    lw t4, 0(t3)
    sw zero, 0(t4)
    
    lui t3, %hi(flag)
    addi t3, t3, %lo(flag)
    addi t4, zero, 1
    sw t4, 0(t3)
    iret