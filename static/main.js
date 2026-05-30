let isRunning = false;
let currentProgramName = "imported.asm";

const navLinks = document.querySelectorAll(".nav a");
const pages = document.querySelectorAll(".page");

const asmFileInput = document.getElementById("asmFileInput");
const programEditor = document.getElementById("programEditor");
const forwardingSwitch = document.getElementById("forwardingSwitch");

const loadBtn = document.getElementById("loadBtn");
const stepBtn = document.getElementById("stepBtn");
const runBtn = document.getElementById("runBtn");
const resetBtn = document.getElementById("resetBtn");

const compareBtn = document.getElementById("compareBtn");
const reportForwardingSwitch = document.getElementById("reportForwardingSwitch");
const reportBtn = document.getElementById("reportBtn");

async function postJSON(url, data = {}) {
    const response = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(data)
    });

    const result = await response.json();

    if (!response.ok || result.ok === false) {
        throw new Error(result.error || `Request failed: ${url}`);
    }

    return result;
}

function getProgramPayload(extra = {}) {
    return {
        program_text: programEditor.value,
        program_name: currentProgramName,
        forwarding: forwardingSwitch.checked,
        ...extra
    };
}

function switchPage(pageId) {
    pages.forEach((page) => {
        page.classList.remove("active-page");
    });

    document.getElementById(pageId).classList.add("active-page");

    navLinks.forEach((link) => {
        link.classList.remove("active");

        if (link.dataset.page === pageId) {
            link.classList.add("active");
        }
    });
}

function updatePipelineStage(stageName, stageData) {
    const textElement = document.getElementById(`${stageName}-text`);
    const cardElement = document.getElementById(`stage-${stageName}`);

    textElement.textContent = stageData.text;

    cardElement.classList.remove(
        "op-add",
        "op-addi",
        "op-lw",
        "op-sw",
        "op-beqz",
        "op-halt"
    );

    if (stageData.type && stageData.type !== "empty") {
        cardElement.classList.add(`op-${stageData.type}`);
    }
}

function renderTable(containerId, data, prefix = "", suffix = "") {
    const container = document.getElementById(containerId);
    container.innerHTML = "";

    Object.keys(data).forEach((key) => {
        const row = document.createElement("div");
        row.className = "row";

        const name = document.createElement("span");
        name.textContent = `${prefix}${key}${suffix}`;

        const value = document.createElement("span");
        value.textContent = data[key];

        row.appendChild(name);
        row.appendChild(value);
        container.appendChild(row);
    });
}

function updateUI(state) {
    document.getElementById("programName").textContent = state.program;
    document.getElementById("cycleValue").textContent = state.cycle;
    document.getElementById("pcValue").textContent = state.pc;
    document.getElementById("forwardingValue").textContent = state.forwarding ? "ON" : "OFF";
    document.getElementById("eventValue").textContent = state.event;

    if (state.program_source !== undefined && document.activeElement !== programEditor) {
        programEditor.value = state.program_source;
    }

    updatePipelineStage("IF", state.pipeline.IF);
    updatePipelineStage("ID", state.pipeline.ID);
    updatePipelineStage("EX", state.pipeline.EX);
    updatePipelineStage("MEM", state.pipeline.MEM);
    updatePipelineStage("WB", state.pipeline.WB);

    renderTable("registerView", state.registers);
    renderTable("memoryView", state.memory, "mem[", "]");

    document.getElementById("statCycles").textContent = state.stats.cycles;
    document.getElementById("statInstructions").textContent = state.stats.instructions;
    document.getElementById("statStalls").textContent = state.stats.stalls;
    document.getElementById("statFlushes").textContent = state.stats.flushes;
    document.getElementById("statCpi").textContent = Number(state.stats.cpi).toFixed(3);

    if (state.finished) {
        isRunning = false;
        runBtn.textContent = "Run";
    }
}

function showError(error) {
    alert(error.message || String(error));
}

function handleFileImport() {
    const file = asmFileInput.files[0];

    if (!file) {
        return;
    }

    currentProgramName = file.name;

    const reader = new FileReader();

    reader.onload = function (event) {
        programEditor.value = event.target.result;
        document.getElementById("programName").textContent = currentProgramName;
        document.getElementById("eventValue").textContent = "File imported. Click Load to start.";
    };

    reader.onerror = function () {
        alert("Failed to read the selected file.");
    };

    reader.readAsText(file);
}

