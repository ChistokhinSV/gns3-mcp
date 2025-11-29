/**
 * GNS3 Traffic Monitor - Web UI
 *
 * Vanilla JS + D3.js topology viewer for traffic widget management.
 * v0.4.0
 */

// Configuration
const CONFIG = {
    refreshInterval: 15000,  // 15 seconds
    apiBase: '/api',
};

// Application state
const state = {
    currentProject: null,
    topology: null,
    widgets: [],
    bridges: [],
    selectedLink: null,
    selectedNodes: null,  // {node1, node2} for the selected link
    autoRefreshTimer: null,
};

// ============================================================================
// API Functions
// ============================================================================

async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${CONFIG.apiBase}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
            },
            ...options,
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error(`API error: ${endpoint}`, error);
        throw error;
    }
}

async function getProjects() {
    const data = await apiCall('/projects');
    return data.projects || [];
}

async function getTopology(projectId) {
    return await apiCall(`/topology/${projectId}`);
}

async function getWidgets() {
    const data = await apiCall('/widgets');
    return data.widgets || [];
}

async function getBridges() {
    const data = await apiCall('/bridges');
    return data.bridges || [];
}

async function createWidget(linkId, projectId, x, y, inverse = false, chartType = 'bar') {
    return await apiCall('/widgets', {
        method: 'POST',
        body: JSON.stringify({
            action: 'create',
            link_id: linkId,
            project_id: projectId,
            x: x,
            y: y,
            inverse: inverse,
            chart_type: chartType,
        }),
    });
}

async function deleteWidget(widgetId) {
    return await apiCall('/widgets', {
        method: 'POST',
        body: JSON.stringify({
            action: 'delete',
            widget_id: widgetId,
        }),
    });
}

// ============================================================================
// UI Functions
// ============================================================================

function showModal(title, message, isError = false) {
    const modal = document.getElementById('modal');
    const modalTitle = document.getElementById('modal-title');
    const modalBody = document.getElementById('modal-body');

    modalTitle.textContent = title;
    modalBody.innerHTML = `<p style="color: ${isError ? 'var(--accent-danger)' : 'var(--text-primary)'}">${message}</p>`;
    modal.style.display = 'flex';
}

function hideModal() {
    document.getElementById('modal').style.display = 'none';
}

function updateStatus(connected) {
    const status = document.getElementById('connection-status');
    status.classList.toggle('connected', connected);
    status.textContent = connected ? 'Connected' : 'Disconnected';
}

function updateLastUpdate() {
    const now = new Date();
    document.getElementById('last-update').textContent =
        `Last update: ${now.toLocaleTimeString()}`;
}

function formatRate(bps) {
    if (bps >= 1e9) return `${(bps / 1e9).toFixed(1)}G`;
    if (bps >= 1e6) return `${(bps / 1e6).toFixed(1)}M`;
    if (bps >= 1e3) return `${(bps / 1e3).toFixed(1)}K`;
    return `${bps.toFixed(0)}`;
}

// ============================================================================
// Project Selection
// ============================================================================

async function loadProjects() {
    try {
        const projects = await getProjects();
        const select = document.getElementById('project-select');

        // Clear existing options (keep first "Select Project...")
        while (select.options.length > 1) {
            select.remove(1);
        }

        // Add project options
        projects.forEach(project => {
            const option = document.createElement('option');
            option.value = project.project_id;
            option.textContent = project.name;
            if (project.status === 'opened') {
                option.textContent += ' (opened)';
            }
            select.appendChild(option);
        });

        updateStatus(true);
    } catch (error) {
        updateStatus(false);
        showModal('Error', `Failed to load projects: ${error.message}`, true);
    }
}

async function selectProject(projectId) {
    if (!projectId) {
        state.currentProject = null;
        state.topology = null;
        clearTopology();
        document.getElementById('topology-status').textContent = 'No project selected';
        return;
    }

    state.currentProject = projectId;
    document.getElementById('topology-status').textContent = 'Loading...';

    try {
        await refreshAll();
        document.getElementById('topology-status').textContent = 'Loaded';
    } catch (error) {
        document.getElementById('topology-status').textContent = 'Error';
        showModal('Error', `Failed to load project: ${error.message}`, true);
    }
}

