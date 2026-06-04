.text
.org 0x0
    jal zero, start

.org 0x4
    jal zero, isr

start:
    ei
inf_loop:
    jal zero, inf_loop

isr:
    in t0, 1
    beq t0, zero, end_cat
    out t0, 0
    iret

end_cat:
    halt