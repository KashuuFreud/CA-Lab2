# RAW hazard program
# lw writes r1, and the following add immediately reads r1.

addi r2 r0 100
lw r1 0 r2
add r3 r1 r1
sw r3 4 r2
halt