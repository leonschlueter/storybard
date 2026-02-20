const campaignId = "8c822428-22aa-4a5a-897c-a544e847a505";

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    console.error("Failed:", url);
    return null;
  }
  return res.json();
}

async function loadGameState() {
  const [scene, contextBlocks, threads, events] = await Promise.all([
    fetchJSON(`/api/v1/scene/${campaignId}`),
    fetchJSON(`/api/v1/campaigns/${campaignId}/context-blocks?active_only=false`),
    fetchJSON(`/api/v1/campaigns/${campaignId}/threads`),
    fetchJSON(`/api/v1/campaigns/${campaignId}/events?limit=60`)
  ]);

  renderScene(scene);
  renderContext(contextBlocks);
  renderThreads(threads);
  renderEvents(events);
}

function renderScene(scene) {
  const el = document.getElementById("scene");

  if (!scene) {
    el.innerHTML = "<p>No scene loaded</p>";
    return;
  }

  el.innerHTML = `
    <h2>${scene.title}</h2>
    <p>${scene.summary}</p>
    <div><strong>NPCs:</strong> ${(scene.npc_ids || []).join(", ")}</div>
    <div><strong>Locations:</strong> ${(scene.location_ids || []).join(", ")}</div>
  `;
}

function renderContext(blocks) {
  const el = document.getElementById("context");

  if (!blocks || !blocks.length) {
    el.innerHTML = "<p>No context blocks</p>";
    return;
  }

  el.innerHTML = "<h3>Context Blocks</h3>";

  blocks.forEach(block => {
    const card = document.createElement("div");
    card.style.border = "1px solid #444";
    card.style.padding = "8px";
    card.style.marginBottom = "6px";
    card.style.cursor = "pointer";

    card.innerHTML = `
      <strong>${block.title}</strong><br/>
      <small>Type: ${block.type}</small>
    `;

    card.onclick = () => {
      alert(block.summary || "No summary");
    };

    el.appendChild(card);
  });
}

function renderThreads(threads) {
  const el = document.getElementById("threads");

  if (!threads || !threads.length) {
    el.innerHTML = "<p>No threads</p>";
    return;
  }

  el.innerHTML = "<h3>Threads</h3>";

  threads.forEach(thread => {
    const div = document.createElement("div");
    div.innerText = thread.title || thread.id;
    el.appendChild(div);
  });
}

function renderEvents(events) {
  const el = document.getElementById("events");

  if (!events || !events.length) {
    el.innerHTML = "<p>No events</p>";
    return;
  }

  el.innerHTML = "<h3>Recent Events (Debug)</h3>";

  events.forEach(event => {
    const pre = document.createElement("pre");
    pre.style.fontSize = "11px";
    pre.textContent = JSON.stringify(event, null, 2);
    el.appendChild(pre);
  });
}