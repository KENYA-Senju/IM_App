const element = document.getElementById("search");
const quantity = document.getElementById("amount");
const project = document.getElementById("project");
const button = document.getElementById("placeAddRequest");
const radioButtons = document.getElementsByName("op");
const suggestions = document.getElementById("materials-list");
const table = document.getElementById("table"); 
const projectSuggestions = document.getElementById("project-track");
const allocationLegend = document.getElementById("allocation-legend");
const HEADINGS = ["ID", "Material", "Stock", "Recent", "Projects", "Total"]
const hf = ["id", "material", "quantity", "time", "project", "stock"]
const PROJECT_COLORS = ["#69b7ff", "#20c878", "#ffc857", "#ef8354", "#b79ced", "#f08cae", "#72d6c9", "#d7e36f"];
const projectColorMap = new Map();
const projectDisplayMap = new Map();

let name_to_id = {};

const API = window.API_BASE || "http://localhost:8000";
async function applyRequest(DICT, endpoint = "/IM-server") {
    console.log("Sending Data to Server:", DICT);
    const response = await fetch(`${API}${endpoint}`, {
        method: 'POST',
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(DICT)
    });
    const data = await response.json();
    console.log("Server Responded with Response: ", data)
    return data;
}

function addHeaders(){ 
    const a = document.createElement("tr")
    // add headings to program 
    HEADINGS.forEach((element) => { 
        const b = document.createElement("th") 
        b.textContent  = element
        a.appendChild(b)
    });
    table.appendChild(a) 
}

function projectKey(projectName) {
    return String(projectName).trim().toLowerCase().replace(/[\s_]+/g, "-").replace(/-+/g, "-");
}

function colorForProject(projectName) {
    const key = projectKey(projectName);
    if (!projectColorMap.has(key)) {
        projectColorMap.set(key, PROJECT_COLORS[projectColorMap.size % PROJECT_COLORS.length]);
        projectDisplayMap.set(key, String(projectName).trim());
    }
    return projectColorMap.get(key);
}

function createAllocationBar(allocations) {
    const barWrap = document.createElement("div");
    barWrap.className = "allocation-bar-wrap";
    const bar = document.createElement("div");
    bar.className = "allocation-bar";
    const entries = Object.entries(allocations || {})
        .map(([name, amount]) => [name, Number(amount)])
        .filter(([, amount]) => Number.isFinite(amount) && amount > 0);
    const total = entries.reduce((sum, [, amount]) => sum + amount, 0);

    if (total === 0) {
        bar.title = "No project allocations";
        barWrap.appendChild(bar);
        return barWrap;
    }

    entries.forEach(([name, amount]) => {
        const slice = document.createElement("span");
        slice.className = "allocation-slice";
        slice.style.width = `${(amount / total) * 100}%`;
        slice.style.backgroundColor = colorForProject(name);
        slice.dataset.description = `${name}: ${amount} (${Math.round((amount / total) * 100)}%)`;
        slice.title = slice.dataset.description;
        bar.appendChild(slice);
    });
    const totalLabel = document.createElement("span");
    totalLabel.className = "allocation-total";
    totalLabel.textContent = `${total} allocated`;
    barWrap.append(bar, totalLabel);
    return barWrap;
}

function renderAllocationLegend() {
    if (!allocationLegend) return;
    allocationLegend.innerHTML = "";
    const table = document.createElement("table");
    table.className = "legend-table";
    const heading = document.createElement("caption");
    heading.textContent = "Allocation color legend";
    table.appendChild(heading);
    [...projectColorMap.entries()].forEach(([project, color]) => {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        const swatch = document.createElement("span");
        swatch.className = "legend-swatch";
        swatch.style.backgroundColor = color;
        cell.append(swatch, document.createTextNode(projectDisplayMap.get(project)));
        row.appendChild(cell);
        table.appendChild(row);
    });
    allocationLegend.appendChild(table);
}

const allocationTooltip = document.createElement("div");
allocationTooltip.className = "allocation-tooltip";
allocationTooltip.hidden = true;
document.body.appendChild(allocationTooltip);

document.addEventListener("mouseover", event => {
    const slice = event.target.closest(".allocation-slice");
    if (!slice) return;
    allocationTooltip.textContent = slice.dataset.description;
    allocationTooltip.hidden = false;
});

document.addEventListener("mousemove", event => {
    if (!allocationTooltip.hidden) {
        allocationTooltip.style.left = `${event.clientX + 12}px`;
        allocationTooltip.style.top = `${event.clientY + 12}px`;
    }
});

document.addEventListener("mouseout", event => {
    if (event.target.closest(".allocation-slice")) allocationTooltip.hidden = true;
});

function updateTable(e){ 
    const c = document.createElement("tr") 
    hf.forEach(f => {
        const cell = document.createElement("td");
        if (f === "project") {
            cell.appendChild(createAllocationBar(e[f]));
        } else {
            cell.textContent = e[f] ?? "";
        }
        c.appendChild(cell);
    });
    table.appendChild(c)
}

function updateSuggestions(data) {
    suggestions.innerHTML = "";
    table.innerHTML= "";
    projectSuggestions.innerHTML = "";
    //Add back the headers
    addHeaders();
    name_to_id = {};

    const projectNames = new Set();

    for (let i = 0; i < data.length; i++) {
        const item = data[i];
        const option = document.createElement("option");
        option.value = `${item.id} - ${item.material}`;
        suggestions.appendChild(option);
        name_to_id[item.material.toLowerCase()] = item.id;


        if (item.project && typeof item.project === "object") {
            Object.keys(item.project).forEach((projectName) => {
                projectNames.add(projectName);
            });
        }


        updateTable(data[i])
    }


    projectNames.forEach((projectName) => {
        const projectOption = document.createElement("option");
        projectOption.value = projectName;
        projectSuggestions.appendChild(projectOption);
    });
    renderAllocationLegend();
}
function normalizeProjectValue(value) {
    const text = String(value ?? "").trim();
    return text === "" ? "Any" : text;
}

async function loadInitialSuggestions() {
    const refreshInfo = { code: "refresh" };
    const response = await applyRequest(refreshInfo, "/IM-server");
    if (response && Array.isArray(response.data)) {
        updateSuggestions(response.data);
    }
}

button.addEventListener("click", async function () {
    await ensureConnected();
    let operation = "";
    for (let i = 0; i < radioButtons.length; i++) {
        if (radioButtons[i].checked) {
            operation = radioButtons[i].value;
        }
    }

    const rawValue = element.value.trim();
    let item = rawValue;
    let id = null;
    const match = rawValue.match(/^(\d+)\s*-\s*(.+)$/);
    if (match) {
        id = Number(match[1]);
        item = match[2].trim();
    } else if (rawValue.toLowerCase() in name_to_id) {
        id = name_to_id[rawValue.toLowerCase()];
    }
    const normalizeProject = normalizeProjectValue(project.value)
    const addInfo = {
        code: "a",
        item: item,
        amount: quantity.value,
        operation: operation, 
        project: normalizeProject
    };
    if (id !== null) {
        addInfo.id = id;
    }

    const response = await applyRequest(addInfo, "/IM-server");
    console.log(`Server Responded to ${operation}:`);
    console.log(response);

    if (response && Array.isArray(response.data)) {
        updateSuggestions(response.data);
    } else {
        await loadInitialSuggestions();
    }
});

window.addEventListener("DOMContentLoaded", async () => {
    await ensureConnected();
    loadInitialSuggestions();
});

