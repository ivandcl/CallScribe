const API = "/api";
let currentRecordingId = null;
let isRecording = false;
let pollInterval = null;
let detailPollInterval = null;

// -- Init --

document.addEventListener("DOMContentLoaded", () => {
    loadRecordings();
    startStatusPolling();
});

// -- Status polling --

function startStatusPolling() {
    pollInterval = setInterval(pollStatus, 3000);
    pollStatus();
}

async function pollStatus() {
    try {
        const res = await fetch(`${API}/status`);
        const data = await res.json();
        isRecording = data.is_recording;
        updateRecordingUI(data);
    } catch (e) {
        // Server might be down
    }
}

function updateRecordingUI(status) {
    const badge = document.getElementById("status-badge");
    const btn = document.getElementById("btn-record");

    if (status.is_recording) {
        badge.textContent = "Grabando";
        badge.className = "badge badge-recording";
        btn.textContent = "Detener grabacion";
        btn.className = "btn btn-danger";
    } else {
        badge.textContent = "Inactivo";
        badge.className = "badge badge-inactive";
        btn.textContent = "Iniciar grabacion";
        btn.className = "btn btn-primary";
    }
}

// -- Recording control --

async function toggleRecording() {
    const btn = document.getElementById("btn-record");
    btn.disabled = true;

    try {
        if (isRecording) {
            const res = await fetch(`${API}/recording/stop`, { method: "POST" });
            if (!res.ok) {
                const err = await res.json();
                alert("Error al detener: " + (err.detail || "Error desconocido"));
                return;
            }
            await loadRecordings();
        } else {
            const res = await fetch(`${API}/recording/start`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({}),
            });
            if (!res.ok) {
                const err = await res.json();
                alert("Error al iniciar: " + (err.detail || "Error desconocido"));
                return;
            }
            await loadRecordings();
        }
        await pollStatus();
    } finally {
        btn.disabled = false;
    }
}

// -- Import file --

function importFile() {
    document.getElementById("file-input").click();
}

