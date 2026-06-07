.data
  .org 0x0
  hello_msg: .string "Hello World!\n"

  .text
  .org 0x0
      lui s0, %hi(hello_msg)
      addi s0, s0, %lo(hello_msg)

  print_loop:
      lw a0, 0(s0)
      beq a0, zero, end_print
      out a0, 0
      addi s0, s0, 4
      jal zero, print_loop

  end_print:
      halt