// ============================================================================
// Topology Rendering (D3.js)
// ============================================================================

function clearTopology() {
    const svg = d3.select('#topology-svg');
    svg.selectAll('*').remove();
    document.getElementById('node-count').textContent = '0 nodes';
    document.getElementById('link-count').textContent = '0 links';
}

function renderTopology(topology) {
    const container = document.getElementById('topology-container');
    const svg = d3.select('#topology-svg');

    // Clear previous
    svg.selectAll('*').remove();

    if (!topology || !topology.nodes || !topology.links) {
        return;
    }

    const width = container.clientWidth;
    const height = container.clientHeight;

    // Calculate bounds
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;

    topology.nodes.forEach(node => {
        minX = Math.min(minX, node.x);
        maxX = Math.max(maxX, node.x);
        minY = Math.min(minY, node.y);
        maxY = Math.max(maxY, node.y);
    });

    // Add padding
    const padding = 100;
    minX -= padding;
    minY -= padding;
    maxX += padding;
    maxY += padding;

    // Set viewBox for auto-scaling
    svg.attr('viewBox', `${minX} ${minY} ${maxX - minX} ${maxY - minY}`);

    // Define arrow markers
    const defs = svg.append('defs');

    // Forward arrow (at end of line)
    defs.append('marker')
        .attr('id', 'arrow')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 8)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', '#00aaff');

    // Reverse arrow (at start of line)
    defs.append('marker')
        .attr('id', 'arrow-reverse')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 2)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto-start-reverse')
        .append('path')
        .attr('d', 'M10,-5L0,0L10,5')
        .attr('fill', '#00aaff');

    // Create a group for zoom/pan
    const g = svg.append('g');

    // Build node lookup
    const nodeMap = {};
    topology.nodes.forEach(node => {
        nodeMap[node.node_id] = node;
    });

    // Build widget lookup by link_id
    const widgetByLink = {};
    topology.widgets.forEach(w => {
        widgetByLink[w.link_id] = w;
    });

    // Render links first (below nodes)
    const links = g.selectAll('.link')
        .data(topology.links)
        .enter()
        .append('g')
        .attr('class', 'link-group');

    links.each(function(link) {
        const group = d3.select(this);
        const nodes = link.nodes || [];

        if (nodes.length < 2) return;

        const node1 = nodeMap[nodes[0].node_id];
        const node2 = nodeMap[nodes[1].node_id];

        if (!node1 || !node2) return;

        // Node centers (assuming 58x58 icons)
        const cx1 = node1.x + 29;
        const cy1 = node1.y + 29;
        const cx2 = node2.x + 29;
        const cy2 = node2.y + 29;

        // Check if widget exists and has inverse
        const widget = widgetByLink[link.link_id];
        const inverse = widget?.inverse || false;

        // Calculate line endpoints at node edge (radius 28 to account for stroke)
        const nodeRadius = 28;
        const dx = cx2 - cx1;
        const dy = cy2 - cy1;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const nx = dx / dist;
        const ny = dy / dist;

        // Calculate endpoints based on inverse state
        let x1, y1, x2, y2;
        if (inverse) {
            // Swap direction: line goes from node2 to node1
            x1 = cx2 - nx * nodeRadius;
            y1 = cy2 - ny * nodeRadius;
            x2 = cx1 + nx * nodeRadius;
            y2 = cy1 + ny * nodeRadius;
        } else {
            // Normal: line goes from node1 to node2
            x1 = cx1 + nx * nodeRadius;
            y1 = cy1 + ny * nodeRadius;
            x2 = cx2 - nx * nodeRadius;
            y2 = cy2 - ny * nodeRadius;
        }

        // Draw link line with arrow at destination
        const line = group.append('line')
            .attr('class', 'link-line')
            .attr('x1', x1)
            .attr('y1', y1)
            .attr('x2', x2)
            .attr('y2', y2)
            .attr('data-link-id', link.link_id)
            .attr('data-cx1', cx1)
            .attr('data-cy1', cy1)
            .attr('data-cx2', cx2)
            .attr('data-cy2', cy2)
            .attr('marker-end', 'url(#arrow)');

        if (widget) {
            line.classed('has-widget', true);
        }

        // Click handler
        line.on('click', function(event) {
            event.stopPropagation();
            selectLink(link, node1, node2);
        });

        // Port indicators (small dots near line endpoints)
        const indicatorOffset = 12;

        // Indicator at node1 end
        group.append('circle')
            .attr('class', 'link-indicator')
            .classed('active', node1.status === 'started')
            .attr('cx', x1 + nx * indicatorOffset)
            .attr('cy', y1 + ny * indicatorOffset)
            .attr('r', 4);

        // Indicator at node2 end
        group.append('circle')
            .attr('class', 'link-indicator')
            .classed('active', node2.status === 'started')
            .attr('cx', x2 - nx * indicatorOffset)
            .attr('cy', y2 - ny * indicatorOffset)
            .attr('r', 4);
    });

    // Render nodes
    const nodeGroups = g.selectAll('.node')
        .data(topology.nodes)
        .enter()
        .append('g')
        .attr('class', 'node-group')
        .attr('transform', d => `translate(${d.x}, ${d.y})`);

    // Node circles
    nodeGroups.append('circle')
        .attr('class', 'node-circle')
        .classed('started', d => d.status === 'started')
        .classed('stopped', d => d.status === 'stopped')
        .attr('cx', 29)
        .attr('cy', 29)
        .attr('r', 25);

    // Node labels
    nodeGroups.append('text')
        .attr('class', 'node-label')
        .attr('x', 29)
        .attr('y', 70)
        .text(d => d.name);

    // Update counts
    document.getElementById('node-count').textContent = `${topology.nodes.length} nodes`;
    document.getElementById('link-count').textContent = `${topology.links.length} links`;

    // Add zoom behavior
    const zoom = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        });

    svg.call(zoom);

    // Click on background to deselect
    svg.on('click', () => {
        deselectLink();
    });
}