async function handleFileSelected(event) {
    const file = event.target.files[0];
    if (!file) return;

    const btn = document.getElementById("btn-import");
    btn.disabled = true;
    btn.textContent = "Importando...";

    try {
        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch(`${API}/recordings/import`, {
            method: "POST",
            body: formData,
        });

        if (!res.ok) {
            const err = await res.json();
            alert("Error al importar: " + (err.detail || "Error desconocido"));
            return;
        }

        await loadRecordings();
    } catch (e) {
        alert("Error al importar archivo: " + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = "Importar archivo";
        event.target.value = "";
    }
}

// -- Recordings list --

async function loadRecordings() {
    try {
        const res = await fetch(`${API}/recordings`);
        const data = await res.json();
        renderRecordings(data);
    } catch (e) {
        console.error("Error cargando grabaciones:", e);
    }
}

function renderRecordings(recordings) {
    const container = document.getElementById("recordings-container");
    const noMsg = document.getElementById("no-recordings");

    if (recordings.length === 0) {
        container.innerHTML = "";
        noMsg.style.display = "block";
        return;
    }

    noMsg.style.display = "none";
    container.innerHTML = recordings.map(r => {
        const date = r.started_at ? new Date(r.started_at).toLocaleString("es-ES") : "";
        const duration = r.duration_secs ? formatDuration(r.duration_secs) : "--:--";
        return `
            <div class="recording-card" onclick="showDetail('${r.id}')">
                <div class="recording-card-info">
                    <div class="recording-card-title">${escapeHtml(r.title)}</div>
                    <div class="recording-card-meta">${date} | ${duration}</div>
                </div>
                <span class="badge badge-${r.status}">${r.status}</span>
            </div>
        `;
    }).join("");
}

// -- Detail view --

async function showDetail(id) {
    currentRecordingId = id;
    document.getElementById("recordings-list").style.display = "none";
    document.getElementById("recording-detail").style.display = "block";

    await refreshDetail();
    startDetailPolling();
}

function showList() {
    currentRecordingId = null;
    stopDetailPolling();
    document.getElementById("recording-detail").style.display = "none";
    document.getElementById("recordings-list").style.display = "block";
    loadRecordings();
}

function startDetailPolling() {
    stopDetailPolling();
    detailPollInterval = setInterval(async () => {
        if (currentRecordingId) {
            await refreshDetail();
        }
    }, 3000);
}

function stopDetailPolling() {
    if (detailPollInterval) {
        clearInterval(detailPollInterval);
        detailPollInterval = null;
    }
}

async function refreshDetail() {
    if (!currentRecordingId) return;

    try {
        const res = await fetch(`${API}/recordings/${currentRecordingId}`);
        if (!res.ok) return;
        const data = await res.json();
        renderDetail(data);
    } catch (e) {
        console.error("Error cargando detalle:", e);
    }
}

function renderDetail(rec) {
    document.getElementById("detail-title").value = rec.title;
    const statusBadge = document.getElementById("detail-status");
    statusBadge.textContent = rec.status;
    statusBadge.className = `badge badge-${rec.status}`;

    const date = rec.started_at ? new Date(rec.started_at).toLocaleString("es-ES") : "";
    document.getElementById("detail-date").textContent = date;
    document.getElementById("detail-duration").textContent =
        rec.duration_secs ? formatDuration(rec.duration_secs) : "--:--";

    // Error
    const errorBox = document.getElementById("detail-error");
    if (rec.error_message) {
        errorBox.textContent = rec.error_message;
        errorBox.style.display = "block";
    } else {
        errorBox.style.display = "none";
    }

    // Buttons
    const inProgress = ["recording", "transcribing", "summarizing"].includes(rec.status);
    document.getElementById("btn-transcribe").disabled =
        inProgress || !rec.audio_url || rec.transcript_text !== null;
    document.getElementById("btn-summarize").disabled =
        inProgress || rec.transcript_text === null || rec.summary_markdown !== null;
    document.getElementById("btn-process").disabled =
        inProgress || !rec.audio_url;
    document.getElementById("btn-delete").disabled = rec.status === "recording";

    // Audio
    const audioSection = document.getElementById("audio-section");
    if (rec.audio_url) {
        audioSection.style.display = "block";
        const player = document.getElementById("audio-player");
        if (!player.src.includes(rec.id)) {
            player.src = rec.audio_url;
        }
    } else {
        audioSection.style.display = "none";
    }

    // Transcript
    const transcriptSection = document.getElementById("transcript-section");
    if (rec.transcript_text) {
        transcriptSection.style.display = "block";
        document.getElementById("transcript-text").textContent = rec.transcript_text;
    } else {
        transcriptSection.style.display = "none";
    }

    // Summary
    const summarySection = document.getElementById("summary-section");
    if (rec.summary_markdown) {
        summarySection.style.display = "block";
        if (typeof marked !== "undefined") {
            document.getElementById("summary-content").innerHTML =
                marked.parse(rec.summary_markdown);
        } else {
            document.getElementById("summary-content").textContent = rec.summary_markdown;
        }
    } else {
        summarySection.style.display = "none";
    }

    // Stop detail polling if final state
    if (!inProgress && detailPollInterval) {
        stopDetailPolling();
    }
}

// -- Actions --

async function updateTitle() {
    if (!currentRecordingId) return;
    const title = document.getElementById("detail-title").value.trim();
    if (!title) return;

    await fetch(`${API}/recordings/${currentRecordingId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
    });
}

async function transcribeRecording() {
    if (!currentRecordingId) return;
    const res = await fetch(`${API}/recordings/${currentRecordingId}/transcribe`, {
        method: "POST",
    });
    if (!res.ok) {
        const err = await res.json();
        alert("Error: " + (err.detail || "Error desconocido"));
        return;
    }
    startDetailPolling();
    await refreshDetail();
}

async function summarizeRecording() {
    if (!currentRecordingId) return;
    const res = await fetch(`${API}/recordings/${currentRecordingId}/summarize`, {
        method: "POST",
    });
    if (!res.ok) {
        const err = await res.json();
        alert("Error: " + (err.detail || "Error desconocido"));
        return;
    }
    startDetailPolling();
    await refreshDetail();
}

async function processRecording() {
    if (!currentRecordingId) return;
    const res = await fetch(`${API}/recordings/${currentRecordingId}/process`, {
        method: "POST",
    });
    if (!res.ok) {
        const err = await res.json();
        alert("Error: " + (err.detail || "Error desconocido"));
        return;
    }
    startDetailPolling();
    await refreshDetail();
}

async function deleteRecording() {
    if (!currentRecordingId) return;
    if (!confirm("Eliminar esta grabacion y todos sus archivos?")) return;

    const res = await fetch(`${API}/recordings/${currentRecordingId}`, {
        method: "DELETE",
    });
    if (res.ok) {
        showList();
    } else {
        const err = await res.json();
        alert("Error: " + (err.detail || "Error desconocido"));
    }
}

// -- Helpers --

function formatDuration(secs) {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = secs % 60;
    if (h > 0) {
        return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    }
    return `${m}:${String(s).padStart(2, "0")}`;
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}
