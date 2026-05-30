# Branch hazard program
# r1 decreases from 2 to 0.
# beqz r1 end creates a control hazard.
# beqz r0 loop works as an unconditional branch.

addi r1 r0 2
loop:
addi r1 r1 -1
beqz r1 end
add r2 r2 r1
beqz r0 loop
end:
halt