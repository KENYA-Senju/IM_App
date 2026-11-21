const API = window.API_BASE || "http://localhost:8000";
const projectList = document.getElementById("project-list");
const message = document.getElementById("message");
let materials = [];

async function request(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
        headers: { "Content-Type": "application/json" },
        ...options
    });
    const payload = response.status === 204 ? null : await response.json();
    if (!response.ok) {
        throw new Error(payload?.detail || "Request failed");
    }
    return payload;
}

function showError(error) {
    message.textContent = error.message;
}

async function loadMaterials() {
    materials = await request("/api/inventory/materials");
}

async function loadProjects() {
    const projects = await request("/api/projects");
    projectList.innerHTML = "";
    for (const project of projects) {
        const details = document.createElement("details");
        details.innerHTML = `
            <summary>${project.name} <small>(${project.status})</small></summary>
            <div class="project-content"><p>Loading components...</p></div>`;
        details.addEventListener("toggle", async () => {
            if (details.open && !details.dataset.loaded) {
                try {
                    await renderProject(details, project.id);
                    details.dataset.loaded = "true";
                } catch (error) { showError(error); }
            }
        });
        projectList.appendChild(details);
    }
}

function materialOptions(project_name) {
    return materials.map(material =>
        `<option value="${material.id}">${material.material} (#${material.id}, stock ${material.project[project_name]?? "None"})</option>`
    ).join("");
}// This is it!!!