async function loadProgram() {
    try {
        const state = await postJSON("/api/load", getProgramPayload());
        updateUI(state);
    } catch (error) {
        showError(error);
    }
}

async function resetProgram() {
    try {
        const state = await postJSON("/api/reset", {});
        updateUI(state);
    } catch (error) {
        showError(error);
    }
}

async function stepProgram() {
    try {
        const state = await postJSON("/api/step", {});
        updateUI(state);
    } catch (error) {
        showError(error);
    }
}

async function runProgram() {
    if (isRunning) {
        isRunning = false;
        runBtn.textContent = "Run";
        return;
    }

    isRunning = true;
    runBtn.textContent = "Pause";

    while (isRunning) {
        try {
            const state = await postJSON("/api/step", {});
            updateUI(state);

            if (state.finished) {
                isRunning = false;
                runBtn.textContent = "Run";
                break;
            }

            await new Promise((resolve) => setTimeout(resolve, 450));
        } catch (error) {
            isRunning = false;
            runBtn.textContent = "Run";
            showError(error);
            break;
        }
    }
}

async function updateForwarding() {
    try {
        const state = await postJSON("/api/forwarding", {
            forwarding: forwardingSwitch.checked
        });

        updateUI(state);
    } catch (error) {
        showError(error);
    }
}

function statsToTable(stats) {
    return {
        Cycles: stats.cycles,
        Instructions: stats.instructions,
        Stalls: stats.stalls,
        Flushes: stats.flushes,
        CPI: Number(stats.cpi).toFixed(3)
    };
}

function renderCharts(offStats, onStats) {
    const chartView = document.getElementById("chartView");
    chartView.innerHTML = "";

    const metrics = [
        { key: "cycles", label: "Cycles" },
        { key: "stalls", label: "Stalls" },
        { key: "cpi", label: "CPI" }
    ];

    metrics.forEach((metric) => {
        const offValue = Number(offStats[metric.key]);
        const onValue = Number(onStats[metric.key]);
        const maxValue = Math.max(offValue, onValue, 1);

        const row = document.createElement("div");
        row.className = "chart-row";

        row.innerHTML = `
            <div class="chart-label">
                <span>${metric.label}</span>
                <span>OFF ${offValue} / ON ${onValue}</span>
            </div>

            <div class="bar-track">
                <div class="bar-fill" style="width: ${(offValue / maxValue) * 100}%"></div>
            </div>

            <div class="bar-track">
                <div class="bar-fill on" style="width: ${(onValue / maxValue) * 100}%"></div>
            </div>
        `;

        chartView.appendChild(row);
    });
}

async function runComparison() {
    try {
        compareBtn.textContent = "Running...";

        const result = await postJSON("/api/compare", getProgramPayload());

        renderTable("offStats", statsToTable(result.off.stats));
        renderTable("onStats", statsToTable(result.on.stats));
        renderCharts(result.off.stats, result.on.stats);

        document.getElementById("analysisText").textContent = result.analysis;
    } catch (error) {
        showError(error);
    } finally {
        compareBtn.textContent = "Run Comparison";
    }
}

async function generateReportNotes() {
    try {
        reportBtn.textContent = "Generating...";

        const result = await postJSON("/api/report", getProgramPayload({
            forwarding: reportForwardingSwitch.checked
        }));

        document.getElementById("reportOutput").textContent = result.report;

        const checklist = document.getElementById("screenshotChecklist");
        checklist.innerHTML = "";

        result.checklist.forEach((item) => {
            const li = document.createElement("li");
            li.textContent = item;
            checklist.appendChild(li);
        });
    } catch (error) {
        showError(error);
    } finally {
        reportBtn.textContent = "Generate Report Notes";
    }
}

navLinks.forEach((link) => {
    link.addEventListener("click", (event) => {
        event.preventDefault();
        switchPage(link.dataset.page);
    });
});

asmFileInput.addEventListener("change", handleFileImport);
loadBtn.addEventListener("click", loadProgram);
resetBtn.addEventListener("click", resetProgram);
stepBtn.addEventListener("click", stepProgram);
runBtn.addEventListener("click", runProgram);
forwardingSwitch.addEventListener("change", updateForwarding);
compareBtn.addEventListener("click", runComparison);
reportBtn.addEventListener("click", generateReportNotes);

window.addEventListener("load", () => {
    document.getElementById("programName").textContent = currentProgramName;
});
