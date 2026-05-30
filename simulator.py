from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import os
import re


@dataclass
class Instruction:
    op: str
    raw: str
    pc: int
    rd: Optional[str] = None
    rs: Optional[str] = None
    rt: Optional[str] = None
    imm: int = 0
    label: Optional[str] = None

    def __str__(self):
        return self.raw


class PipelineSimulator:
    """A small five-stage MIPS-like pipeline simulator.

    Supported instructions:
    add rd, rs, rt
    addi rd, rs, imm
    lw rd, imm(rs)     or lw rd, imm, rs
    sw rs, imm(rt)     or sw rs, imm, rt
    beqz rs, label
    halt

    The simulator can be initialized either from program_text or from program_path.
    """

    def __init__(
        self,
        program_text: Optional[str] = None,
        program_path: Optional[str] = None,
        program_name: str = "imported.asm",
        forwarding: bool = False,
    ):
        if program_text is None and program_path is None:
            raise ValueError("Either program_text or program_path must be provided.")

        self.program_path = program_path
        self.program_name = os.path.basename(program_path) if program_path else program_name
        self.program_source = program_text if program_text is not None else self._read_file(program_path)
        self.forwarding = forwarding

        self.instructions: List[Instruction] = []
        self.labels: Dict[str, int] = {}

        self.pc = 0
        self.cycle = 0
        self.instruction_count = 0
        self.stall_count = 0
        self.flush_count = 0

        self.finished_fetch = False
        self.halted = False
        self.last_event = "Ready."

        self.registers: Dict[str, int] = {f"r{i}": 0 for i in range(32)}
        self.memory: Dict[int, int] = {
            0: 0,
            4: 0,
            8: 0,
            12: 0,
            100: 10,
            104: 0,
        }

        self.IF = None
        self.ID = None
        self.EX = None
        self.MEM = None
        self.WB = None

        self.load_program()

    @staticmethod
    def _read_file(path: str) -> str:
        with open(path, "r", encoding="utf-8") as file:
            return file.read()

    @staticmethod
    def normalize_register(reg: Optional[str]) -> Optional[str]:
        if reg is None:
            return None
        reg = reg.strip().replace("$", "").lower()
        return reg

    @staticmethod
    def parse_int(value: str) -> int:
        value = value.strip()
        if value.lower().startswith("0x"):
            return int(value, 16)
        return int(value)

    def clean_source_lines(self) -> List[str]:
        lines = []

        for raw_line in self.program_source.splitlines():
            line = raw_line.strip()

            for marker in ["#", "//", ";"]:
                if marker in line:
                    line = line.split(marker, 1)[0].strip()

            if not line:
                continue

            # Ignore section directives. The simulator focuses on executable lines.
            if line.lower() in [".text", ".data"]:
                continue

            # Ignore simple data declarations such as A: .word 1, 2, 3.
            if ".word" in line.lower():
                continue

            lines.append(line)

        return lines

    def load_program(self):
        raw_lines = self.clean_source_lines()
        cleaned_lines = []
        pc = 0

        for line in raw_lines:
            if ":" in line:
                label_part, rest = line.split(":", 1)
                label = label_part.strip()

                if label:
                    self.labels[label] = pc

                rest = rest.strip()
                if rest:
                    cleaned_lines.append(rest)
                    pc += 1
            else:
                cleaned_lines.append(line)
                pc += 1

        for index, line in enumerate(cleaned_lines):
            self.instructions.append(self.parse_instruction(line, index))

    def tokenize(self, line: str) -> List[str]:
        # Convert lw r1,0(r2) into tokens: lw r1 0 r2
        normalized = line.replace(",", " ")
        normalized = normalized.replace("(", " ").replace(")", " ")
        return normalized.split()

    def parse_instruction(self, line: str, pc: int) -> Instruction:
        parts = self.tokenize(line)

        if not parts:
            raise ValueError("Empty instruction")

        op = parts[0].lower()

        if op in ["nop", "sll"]:
            # Treat common MIPS nop form SLL $r0,$r0,0 as a harmless ADDI r0,r0,0.
            return Instruction(op="addi", raw=line, pc=pc, rd="r0", rs="r0", imm=0)

        if op == "add":
            return Instruction(
                op="add",
                raw=line,
                pc=pc,
                rd=self.normalize_register(parts[1]),
                rs=self.normalize_register(parts[2]),
                rt=self.normalize_register(parts[3]),
            )

        if op == "addi":
            return Instruction(
                op="addi",
                raw=line,
                pc=pc,
                rd=self.normalize_register(parts[1]),
                rs=self.normalize_register(parts[2]),
                imm=self.parse_int(parts[3]),
            )

        if op == "lw":
            return Instruction(
                op="lw",
                raw=line,
                pc=pc,
                rd=self.normalize_register(parts[1]),
                imm=self.parse_int(parts[2]),
                rs=self.normalize_register(parts[3]),
            )

        if op == "sw":
            return Instruction(
                op="sw",
                raw=line,
                pc=pc,
                rs=self.normalize_register(parts[1]),
                imm=self.parse_int(parts[2]),
                rt=self.normalize_register(parts[3]),
            )

        if op == "beqz":
            return Instruction(
                op="beqz",
                raw=line,
                pc=pc,
                rs=self.normalize_register(parts[1]),
                label=parts[2],
            )

        if op == "halt":
            return Instruction(op="halt", raw=line, pc=pc)

        raise ValueError(f"Unsupported instruction: {line}")

    def make_stage(self, instr: Optional[Instruction]):
        if instr is None:
            return None

        return {
            "instr": instr,
            "alu_result": None,
            "mem_result": None,
            "store_address": None,
            "store_value": None,
            "taken": False,
            "target_pc": None,
        }

    def get_dest_register(self, stage) -> Optional[str]:
        if stage is None:
            return None

        instr = stage["instr"]

        if instr.op in ["add", "addi", "lw"]:
            return instr.rd

        return None

    def get_read_registers(self, instr: Optional[Instruction]) -> List[str]:
        if instr is None:
            return []

        if instr.op == "add":
            return [instr.rs, instr.rt]

        if instr.op == "addi":
            return [instr.rs]

        if instr.op == "lw":
            return [instr.rs]

        if instr.op == "sw":
            return [instr.rs, instr.rt]

        if instr.op == "beqz":
            return [instr.rs]

        return []

    def reads_stage_dest(self, instr: Optional[Instruction], stage) -> bool:
        if instr is None or stage is None:
            return False

        read_regs = [reg for reg in self.get_read_registers(instr) if reg != "r0"]
        dest = self.get_dest_register(stage)

        if dest is None or dest == "r0":
            return False

        return dest in read_regs

    def has_data_hazard(self) -> bool:
        if self.ID is None:
            return False

        id_instr = self.ID["instr"]

        if not self.forwarding:
            if self.reads_stage_dest(id_instr, self.EX):
                return True

            if self.reads_stage_dest(id_instr, self.MEM):
                return True

            return False

        if self.EX is not None:
            ex_instr = self.EX["instr"]

            if ex_instr.op == "lw" and self.reads_stage_dest(id_instr, self.EX):
                return True

        return False

    def get_register_value(self, reg: str) -> int:
        reg = self.normalize_register(reg)

        if reg == "r0":
            return 0

        if self.forwarding:
            forwarded = self.try_forward(reg)

            if forwarded is not None:
                return forwarded

        return self.registers.get(reg, 0)

    def try_forward(self, reg: str):
        if reg == "r0":
            return 0

        for stage in [self.MEM, self.WB]:
            if stage is None:
                continue

            instr = stage["instr"]
            dest = self.get_dest_register(stage)

            if dest != reg:
                continue

            if instr.op in ["add", "addi"] and stage["alu_result"] is not None:
                return stage["alu_result"]

            if instr.op == "lw" and stage["mem_result"] is not None:
                return stage["mem_result"]

        return None

    def fetch(self):
        if self.finished_fetch:
            return None

        if self.pc >= len(self.instructions):
            self.finished_fetch = True
            return None

        instr = self.instructions[self.pc]
        self.pc += 1

        return self.make_stage(instr)

    def execute_stage(self, stage):
        if stage is None:
            return

        instr = stage["instr"]

        if instr.op == "add":
            stage["alu_result"] = self.get_register_value(instr.rs) + self.get_register_value(instr.rt)

        elif instr.op == "addi":
            stage["alu_result"] = self.get_register_value(instr.rs) + instr.imm

        elif instr.op == "lw":
            base = self.get_register_value(instr.rs)
            stage["alu_result"] = base + instr.imm

        elif instr.op == "sw":
            base = self.get_register_value(instr.rt)
            value = self.get_register_value(instr.rs)
            stage["store_address"] = base + instr.imm
            stage["store_value"] = value

        elif instr.op == "beqz":
            value = self.get_register_value(instr.rs)

            if value == 0:
                if instr.label not in self.labels:
                    raise ValueError(f"Unknown branch label: {instr.label}")
                stage["taken"] = True
                stage["target_pc"] = self.labels[instr.label]

    def memory_stage(self, stage):
        if stage is None:
            return

        instr = stage["instr"]

        if instr.op == "lw":
            address = stage["alu_result"]
            stage["mem_result"] = self.memory.get(address, 0)

        elif instr.op == "sw":
            address = stage["store_address"]
            value = stage["store_value"]
            self.memory[address] = value

    def write_back_stage(self, stage):
        if stage is None:
            return

        instr = stage["instr"]

        if instr.op in ["add", "addi"]:
            if instr.rd != "r0":
                self.registers[instr.rd] = stage["alu_result"]
            self.instruction_count += 1

        elif instr.op == "lw":
            if instr.rd != "r0":
                self.registers[instr.rd] = stage["mem_result"]
            self.instruction_count += 1

        elif instr.op == "sw":
            self.instruction_count += 1

        elif instr.op == "beqz":
            self.instruction_count += 1

        elif instr.op == "halt":
            self.halted = True

        self.registers["r0"] = 0

    def step(self):
        if self.is_done():
            self.last_event = "Program already finished."
            return

        self.cycle += 1
        self.last_event = "Normal pipeline advance."

        old_IF = self.IF
        old_ID = self.ID
        old_EX = self.EX
        old_MEM = self.MEM
        old_WB = self.WB

        self.write_back_stage(old_WB)
        self.memory_stage(old_MEM)
        self.execute_stage(old_EX)

        branch_taken = False
        branch_target = None

        if old_EX is not None:
            instr = old_EX["instr"]

            if instr.op == "beqz" and old_EX["taken"]:
                branch_taken = True
                branch_target = old_EX["target_pc"]

        hazard = self.has_data_hazard()

        if branch_taken:
            self.flush_count += 1
            self.pc = branch_target
            self.finished_fetch = False

            self.WB = old_MEM
            self.MEM = old_EX
            self.EX = None
            self.ID = None
            self.IF = None

            self.last_event = "Branch taken. IF and ID are flushed."
            return

        if hazard:
            self.stall_count += 1

            self.WB = old_MEM
            self.MEM = old_EX
            self.EX = None
            self.ID = old_ID
            self.IF = old_IF

            self.last_event = "RAW hazard detected. Bubble inserted into EX."
            return

        self.WB = old_MEM
        self.MEM = old_EX
        self.EX = old_ID
        self.ID = old_IF
        self.IF = self.fetch()

    def is_pipeline_empty(self) -> bool:
        return self.IF is None and self.ID is None and self.EX is None and self.MEM is None and self.WB is None

    def is_done(self) -> bool:
        return self.halted and self.is_pipeline_empty()

    def stage_to_text(self, stage):
        if stage is None:
            return "—"
        return str(stage["instr"])

    def get_stage_type(self, stage):
        if stage is None:
            return "empty"
        return stage["instr"].op

    def get_cpi(self) -> float:
        if self.instruction_count == 0:
            return 0.0
        return self.cycle / self.instruction_count

    def read_program_source(self):
        return self.program_source

    def get_state(self):
        register_view = {f"r{i}": self.registers[f"r{i}"] for i in range(8)}
        memory_view = {str(key): self.memory[key] for key in sorted(self.memory.keys())}

        return {
            "program": self.program_name,
            "program_source": self.read_program_source(),
            "forwarding": self.forwarding,
            "cycle": self.cycle,
            "pc": self.pc,
            "finished": self.is_done(),
            "event": self.last_event,
            "pipeline": {
                "IF": {"text": self.stage_to_text(self.IF), "type": self.get_stage_type(self.IF)},
                "ID": {"text": self.stage_to_text(self.ID), "type": self.get_stage_type(self.ID)},
                "EX": {"text": self.stage_to_text(self.EX), "type": self.get_stage_type(self.EX)},
                "MEM": {"text": self.stage_to_text(self.MEM), "type": self.get_stage_type(self.MEM)},
                "WB": {"text": self.stage_to_text(self.WB), "type": self.get_stage_type(self.WB)},
            },
            "registers": register_view,
            "memory": memory_view,
            "stats": {
                "cycles": self.cycle,
                "instructions": self.instruction_count,
                "stalls": self.stall_count,
                "flushes": self.flush_count,
                "cpi": round(self.get_cpi(), 3),
            },
        }