// ============================================================================
// Link Selection
// ============================================================================

function selectLink(link, node1, node2) {
    state.selectedLink = link;
    state.selectedNodes = { node1, node2 };

    // Update SVG
    d3.selectAll('.link-line').classed('selected', false);
    d3.select(`[data-link-id="${link.link_id}"]`).classed('selected', true);

    // Update panel
    const panel = document.getElementById('selected-link-panel');
    panel.style.display = 'block';

    // Check if widget exists for this link
    const widget = state.widgets.find(w => w.link_id === link.link_id);
    const hasWidget = !!widget;

    // Set inverse checkbox and chart type from widget state (or defaults)
    const inverse = widget?.inverse || false;
    const chartType = widget?.chart_type || 'bar';
    document.getElementById('inverse-checkbox').checked = inverse;
    document.getElementById('chart-type-select').value = chartType;

    document.getElementById('selected-link-id').textContent = link.link_id.substring(0, 8) + '...';
    // Show endpoints based on inverse state
    if (inverse) {
        document.getElementById('selected-endpoints').textContent = `${node2.name} → ${node1.name}`;
    } else {
        document.getElementById('selected-endpoints').textContent = `${node1.name} → ${node2.name}`;
    }
    document.getElementById('selected-status').textContent = link.suspend ? 'Suspended' : 'Active';

    // Update arrow direction on SVG based on widget inverse state
    updateLinkArrow(link.link_id, inverse);

    // Show appropriate button
    document.getElementById('create-widget-btn').style.display = hasWidget ? 'none' : 'block';
    document.getElementById('delete-widget-btn').style.display = hasWidget ? 'block' : 'none';

    // Store widget ID if exists
    if (hasWidget) {
        document.getElementById('delete-widget-btn').dataset.widgetId = widget.widget_id;
    } else {
        document.getElementById('delete-widget-btn').dataset.widgetId = '';
    }
}