async function renderProject(details, projectId) {
    const project = await request(`/api/projects/${projectId}`);
    const content = details.querySelector(".project-content");
    content.innerHTML = `
        <form data-project-edit="${project.id}">
            <label>Project name <input name="name" value="${project.name}" required maxlength="120"></label>
            <label>Status <select name="status"><option ${project.status === "active" ? "selected" : ""}>active</option><option ${project.status === "paused" ? "selected" : ""}>paused</option><option ${project.status === "archived" ? "selected" : ""}>archived</option></select></label>
            <button type="submit">Save project</button>
        </form>
        <div class="component-list"></div>
        <form class="add-component" data-component-form="${project.id}">
            <label>Component name <input name="name" required maxlength="120"></label>
            <button type="submit">Add component</button>
        </form>`;
    const componentList = content.querySelector(".component-list");
    project.components.forEach(component => {
        const wrapper = document.createElement("article");
        wrapper.className = "component";
        wrapper.innerHTML = `
            <details>
                <summary>${component.name} <small>(${component.status})</small></summary>
                <div class="component-content">
                    <div class="component-heading">
                        <h3>Component controls</h3>
                        <button type="button" data-complete="${component.id}">
                            ${component.status === "finished" ? "Reopen" : "Confirm complete"}
                        </button>
                    </div>
                    <form data-component-edit="${component.id}">
                        <input name="name" value="${component.name}" required maxlength="120">
                        <select name="status"><option ${component.status === "unfinished" ? "selected" : ""}>unfinished</option><option ${component.status === "finished" ? "selected" : ""}>finished</option></select>
                        <button type="submit">Save component</button>
                    </form>
                    <div class="parts">${component.parts.map(part => `
                <div class="part">
                    <strong>${part.material}</strong>
                    <span>Required: ${part.required_quantity}</span>
                    <span>Available: ${part.available_quantity}</span>
                    <span>Confirmed: ${part.completed_quantity}</span>
                    <span class="${part.available ? "ok" : "missing"}">${part.completed ? "Completed" : part.available ? "Ready" : "Missing"}</span>
                    <form data-part-edit="${part.id}">
                        <input name="required_quantity" type="number" min="1" value="${part.required_quantity}" required>
                        <button type="submit">Save</button>
                    </form>
                    <button type="button" data-delete-part="${part.id}">Remove</button>
                </div>`).join("")}</div>
                    <form class="add-part" data-part-form="${component.id}">
                        <label>Inventory material <select name="material_id" required>${materialOptions(project.name)}</select></label>
                        <label>Required quantity <input name="required_quantity" type="number" min="1" required></label>
                        <button type="submit">Add part</button>
                    </form>
                </div>
            </details>`;
        componentList.appendChild(wrapper);
    });

    content.querySelectorAll("[data-complete]").forEach(button => {
        button.addEventListener("click", async () => {
            try {
                const action = button.textContent.trim() === "Reopen" ? "reopen" : "complete";
                await request(`/api/components/${button.dataset.complete}/${action}`, { method: "POST" });
                details.dataset.loaded = "";
                await renderProject(details, projectId);
                details.dataset.loaded = "true";
            } catch (error) { showError(error); }
        });
    });
    content.querySelectorAll("[data-project-edit]").forEach(form => {
        form.addEventListener("submit", async event => {
            event.preventDefault();
            try {
                const data = new FormData(form);
                await request(`/api/projects/${form.dataset.projectEdit}`, { method: "PATCH", body: JSON.stringify({ name: data.get("name"), status: data.get("status") }) });
                await loadProjects();
            } catch (error) { showError(error); }
        });
    });
    content.querySelectorAll("[data-component-form]").forEach(form => {
        form.addEventListener("submit", async event => {
            event.preventDefault();
            try {
                const data = new FormData(form);
                await request(`/api/projects/${form.dataset.componentForm}/components`, { method: "POST", body: JSON.stringify({ name: data.get("name") }) });
                details.dataset.loaded = "";
                await renderProject(details, projectId);
                details.dataset.loaded = "true";
            } catch (error) { showError(error); }
        });
    });
    content.querySelectorAll("[data-component-edit]").forEach(form => {
        form.addEventListener("submit", async event => {
            event.preventDefault();
            try {
                const data = new FormData(form);
                await request(`/api/components/${form.dataset.componentEdit}`, {
                    method: "PATCH",
                    body: JSON.stringify({ name: data.get("name"), status: data.get("status") })
                });
                await renderProject(details, projectId);
            } catch (error) { showError(error); }
        });
    });
    content.querySelectorAll("[data-part-form]").forEach(form => {
        form.addEventListener("submit", async event => {
            event.preventDefault();
            try {
                const data = new FormData(form);
                await request(`/api/components/${form.dataset.partForm}/parts`, {
                    method: "POST",
                    body: JSON.stringify({
                        material_id: Number(data.get("material_id")),
                        required_quantity: Number(data.get("required_quantity"))
                    })
                });
                await renderProject(details, projectId);
            } catch (error) { showError(error); }
        });
    });
    content.querySelectorAll("[data-delete-part]").forEach(button => {
        button.addEventListener("click", async () => {
            try {
                await request(`/api/component-parts/${button.dataset.deletePart}`, { method: "DELETE" });
                await renderProject(details, projectId);
            } catch (error) { showError(error); }
        });
    });
    content.querySelectorAll("[data-part-edit]").forEach(form => {
        form.addEventListener("submit", async event => {
            event.preventDefault();
            try {
                const data = new FormData(form);
                await request(`/api/component-parts/${form.dataset.partEdit}`, {
                    method: "PATCH",
                    body: JSON.stringify({ required_quantity: Number(data.get("required_quantity")) })
                });
                await renderProject(details, projectId);
            } catch (error) { showError(error); }
        });
    });
}

document.getElementById("project-form").addEventListener("submit", async event => {
    event.preventDefault();
    try {
        const name = document.getElementById("project-name").value;
        const project = await request("/api/projects", {
            method: "POST", body: JSON.stringify({ name })
        });
        document.getElementById("project-name").value = "";
        await loadProjects();
        const createdProject = [...document.querySelectorAll("#project-list details")].find(
            details => details.querySelector("summary")?.textContent.startsWith(project.name)
        );
        if (createdProject) {
            createdProject.open = true;
            createdProject.dispatchEvent(new Event("toggle"));
        }
    } catch (error) { showError(error); }
});

(async () => {
    try {
        await ensureConnected("message");
        await loadMaterials();
        await loadProjects();
    } catch (error) { showError(error); }
})();
