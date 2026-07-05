// ---- Study Notes Generator: browser logic ----

const form = document.getElementById("topic-form");
const topicInput = document.getElementById("topic");
const formError = document.getElementById("form-error");

const progressPanel = document.getElementById("progress-panel");
const progressMessage = document.getElementById("progress-message");
const progressPercent = document.getElementById("progress-percent");
const progressFill = document.getElementById("progress-fill");
const stageList = document.getElementById("stage-list");

const notesCard = document.getElementById("notes-card");
const notesTopic = document.getElementById("notes-topic");
const notesContent = document.getElementById("notes-content");
const downloadDocx = document.getElementById("download-docx");
const downloadPdf = document.getElementById("download-pdf");

let pollTimer = null;
let currentJobId = null;

const levelSwitch = document.getElementById("level-switch");
const levelButtons = levelSwitch.querySelectorAll(".level-btn");
const levelStatus = document.getElementById("level-status");

// ---- Generate notes ----
form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const topic = topicInput.value.trim();
    formError.hidden = true;

    if (topic.length < 3) {
        showFormError("Enter a topic with at least 3 characters.");
        return;
    }

    setFormBusy(true);
    notesCard.hidden = true;
    progressPanel.hidden = false;
    updateProgress({ message: "Queued. Your study crew is getting ready.", progress: 5, stages: [] });

    try {
        const res = await fetch("/api/reports", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ topic }),
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.error || "Could not start.");
        }
        pollJob(data.id);
    } catch (err) {
        showFormError(err.message);
        setFormBusy(false);
        progressPanel.hidden = true;
    }
});

function pollJob(jobId) {
    clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
        try {
            const res = await fetch(`/api/reports/${jobId}`);
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "Lost the job.");

            updateProgress(data);

            if (data.status === "complete") {
                clearInterval(pollTimer);
                setFormBusy(false);
                showNotes(data);
                loadHistory();
            } else if (data.status === "failed") {
                clearInterval(pollTimer);
                setFormBusy(false);
                showFormError(data.error || "The notes could not be generated.");
            }
        } catch (err) {
            clearInterval(pollTimer);
            setFormBusy(false);
            showFormError(err.message);
        }
    }, 2500);
}

function updateProgress(data) {
    const pct = data.progress || 0;
    progressMessage.textContent = data.message || "Working…";
    progressPercent.textContent = `${pct}%`;
    progressFill.style.width = `${pct}%`;

    stageList.innerHTML = "";
    (data.stages || []).forEach((stage) => {
        const li = document.createElement("li");
        li.textContent = stage.label;
        if (stage.status && stage.status !== "pending") {
            li.classList.add(stage.status);
        }
        stageList.appendChild(li);
    });
}

function showNotes(data) {
    currentJobId = data.id;
    notesTopic.textContent = data.topic || "";
    notesContent.innerHTML = data.html || "<p>No notes were produced.</p>";
    if (data.download_url) {
        downloadDocx.href = data.download_url;
        downloadDocx.hidden = false;
    } else {
        downloadDocx.hidden = true;
    }
    markActiveLevel(data.level || "medium");
    loadStickies();
    notesCard.hidden = false;
    notesCard.scrollIntoView({ behavior: "smooth", block: "start" });
}

function markActiveLevel(level) {
    levelButtons.forEach((btn) => {
        btn.classList.toggle("is-active", btn.dataset.level === level);
    });
}

// Switch difficulty level. Already-made levels load instantly; a new one is rewritten by the AI.
levelButtons.forEach((btn) => {
    btn.addEventListener("click", async () => {
        const level = btn.dataset.level;
        if (!currentJobId || btn.classList.contains("is-active")) return;

        levelButtons.forEach((b) => (b.disabled = true));
        levelStatus.hidden = false;
        try {
            const res = await fetch(`/api/reports/${currentJobId}/level`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ level }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "Could not switch level.");
            showNotes(data);
        } catch (err) {
            showFormError(err.message);
        } finally {
            levelButtons.forEach((b) => (b.disabled = false));
            levelStatus.hidden = true;
        }
    });
});

downloadPdf.addEventListener("click", () => window.print());

function showFormError(message) {
    formError.textContent = message;
    formError.hidden = false;
}
function setFormBusy(busy) {
    topicInput.disabled = busy;
    form.querySelector("button[type=submit]").disabled = busy;
}

// ---- History of past notes ----
const historyList = document.getElementById("history-list");

async function loadHistory() {
    try {
        const res = await fetch("/api/reports");
        if (!res.ok) return;
        renderHistory(await res.json());
    } catch (_) {
        // MongoDB not reachable yet — history just stays empty.
    }
}