function deselectLink() {
    state.selectedLink = null;
    state.selectedNodes = null;

    d3.selectAll('.link-line').classed('selected', false);
    document.getElementById('selected-link-panel').style.display = 'none';
}

function updateLinkArrow(linkId, inverse) {
    const line = d3.select(`[data-link-id="${linkId}"]`);
    if (line.empty()) return;

    // Get stored center coordinates
    const cx1 = parseFloat(line.attr('data-cx1'));
    const cy1 = parseFloat(line.attr('data-cy1'));
    const cx2 = parseFloat(line.attr('data-cx2'));
    const cy2 = parseFloat(line.attr('data-cy2'));

    const nodeRadius = 28;
    const dx = cx2 - cx1;
    const dy = cy2 - cy1;
    const dist = Math.sqrt(dx * dx + dy * dy);
    const nx = dx / dist;
    const ny = dy / dist;

    if (inverse) {
        // Swap direction: line goes from node2 to node1
        const x1 = cx2 - nx * nodeRadius;
        const y1 = cy2 - ny * nodeRadius;
        const x2 = cx1 + nx * nodeRadius;
        const y2 = cy1 + ny * nodeRadius;
        line.attr('x1', x1).attr('y1', y1).attr('x2', x2).attr('y2', y2);
    } else {
        // Normal: line goes from node1 to node2
        const x1 = cx1 + nx * nodeRadius;
        const y1 = cy1 + ny * nodeRadius;
        const x2 = cx2 - nx * nodeRadius;
        const y2 = cy2 - ny * nodeRadius;
        line.attr('x1', x1).attr('y1', y1).attr('x2', x2).attr('y2', y2);
    }
}

function handleInverseChange() {
    if (!state.selectedLink || !state.selectedNodes) return;

    const inverse = document.getElementById('inverse-checkbox').checked;
    const { node1, node2 } = state.selectedNodes;

    // Update endpoints text
    if (inverse) {
        document.getElementById('selected-endpoints').textContent = `${node2.name} → ${node1.name}`;
    } else {
        document.getElementById('selected-endpoints').textContent = `${node1.name} → ${node2.name}`;
    }

    // Update arrow on topology
    updateLinkArrow(state.selectedLink.link_id, inverse);
}

// ============================================================================
// Widget Management
// ============================================================================

async function handleCreateWidget() {
    if (!state.selectedLink || !state.currentProject) {
        showModal('Error', 'No link selected', true);
        return;
    }

    const inverse = document.getElementById('inverse-checkbox').checked;
    const chartType = document.getElementById('chart-type-select').value;

    try {
        const result = await createWidget(
            state.selectedLink.link_id,
            state.currentProject,
            null,
            null,
            inverse,
            chartType
        );

        if (result.success) {
            showModal('Success', result.message);
            await refreshAll();
        } else {
            showModal('Error', result.error || 'Failed to create widget', true);
        }
    } catch (error) {
        showModal('Error', error.message, true);
    }
}

async function handleDeleteWidget() {
    const widgetId = document.getElementById('delete-widget-btn').dataset.widgetId;

    if (!widgetId) {
        showModal('Error', 'No widget ID found', true);
        return;
    }

    try {
        const result = await deleteWidget(widgetId);

        if (result.success) {
            showModal('Success', result.message);
            await refreshAll();

            // Update selected panel if link is still selected
            if (state.selectedLink && state.selectedNodes) {
                selectLink(state.selectedLink, state.selectedNodes.node1, state.selectedNodes.node2);
            }
        } else {
            showModal('Error', result.error || 'Failed to delete widget', true);
        }
    } catch (error) {
        showModal('Error', error.message, true);
    }
}

