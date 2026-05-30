from flask import Flask, jsonify, render_template, request
from simulator import PipelineSimulator

app = Flask(__name__)

simulator = None
current_program_text = """# Import an .asm file from the web page, or paste code here.
# Supported instructions: add, addi, lw, sw, beqz, halt.
halt
"""
current_program_name = "imported.asm"
current_forwarding = False


def make_error(message: str, status_code: int = 400):
    return jsonify({"ok": False, "error": message}), status_code


def create_simulator(program_text: str, program_name: str, forwarding: bool) -> PipelineSimulator:
    return PipelineSimulator(
        program_text=program_text,
        program_name=program_name,
        forwarding=forwarding,
    )


def run_to_completion(program_text: str, program_name: str, forwarding: bool, max_steps: int = 300):
    sim = create_simulator(program_text, program_name, forwarding)

    steps = 0
    while not sim.is_done() and steps < max_steps:
        sim.step()
        steps += 1

    return sim.get_state()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/load", methods=["POST"])
def load_program():
    global simulator, current_program_text, current_program_name, current_forwarding

    data = request.get_json(silent=True) or {}
    program_text = data.get("program_text", "")
    program_name = data.get("program_name", "imported.asm")
    forwarding = bool(data.get("forwarding", False))

    if not program_text.strip():
        return make_error("Program is empty. Please import or paste an ASM file first.")

    try:
        current_program_text = program_text
        current_program_name = program_name
        current_forwarding = forwarding
        simulator = create_simulator(current_program_text, current_program_name, current_forwarding)
        return jsonify(simulator.get_state())
    except Exception as exc:
        return make_error(str(exc))


@app.route("/api/reset", methods=["POST"])
def reset_program():
    global simulator

    try:
        simulator = create_simulator(current_program_text, current_program_name, current_forwarding)
        return jsonify(simulator.get_state())
    except Exception as exc:
        return make_error(str(exc))


@app.route("/api/step", methods=["POST"])
def step_program():
    global simulator

    try:
        if simulator is None:
            simulator = create_simulator(current_program_text, current_program_name, current_forwarding)

        simulator.step()
        return jsonify(simulator.get_state())
    except Exception as exc:
        return make_error(str(exc))


@app.route("/api/run", methods=["POST"])
def run_program():
    global simulator

    try:
        if simulator is None:
            simulator = create_simulator(current_program_text, current_program_name, current_forwarding)

        max_steps = 300
        steps = 0

        while not simulator.is_done() and steps < max_steps:
            simulator.step()
            steps += 1

        return jsonify(simulator.get_state())
    except Exception as exc:
        return make_error(str(exc))


@app.route("/api/forwarding", methods=["POST"])
def set_forwarding():
    global simulator, current_forwarding

    data = request.get_json(silent=True) or {}
    current_forwarding = bool(data.get("forwarding", False))

    try:
        simulator = create_simulator(current_program_text, current_program_name, current_forwarding)
        return jsonify(simulator.get_state())
    except Exception as exc:
        return make_error(str(exc))


@app.route("/api/compare", methods=["POST"])
def compare_program():
    data = request.get_json(silent=True) or {}
    program_text = data.get("program_text", current_program_text)
    program_name = data.get("program_name", current_program_name)

    if not program_text.strip():
        return make_error("Program is empty. Please import or paste an ASM file first.")

    try:
        off_state = run_to_completion(program_text, program_name, forwarding=False)
        on_state = run_to_completion(program_text, program_name, forwarding=True)
        analysis_text = build_analysis_text(program_name, off_state, on_state)

        return jsonify({
            "program": program_name,
            "off": off_state,
            "on": on_state,
            "analysis": analysis_text,
        })
    except Exception as exc:
        return make_error(str(exc))


@app.route("/api/report", methods=["POST"])
def generate_report_notes():
    data = request.get_json(silent=True) or {}
    program_text = data.get("program_text", current_program_text)
    program_name = data.get("program_name", current_program_name)
    forwarding = bool(data.get("forwarding", current_forwarding))

    if not program_text.strip():
        return make_error("Program is empty. Please import or paste an ASM file first.")

    try:
        state = run_to_completion(program_text, program_name, forwarding=forwarding)
        report_text = build_report_text(program_name, forwarding, state)

        return jsonify({
            "program": program_name,
            "forwarding": forwarding,
            "state": state,
            "report": report_text,
            "checklist": build_screenshot_checklist(program_name),
        })
    except Exception as exc:
        return make_error(str(exc))


def build_analysis_text(program_name: str, off_state: dict, on_state: dict) -> str:
    off_stats = off_state["stats"]
    on_stats = on_state["stats"]

    stall_delta = off_stats["stalls"] - on_stats["stalls"]
    cycle_delta = off_stats["cycles"] - on_stats["cycles"]
    cpi_delta = round(off_stats["cpi"] - on_stats["cpi"], 3)

    lower_name = program_name.lower()

    if "raw" in lower_name or "hazard" in lower_name:
        intro = (
            "This imported program is treated as a RAW-hazard test case. "
            "The key observation is whether a later instruction reads a register before an earlier instruction has written it back."
        )
    elif "branch" in lower_name:
        intro = (
            "This imported program is treated as a branch-control test case. "
            "The key observation is whether beqz changes the PC and causes wrong-path instructions to be flushed."
        )
    else:
        intro = (
            "This imported program is treated as a general pipeline test case. "
            "The statistics reflect the combined cost of filling the pipeline, stalls and flushes."
        )

    if stall_delta > 0:
        result = (
            f"With forwarding enabled, the simulator reduces {stall_delta} stall cycle(s), "
            f"{cycle_delta} total cycle(s), and {cpi_delta:.3f} CPI compared with forwarding disabled."
        )
    elif stall_delta == 0:
        result = (
            "Forwarding does not change the stall count in this run. "
            "This usually means the imported program has no data dependency that benefits from bypassing, "
            "or its main cost comes from control hazards."
        )
    else:
        result = (
            "The measured stall count does not decrease after enabling forwarding. "
            "Please check whether the imported program is dominated by branches or unsupported instruction patterns."
        )

    return intro + " " + result


def build_report_text(program_name: str, forwarding: bool, state: dict) -> str:
    stats = state["stats"]
    mode = "ON" if forwarding else "OFF"

    report = f"""Program: {program_name}
Forwarding: {mode}
Cycles: {stats["cycles"]}
Instructions: {stats["instructions"]}
Stalls: {stats["stalls"]}
Flushes: {stats["flushes"]}
CPI: {stats["cpi"]}

Analysis:
This program is loaded from an external ASM file rather than from a built-in program string. After loading, the simulator parses labels and instructions, then displays the five-stage pipeline state cycle by cycle. The statistics panel records cycles, completed instructions, stalls, flushes and CPI.

Result Interpretation:
The execution result shows that the simulator supports file-based program input, pipeline visualization, forwarding control and performance statistics. The measured CPI reflects pipeline filling cost as well as possible RAW hazards, branch flushes and bubble insertion.
"""

    return report


def build_screenshot_checklist(program_name: str):
    return [
        "Screenshot 1: Imported ASM file shown in the Source panel.",
        "Screenshot 2: Main simulator interface after clicking Load.",
        "Screenshot 3: A middle cycle where IF, ID, EX, MEM and WB are active.",
        "Screenshot 4: Final statistics panel after the program finishes.",
        "Screenshot 5: Forwarding OFF / ON comparison result if this program contains RAW hazards.",
    ]


if __name__ == "__main__":
    app.run(debug=True)