function renderHistory(jobs) {
    historyList.innerHTML = "";
    if (!jobs.length) {
        const li = document.createElement("li");
        li.className = "history-empty";
        li.textContent = "No notes yet.";
        historyList.appendChild(li);
        return;
    }

    jobs.forEach((job) => {
        const li = document.createElement("li");
        const item = document.createElement("div");
        item.className = "history-item";
        item.innerHTML =
            `<span class="h-topic">${escapeHtml(job.topic)}</span>` +
            `<span class="h-right">` +
            `<span class="h-status ${job.status}">${job.status}</span>` +
            `<button class="history-delete" type="button" title="Delete">🗑</button>` +
            `</span>`;
        item.addEventListener("click", () => openHistory(job.id));

        const del = item.querySelector(".history-delete");
        del.addEventListener("click", (event) => {
            event.stopPropagation();
            deleteReport(job.id, job.topic);
        });

        li.appendChild(item);
        historyList.appendChild(li);
    });
}

async function deleteReport(jobId, topic) {
    if (!confirm(`Delete the notes for "${topic}"? This can't be undone.`)) return;

    const res = await fetch(`/api/reports/${jobId}`, { method: "DELETE" });
    if (res.ok) {
        if (currentJobId === jobId) {
            notesCard.hidden = true;
            currentJobId = null;
            loadStickies(); // re-gates the notepad now that no note is open
        }
        loadHistory();
    }
}

async function openHistory(jobId) {
    const res = await fetch(`/api/reports/${jobId}`);
    if (!res.ok) return;
    const data = await res.json();
    if (data.status === "complete") {
        showNotes(data);
    } else {
        progressPanel.hidden = false;
        updateProgress(data);
    }
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
}

// ---- Font toggle (handwriting <-> easy read) ----
const fontToggle = document.getElementById("font-toggle");
fontToggle.addEventListener("click", () => {
    const clean = document.body.classList.toggle("clean-font");
    fontToggle.textContent = clean ? "Aa · Handwriting" : "Aa · Easy read";
});

// ---- Sticky notepad (stored in MongoDB) ----
const stickyForm = document.getElementById("sticky-form");
const stickyInput = document.getElementById("sticky-input");
const stickyList = document.getElementById("sticky-list");
const colorPicker = document.getElementById("color-picker");
let selectedColor = "yellow";

colorPicker.addEventListener("click", (event) => {
    const swatch = event.target.closest(".swatch");
    if (!swatch) return;
    colorPicker.querySelectorAll(".swatch").forEach((s) => s.classList.remove("is-active"));
    swatch.classList.add("is-active");
    selectedColor = swatch.dataset.color;
});

stickyForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = stickyInput.value.trim();
    if (!text || !currentJobId) return;

    const res = await fetch("/api/stickies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, color: selectedColor, note_id: currentJobId }),
    });
    if (res.ok) {
        stickyInput.value = "";
        loadStickies();
    }
});

// The notepad is tied to the open note. No note open -> disabled with a hint.
function setNotepadEnabled(enabled) {
    stickyInput.disabled = !enabled;
    stickyForm.querySelector("button[type=submit]").disabled = !enabled;
    stickyInput.placeholder = enabled ? "Jot something down…" : "Open a note first…";
    if (!enabled) {
        stickyList.innerHTML =
            '<p class="sticky-empty">Open or make a note to jot notes for it.</p>';
    }
}

async function loadStickies() {
    if (!currentJobId) {
        setNotepadEnabled(false);
        return;
    }
    setNotepadEnabled(true);
    try {
        const res = await fetch(`/api/stickies?note_id=${currentJobId}`);
        if (!res.ok) return;
        renderStickies(await res.json());
    } catch (_) {
        // MongoDB not reachable yet — notepad just stays empty.
    }
}

function renderStickies(stickies) {
    stickyList.innerHTML = "";
    if (!stickies.length) {
        const empty = document.createElement("p");
        empty.className = "sticky-empty";
        empty.textContent = "No notes for this topic yet. Add your first one above.";
        stickyList.appendChild(empty);
        return;
    }

    stickies.forEach((sticky) => {
        const card = document.createElement("div");
        card.className = `sticky ${sticky.color}`;

        const text = document.createElement("div");
        text.className = "sticky-text";
        text.contentEditable = "true";
        text.textContent = sticky.text;
        text.addEventListener("blur", () => saveStickyEdit(sticky, text.textContent.trim()));

        const meta = document.createElement("div");
        meta.className = "sticky-meta";
        meta.innerHTML = `<span>${formatDate(sticky.updated_at)}</span>`;

        const del = document.createElement("button");
        del.className = "sticky-delete";
        del.type = "button";
        del.title = "Delete";
        del.textContent = "🗑";
        del.addEventListener("click", () => deleteSticky(sticky.id));
        meta.appendChild(del);

        card.appendChild(text);
        card.appendChild(meta);
        stickyList.appendChild(card);
    });
}

async function saveStickyEdit(sticky, newText) {
    if (!newText || newText === sticky.text) return;
    await fetch(`/api/stickies/${sticky.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: newText }),
    });
    sticky.text = newText;
}

async function deleteSticky(id) {
    const res = await fetch(`/api/stickies/${id}`, { method: "DELETE" });
    if (res.ok) loadStickies();
}

function formatDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return "";
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

loadStickies();
loadHistory();