function renderWidgetsList(widgets) {
    const container = document.getElementById('widgets-list');
    document.getElementById('widget-count').textContent = widgets.length;

    if (widgets.length === 0) {
        container.innerHTML = '<p class="empty-message">No widgets active</p>';
        return;
    }

    container.innerHTML = widgets.map(widget => `
        <div class="list-item" data-widget-id="${widget.widget_id}">
            <div class="list-item-title">Link: ${widget.link_id.substring(0, 8)}...</div>
            <div class="list-item-subtitle">Bridge: ${widget.bridge_name}</div>
            ${widget.last_delta ? `
                <div class="list-item-stats">
                    <span class="stat-rx">RX: ${formatRate(widget.last_delta.rx_bps)}/s</span>
                    <span class="stat-tx">TX: ${formatRate(widget.last_delta.tx_bps)}/s</span>
                </div>
            ` : ''}
        </div>
    `).join('');
}

function renderBridgesList(bridges) {
    const container = document.getElementById('bridges-list');
    document.getElementById('bridge-count').textContent = bridges.length;

    if (bridges.length === 0) {
        container.innerHTML = '<p class="empty-message">No bridges found</p>';
        return;
    }

    container.innerHTML = bridges.map(bridge => `
        <div class="list-item ${bridge.has_widget ? 'active' : ''}">
            <div class="list-item-title">${bridge.name}</div>
            <div class="list-item-stats">
                <span class="stat-rx">RX: ${formatRate(bridge.stats.rx_bytes)}</span>
                <span class="stat-tx">TX: ${formatRate(bridge.stats.tx_bytes)}</span>
            </div>
        </div>
    `).join('');
}

// ============================================================================
// Refresh Logic
// ============================================================================

async function refreshAll() {
    try {
        // Load topology if project selected
        if (state.currentProject) {
            state.topology = await getTopology(state.currentProject);
            renderTopology(state.topology);
            state.widgets = state.topology.widgets || [];
        } else {
            state.widgets = await getWidgets();
        }

        // Load bridges
        state.bridges = await getBridges();

        // Update lists
        renderWidgetsList(state.widgets);
        renderBridgesList(state.bridges);

        updateLastUpdate();
        updateStatus(true);
    } catch (error) {
        console.error('Refresh error:', error);
        updateStatus(false);
    }
}

function startAutoRefresh() {
    if (state.autoRefreshTimer) {
        clearInterval(state.autoRefreshTimer);
    }

    state.autoRefreshTimer = setInterval(() => {
        refreshAll();
    }, CONFIG.refreshInterval);
}

// ============================================================================
// Event Handlers
// ============================================================================

function setupEventHandlers() {
    // Project selection
    document.getElementById('project-select').addEventListener('change', (e) => {
        selectProject(e.target.value);
    });

    // Refresh button
    document.getElementById('refresh-btn').addEventListener('click', () => {
        refreshAll();
    });

    // Close selected panel
    document.getElementById('close-selected').addEventListener('click', () => {
        deselectLink();
    });

    // Create widget
    document.getElementById('create-widget-btn').addEventListener('click', () => {
        handleCreateWidget();
    });

    // Delete widget
    document.getElementById('delete-widget-btn').addEventListener('click', () => {
        handleDeleteWidget();
    });

    // Inverse checkbox
    document.getElementById('inverse-checkbox').addEventListener('change', () => {
        handleInverseChange();
    });

    // Modal close
    document.getElementById('modal-close').addEventListener('click', () => {
        hideModal();
    });

    document.getElementById('modal').addEventListener('click', (e) => {
        if (e.target.id === 'modal') {
            hideModal();
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            hideModal();
            deselectLink();
        }
        if (e.key === 'r' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            refreshAll();
        }
    });
}

// ============================================================================
// Initialization
// ============================================================================

async function loadVersion() {
    try {
        const response = await fetch('/version');
        const data = await response.json();
        document.getElementById('version').textContent = `v${data.version}`;
    } catch (error) {
        document.getElementById('version').textContent = 'v?';
    }
}

// ============================================================================
// Proxy Mode Detection & Redirect
// ============================================================================

function showRedirectPage(mainProxyUrl) {
    const overlay = document.getElementById('proxy-overlay');
    overlay.innerHTML = `
        <div class="overlay-content">
            <h2>Redirecting to Main Proxy</h2>
            <p>This is an internal proxy running inside GNS3.</p>
            <p>Traffic monitoring requires the main proxy.</p>
            <p class="redirect-url">Redirecting to: <a href="${mainProxyUrl}">${mainProxyUrl}</a></p>
            <div class="loader"></div>
        </div>
    `;
    overlay.style.display = 'flex';

    // Auto-redirect after 1.5 seconds
    setTimeout(() => {
        window.location.href = mainProxyUrl;
    }, 1500);
}

function showInstructionsPage(mainProxyUrl) {
    const overlay = document.getElementById('proxy-overlay');
    overlay.innerHTML = `
        <div class="overlay-content instructions">
            <h2>Internal Proxy - Limited Functionality</h2>
            <p>This proxy is running inside a GNS3 container and cannot monitor traffic.</p>
            <p>Traffic widgets require the <strong>main proxy</strong> with host access.</p>

            <h3>Option 1: Access Main Proxy Directly</h3>
            <p>If the main proxy is running, access it at:</p>
            <p class="code-block"><a href="${mainProxyUrl}">${mainProxyUrl}</a></p>

            <h3>Option 2: Deploy Main Proxy</h3>
            <p>Run this command on your GNS3 host:</p>
            <pre class="code-block">docker run -d --name gns3-ssh-proxy \\
  --network host --pid host \\
  -v /var/run/docker.sock:/var/run/docker.sock:ro \\
  -e CONTROLLER_PASSWORD=your_password \\
  chistokhinsv/gns3-ssh-proxy:latest</pre>

            <p class="note">The main proxy needs <code>--pid host</code> to access ubridge traffic stats.</p>
        </div>
    `;
    overlay.style.display = 'flex';
}

async function checkProxyMode() {
    try {
        const resp = await fetch('/api/proxy-mode');
        const data = await resp.json();

        if (data.mode === 'internal') {
            // Construct main proxy URL
            // Use browser's hostname (same host user used to access GNS3) because:
            // - Backend's CONTROLLER_HOST may be Docker internal IP (172.17.0.1)
            // - User's browser can only reach the external GNS3 host IP
            // GNS3's HTTP console proxy modifies port numbers in responses,
            // so backend sends port as array of digits to avoid modification
            const host = window.location.hostname;
            const port = data.main_proxy_port_digits ? data.main_proxy_port_digits.join('') : '8022';
            const mainProxyUrl = `http://${host}:${port}`;

            // Try to reach main proxy from browser
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 3000);

                const mainResp = await fetch(`${mainProxyUrl}/version`, {
                    signal: controller.signal
                });
                clearTimeout(timeoutId);

                if (mainResp.ok) {
                    // Main proxy available - redirect
                    showRedirectPage(mainProxyUrl);
                    return false;
                }
            } catch (e) {
                // Main proxy not reachable (timeout, network error, CORS)
                console.log('Main proxy not reachable:', e.message);
            }

            // Show instructions
            showInstructionsPage(mainProxyUrl);
            return false;
        }
        return true; // Main proxy - continue normal init
    } catch (e) {
        console.log('Proxy mode check failed, assuming main proxy:', e.message);
        return true; // Assume main proxy on error
    }
}

async function init() {
    console.log('GNS3 Traffic Monitor initializing...');

    // Check if we're an internal proxy - if so, redirect or show instructions
    const shouldContinue = await checkProxyMode();
    if (!shouldContinue) {
        return; // Stop init - overlay is shown
    }

    setupEventHandlers();
    await loadVersion();
    await loadProjects();
    await refreshAll();
    startAutoRefresh();

    console.log('GNS3 Traffic Monitor ready');
}

// Start when DOM is ready
document.addEventListener('DOMContentLoaded', init);
