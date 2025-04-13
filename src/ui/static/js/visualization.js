// DOM Elements
const visualizationContainer = document.getElementById('visualization');
const visualizationLoading = document.getElementById('visualization-loading');
const visualizationInfo = document.getElementById('visualization-info');
const nodeDetails = document.getElementById('node-details');
const selectedNodeName = document.getElementById('selected-node-name');
const visualizationType = document.getElementById('visualization-type');
const showExternalDeps = document.getElementById('show-external-deps');
const groupByModule = document.getElementById('group-by-module');
const searchModule = document.getElementById('search-module');
const searchBtn = document.getElementById('search-btn');
const themeToggleBtn = document.getElementById('theme-toggle');
const htmlElement = document.documentElement;

// State variables
let dependencyData = null;
let currentVisualization = null;
let zoomBehavior = null;
let expandedModules = new Set(); // Track which modules are expanded

// Load theme from localStorage
document.addEventListener('DOMContentLoaded', () => {
    loadTheme();
    loadVisualizationData();
});

// Event listeners
visualizationType.addEventListener('change', updateVisualization);
showExternalDeps.addEventListener('change', updateVisualization);
groupByModule.addEventListener('change', updateVisualization);
searchBtn.addEventListener('click', searchNodes);
searchModule.addEventListener('keypress', e => {
    if (e.key === 'Enter') searchNodes();
});
themeToggleBtn.addEventListener('click', toggleTheme);

// Collapse all button
const collapseAllBtn = document.getElementById('collapse-all-btn');
if (collapseAllBtn) {
    collapseAllBtn.addEventListener('click', () => {
        expandedModules.clear();
        updateVisualization();
    });
}

// Theme functions
function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    htmlElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const currentTheme = htmlElement.getAttribute('data-theme') || 'light';
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    
    htmlElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    updateThemeIcon(newTheme);
    
    // If we have a visualization, update it for the new theme
    if (currentVisualization) {
        updateVisualization();
    }
}

function updateThemeIcon(theme) {
    const icon = themeToggleBtn.querySelector('i');
    if (theme === 'dark') {
        icon.className = 'fas fa-sun';
    } else {
        icon.className = 'fas fa-moon';
    }
}

// Fetch visualization data
async function loadVisualizationData() {
    try {
        visualizationLoading.style.display = 'flex';
        const response = await fetch('/api/dependency-data');
        const data = await response.json();
        
        if (data.status === 'success') {
            dependencyData = data.data;
            initializeVisualization();
        } else {
            showError(`Error loading data: ${data.message}`);
        }
    } catch (error) {
        console.error('Error loading visualization data:', error);
        showError(`Error loading data: ${error.message}`);
    } finally {
        visualizationLoading.style.display = 'none';
    }
}

function showError(message) {
    visualizationContainer.innerHTML = `
        <div class="error-message">
            <i class="fas fa-exclamation-triangle"></i>
            <p>${message}</p>
            <button onclick="location.reload()">Retry</button>
        </div>
    `;
}

// Initialize visualization based on selected type
function initializeVisualization() {
    updateVisualization();
}

function updateVisualization() {
    // Clear previous visualization
    visualizationContainer.innerHTML = '';
    
    // Create new visualization based on selected type
    const type = visualizationType.value;
    const showExternal = showExternalDeps.checked;
    const groupModules = groupByModule.checked;
    
    switch (type) {
        case 'dependency-graph':
            createDependencyGraph(showExternal, groupModules);
            break;
        case 'module-tree':
            createModuleTree(showExternal, groupModules);
            break;
        case 'file-size':
            createFileSizeTreemap();
            break;
        default:
            createDependencyGraph(showExternal, groupModules);
    }
}

// Create a force-directed graph visualization of dependencies
function createDependencyGraph(showExternal = true, groupModules = true) {
    if (!dependencyData || !dependencyData.dependencies) {
        showError('No dependency data available');
        return;
    }
    
    // Prepare data for visualization
    const nodes = [];
    const links = [];
    const nodeMap = {};
    
    // Process dependencies and create nodes and links
    Object.entries(dependencyData.dependencies).forEach(([source, targets]) => {
        if (!nodeMap[source]) {
            const isExternal = source.includes('external/') || !source.endsWith('.py');
            if (isExternal && !showExternal) return;
            
            nodeMap[source] = {
                id: source,
                name: getFileName(source),
                module: getModuleName(source),
                isExternal: isExternal,
                size: dependencyData.file_sizes?.[source] || 1000
            };
            nodes.push(nodeMap[source]);
        }
        
        targets.forEach(target => {
            if (!nodeMap[target]) {
                const isExternal = target.includes('external/') || !target.endsWith('.py');
                if (isExternal && !showExternal) return;
                
                nodeMap[target] = {
                    id: target,
                    name: getFileName(target),
                    module: getModuleName(target),
                    isExternal: isExternal,
                    size: dependencyData.file_sizes?.[target] || 1000
                };
                nodes.push(nodeMap[target]);
            }
            
            links.push({
                source: source,
                target: target,
                value: 1
            });
        });
    });
    
    // Group nodes by module if requested
    let groupedNodes = nodes;
    let groupedLinks = links;
    
    if (groupModules) {
        const moduleNodes = {};
        const moduleLinks = new Map();
        const moduleFiles = {};
        
        // Create module nodes
        nodes.forEach(node => {
            const moduleName = node.module;
            if (!moduleNodes[moduleName]) {
                moduleNodes[moduleName] = {
                    id: `module:${moduleName}`,
                    name: moduleName,
                    module: moduleName,
                    isModule: true,
                    isExternal: node.isExternal,
                    size: 0,
                    children: []
                };
                moduleFiles[moduleName] = [];
            }
            
            moduleNodes[moduleName].children.push(node);
            moduleFiles[moduleName].push(node);
            moduleNodes[moduleName].size += node.size;
        });
        
        // Add module nodes to visualization
        const moduleNodesList = Object.values(moduleNodes);
        groupedNodes = [...moduleNodesList];
        
        // Add individual file nodes for expanded modules
        for (const moduleName of expandedModules) {
            if (moduleFiles[moduleName]) {
                groupedNodes = groupedNodes.concat(moduleFiles[moduleName]);
            }
        }
        
        // Create module-to-module links
        links.forEach(link => {
            const sourceModule = nodeMap[link.source]?.module;
            const targetModule = nodeMap[link.target]?.module;
            
            if (sourceModule && targetModule && sourceModule !== targetModule) {
                const linkKey = `${sourceModule}|${targetModule}`;
                if (!moduleLinks.has(linkKey)) {
                    moduleLinks.set(linkKey, {
                        source: `module:${sourceModule}`,
                        target: `module:${targetModule}`,
                        value: 0
                    });
                }
                
                moduleLinks.get(linkKey).value += 1;
            }
        });
        
        // Add all module-to-module links
        groupedLinks = Array.from(moduleLinks.values());
        
        // Add file-to-file links for expanded modules
        links.forEach(link => {
            const sourceModule = nodeMap[link.source]?.module;
            const targetModule = nodeMap[link.target]?.module;
            
            if (expandedModules.has(sourceModule) && expandedModules.has(targetModule)) {
                // Both source and target modules are expanded, add the file-to-file link
                groupedLinks.push(link);
            } else if (expandedModules.has(sourceModule)) {
                // Source module is expanded, add file-to-module link
                groupedLinks.push({
                    source: link.source,
                    target: `module:${targetModule}`,
                    value: 1
                });
            } else if (expandedModules.has(targetModule)) {
                // Target module is expanded, add module-to-file link
                groupedLinks.push({
                    source: `module:${sourceModule}`,
                    target: link.target,
                    value: 1
                });
            }
        });
    }
    
    // Create SVG and force simulation
    const width = visualizationContainer.clientWidth;
    const height = visualizationContainer.clientHeight;
    
    const svg = d3.select(visualizationContainer)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', [0, 0, width, height]);
    
    // Add zoom functionality
    const g = svg.append('g');
    
    zoomBehavior = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        });
    
    svg.call(zoomBehavior);
    
    // Add zoom controls
    const zoomControls = svg.append('g')
        .attr('class', 'zoom-controls')
        .attr('transform', 'translate(10, 10)');
    
    // Create zoom in button (with both rect and text as one clickable group)
    const zoomInBtn = zoomControls.append('g')
        .attr('class', 'zoom-btn-group')
        .attr('cursor', 'pointer')
        .attr('title', 'Zoom In')
        .on('click', () => {
            svg.transition().duration(500).call(
                zoomBehavior.transform,
                d3.zoomIdentity.translate(width/2, height/2).scale(1.5)
            );
        });
    
    zoomInBtn.append('rect')
        .attr('class', 'zoom-btn')
        .attr('width', 30)
        .attr('height', 30)
        .attr('rx', 4)
        .attr('ry', 4);
    
    zoomInBtn.append('text')
        .attr('x', 15)
        .attr('y', 20)
        .attr('text-anchor', 'middle')
        .attr('pointer-events', 'none')
        .text('+');
    
    // Create zoom out button
    const zoomOutBtn = zoomControls.append('g')
        .attr('class', 'zoom-btn-group')
        .attr('cursor', 'pointer')
        .attr('transform', 'translate(35, 0)')
        .attr('title', 'Zoom Out')
        .on('click', () => {
            svg.transition().duration(500).call(
                zoomBehavior.transform,
                d3.zoomIdentity.translate(width/2, height/2).scale(0.75)
            );
        });
    
    zoomOutBtn.append('rect')
        .attr('class', 'zoom-btn')
        .attr('width', 30)
        .attr('height', 30)
        .attr('rx', 4)
        .attr('ry', 4);
    
    zoomOutBtn.append('text')
        .attr('x', 15)
        .attr('y', 20)
        .attr('text-anchor', 'middle')
        .attr('pointer-events', 'none')
        .text('-');
    
    // Create reset zoom button
    const resetZoomBtn = zoomControls.append('g')
        .attr('class', 'zoom-btn-group')
        .attr('cursor', 'pointer')
        .attr('transform', 'translate(70, 0)')
        .attr('title', 'Reset Zoom')
        .on('click', () => {
            svg.transition().duration(500).call(
                zoomBehavior.transform,
                d3.zoomIdentity.translate(width/2, height/2).scale(1)
            );
        });
    
    resetZoomBtn.append('rect')
        .attr('class', 'zoom-btn')
        .attr('width', 30)
        .attr('height', 30)
        .attr('rx', 4)
        .attr('ry', 4);
    
    resetZoomBtn.append('text')
        .attr('x', 15)
        .attr('y', 19)
        .attr('text-anchor', 'middle')
        .attr('pointer-events', 'none')
        .text('⟲');
    
    // Create a force simulation
    const simulation = d3.forceSimulation(groupedNodes)
        .force('link', d3.forceLink(groupedLinks).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(d => Math.sqrt(d.size) / 10 + 20));
    
    // Create links
    const link = g.append('g')
        .selectAll('line')
        .data(groupedLinks)
        .join('line')
        .attr('class', 'link')
        .attr('stroke-width', d => Math.sqrt(d.value));
    
    // Create nodes
    const node = g.append('g')
        .selectAll('.node')
        .data(groupedNodes)
        .join('g')
        .attr('class', d => {
            let classes = `node ${d.isExternal ? 'external' : ''}`;
            if (d.isModule) {
                classes += ' module';
                if (expandedModules.has(d.name)) {
                    classes += ' expanded';
                }
            } else {
                classes += ' file';
            }
            return classes;
        })
        .call(drag(simulation));
    
    // Add circles to nodes
    node.append('circle')
        .attr('r', d => d.isModule ? Math.sqrt(d.size) / 10 + 10 : 5)
        .attr('class', d => d.isModule ? 'expandable' : '')
        .attr('fill', d => {
            if (d.isModule && expandedModules.has(d.name)) {
                return '#22c55e'; // Expanded module color
            }
            return d.isExternal ? '#64748b' : '#2563eb'; // Standard colors
        });
    
    // Add labels to nodes
    node.append('text')
        .attr('dx', 12)
        .attr('dy', '.35em')
        .text(d => d.name);
    
    // Add text shadow/outline for better visibility
    // This approach handles both light and dark modes better
    node.append('text')
        .attr('dx', 12)
        .attr('dy', '.35em')
        .attr('class', 'shadow')
        .text(d => d.name)
        .lower();
    
    // Add title for tooltip
    node.append('title')
        .text(d => d.id);
    
    // Handle node click to show details and toggle expansion for modules
    node.on('click', (event, d) => {
        // Show node details
        showNodeDetails(d);
        
        // Toggle expansion for modules
        if (d.isModule) {
            if (expandedModules.has(d.name)) {
                expandedModules.delete(d.name);
            } else {
                expandedModules.add(d.name);
            }
            updateVisualization();
        }
    });
    
    // Update positions on tick
    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        
        node
            .attr('transform', d => `translate(${d.x}, ${d.y})`);
    });
    
    // Set the current visualization
    currentVisualization = {
        type: 'dependency-graph',
        svg: svg,
        simulation: simulation
    };
    
    // Center the view
    svg.call(zoomBehavior.transform, d3.zoomIdentity);
    
    // Helper function for dragging nodes
    function drag(simulation) {
        function dragstarted(event) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            event.subject.fx = event.subject.x;
            event.subject.fy = event.subject.y;
        }
        
        function dragged(event) {
            event.subject.fx = event.x;
            event.subject.fy = event.y;
        }
        
        function dragended(event) {
            if (!event.active) simulation.alphaTarget(0);
            event.subject.fx = null;
            event.subject.fy = null;
        }
        
        return d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended);
    }
}

// Create a tree visualization of modules
function createModuleTree(showExternal = true, groupModules = true) {
    if (!dependencyData || !dependencyData.file_tree) {
        showError('No file tree data available');
        return;
    }
    
    const width = visualizationContainer.clientWidth;
    const height = visualizationContainer.clientHeight;
    
    const svg = d3.select(visualizationContainer)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', [0, 0, width, height]);
    
    // Add zoom functionality
    const g = svg.append('g')
        .attr('transform', `translate(${width / 2}, ${height / 2})`);
    
    zoomBehavior = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
            g.attr('transform', `translate(${event.transform.x}, ${event.transform.y}) scale(${event.transform.k})`);
        });
    
    svg.call(zoomBehavior);
    
    // Create a hierarchy from the file tree
    const root = d3.hierarchy(dependencyData.file_tree);
    
    // Configure the tree layout
    const treeLayout = d3.tree()
        .size([2 * Math.PI, Math.min(width, height) / 2 - 80]);
    
    // Compute the tree layout
    treeLayout(root);
    
    // Add links
    const link = g.append('g')
        .attr('fill', 'none')
        .attr('stroke', '#999')
        .attr('stroke-opacity', 0.4)
        .attr('stroke-width', 1.5)
        .selectAll('path')
        .data(root.links())
        .join('path')
        .attr('d', d3.linkRadial()
            .angle(d => d.x)
            .radius(d => d.y));
    
    // Add nodes
    const node = g.append('g')
        .selectAll('g')
        .data(root.descendants())
        .join('g')
        .attr('transform', d => `
            translate(${d.y * Math.sin(d.x)},
                     ${-d.y * Math.cos(d.x)})
        `)
        .attr('class', d => {
            let classes = `node ${d.data.type === 'file' ? 'file' : 'directory'}`;
            if (d.data.type === 'directory' && expandedModules.has(d.data.name)) {
                classes += ' expanded';
            }
            return classes;
        });
    
    // Add node circles
    node.append('circle')
        .attr('r', d => d.data.type === 'directory' ? 7 : 4)
        .attr('fill', d => {
            // Highlight expanded directories
            if (d.data.type === 'directory' && expandedModules.has(d.data.name)) {
                return '#22c55e'; // Success color for expanded
            }
            return d.data.type === 'directory' ? '#2563eb' : '#64748b';
        });
    
    // Add node labels
    node.append('text')
        .attr('dy', '0.31em')
        .attr('x', d => d.x < Math.PI ? 10 : -10)
        .attr('text-anchor', d => d.x < Math.PI ? 'start' : 'end')
        .attr('transform', d => d.x < Math.PI ? null : 'rotate(180)')
        .text(d => d.data.name);
    
    // Add text shadow/outline for better visibility in both light and dark mode
    node.append('text')
        .attr('dy', '0.31em')
        .attr('x', d => d.x < Math.PI ? 10 : -10)
        .attr('text-anchor', d => d.x < Math.PI ? 'start' : 'end')
        .attr('transform', d => d.x < Math.PI ? null : 'rotate(180)')
        .attr('class', 'shadow')
        .text(d => d.data.name)
        .lower();
    
    // Handle node click to show details
    node.on('click', (event, d) => {
        showNodeDetails({
            id: d.data.path,
            name: d.data.name,
            type: d.data.type,
            language: d.data.language
        });
        
        // Toggle expansion for directories
        if (d.data.type === 'directory') {
            if (expandedModules.has(d.data.name)) {
                expandedModules.delete(d.data.name);
            } else {
                expandedModules.add(d.data.name);
            }
            updateVisualization();
        }
    });
    
    // Set the current visualization
    currentVisualization = {
        type: 'module-tree',
        svg: svg
    };
    
    // Center the view
    svg.call(zoomBehavior.transform, d3.zoomIdentity);
}

// Create a treemap visualization of file sizes
function createFileSizeTreemap() {
    if (!dependencyData || !dependencyData.file_tree || !dependencyData.file_sizes) {
        showError('No file size data available');
        return;
    }
    
    const width = visualizationContainer.clientWidth;
    const height = visualizationContainer.clientHeight;
    
    const svg = d3.select(visualizationContainer)
        .append('svg')
        .attr('width', width)
        .attr('height', height);
    
    // Add zoom functionality
    const g = svg.append('g');
    
    zoomBehavior = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        });
    
    svg.call(zoomBehavior);
    
    // Process the file tree to add size information
    function addSizeToTree(node) {
        if (node.type === 'file') {
            node.size = dependencyData.file_sizes[node.path] || 1;
        } else {
            let totalSize = 0;
            if (node.children) {
                node.children.forEach(child => {
                    totalSize += addSizeToTree(child);
                });
            }
            node.size = totalSize || 1;
        }
        return node.size;
    }
    
    const treemapData = JSON.parse(JSON.stringify(dependencyData.file_tree));
    addSizeToTree(treemapData);
    
    // Function to expand/collapse parts of the tree based on expandedModules
    function expandTreeNodes(node, depth = 0) {
        // For the root node or explicitly expanded directories, show children
        const isExpanded = node.name && expandedModules.has(node.name);
        
        if (depth === 0 || isExpanded || depth < 2) {
            if (node.children) {
                // Process each child recursively
                node.children = node.children.map(child => expandTreeNodes(child, depth + 1));
                return node;
            }
        } else if (node.type === 'directory' && node.children) {
            // Collapsed directory keeps its size but hides children
            node._children = node.children; // Store children
            node.children = null; // Hide them
        }
        
        return node;
    }
    
    // Apply expansion based on expandedModules
    const processedTreemap = JSON.parse(JSON.stringify(treemapData));
    expandTreeNodes(processedTreemap);
    
    // Create a hierarchy from the file tree
    const root = d3.hierarchy(processedTreemap)
        .sum(d => d.size)
        .sort((a, b) => b.value - a.value);
    
    // Create a color scale based on file type
    const colorScale = d3.scaleOrdinal()
        .domain(['Python', 'JavaScript', 'HTML', 'CSS', 'Other'])
        .range(['#2563eb', '#f59e0b', '#ef4444', '#22c55e', '#64748b']);
    
    // Configure the treemap layout
    const treemap = d3.treemap()
        .size([width, height])
        .paddingOuter(3)
        .paddingTop(19)
        .paddingInner(1)
        .round(true);
    
    // Compute the treemap layout
    treemap(root);
    
    // Create the treemap cells
    const cell = g.selectAll('g')
        .data(root.descendants())
        .join('g')
        .attr('transform', d => `translate(${d.x0},${d.y0})`);
    
    // Add cell backgrounds
    cell.append('rect')
        .attr('width', d => d.x1 - d.x0)
        .attr('height', d => d.y1 - d.y0)
        .attr('fill', d => {
            if (d.depth === 0) return 'none';
            if (d.data.type === 'directory') {
                // Highlight expanded directories
                if (d.data.name && expandedModules.has(d.data.name)) {
                    return '#dcfce7'; // Light green background for expanded directories
                }
                return d.depth === 1 ? '#f1f5f9' : '#e2e8f0';
            }
            return colorScale(d.data.language || 'Other');
        })
        .attr('stroke', '#ffffff')
        .attr('class', 'treemap-node')
        .attr('cursor', 'pointer')
        .append('title')
        .text(d => `${d.ancestors().map(d => d.data.name).reverse().join('/')}\nSize: ${formatBytes(d.value)}`);
    
    // Add text labels to cells that are big enough
    cell.filter(d => (d.x1 - d.x0) > 40 && (d.y1 - d.y0) > 20)
        .append('text')
        .attr('x', 4)
        .attr('y', 14)
        .attr('fill', d => d.depth === 1 ? '#1e293b' : '#ffffff')
        .attr('class', 'treemap-label')
        .text(d => d.data.name);
    
    // Add size labels to cells that are big enough
    cell.filter(d => d.data.type === 'file' && (d.x1 - d.x0) > 60 && (d.y1 - d.y0) > 40)
        .append('text')
        .attr('x', 4)
        .attr('y', 30)
        .attr('fill', '#ffffff')
        .attr('font-size', '10px')
        .attr('class', 'treemap-label')
        .text(d => formatBytes(d.value));
    
    // Add expand/collapse indicators for directories
    cell.filter(d => d.data.type === 'directory' && d.depth > 0 && (d.x1 - d.x0) > 40)
        .append('text')
        .attr('x', d => d.x1 - d.x0 - 15)
        .attr('y', 14)
        .attr('text-anchor', 'end')
        .attr('class', 'expand-indicator')
        .attr('fill', '#1e293b')
        .text(d => expandedModules.has(d.data.name) ? '[-]' : '[+]');
    
    // Handle cell click to show details and toggle expansion
    cell.on('click', (event, d) => {
        // Show node details
        showNodeDetails({
            id: d.data.path,
            name: d.data.name,
            type: d.data.type,
            language: d.data.language,
            size: d.value
        });
        
        // Toggle expansion for directories
        if (d.data.type === 'directory' && d.depth > 0) {
            if (expandedModules.has(d.data.name)) {
                expandedModules.delete(d.data.name);
            } else {
                expandedModules.add(d.data.name);
            }
            updateVisualization();
        }
    });
    
    // Set the current visualization
    currentVisualization = {
        type: 'file-size-treemap',
        svg: svg
    };
    
    // Center the view
    svg.call(zoomBehavior.transform, d3.zoomIdentity);
}

// Function to search for nodes
function searchNodes() {
    const searchText = searchModule.value.toLowerCase();
    
    if (!searchText || !currentVisualization) return;
    
    // Clear previous highlighting
    d3.selectAll('.highlighted').classed('highlighted', false);
    
    // Highlight matching nodes
    if (currentVisualization.type === 'dependency-graph') {
        const nodes = d3.selectAll('.node');
        const links = d3.selectAll('.link');
        
        // Highlight nodes that match the search
        nodes.classed('highlighted', d => d.name.toLowerCase().includes(searchText));
        
        // Highlight links connected to matching nodes
        links.classed('highlighted', d => {
            return d.source.name.toLowerCase().includes(searchText) || 
                   d.target.name.toLowerCase().includes(searchText);
        });
    } else if (currentVisualization.type === 'module-tree') {
        const nodes = d3.selectAll('.node');
        
        // Highlight nodes that match the search
        nodes.classed('highlighted', d => d.data.name.toLowerCase().includes(searchText));
    } else if (currentVisualization.type === 'file-size-treemap') {
        const cells = d3.selectAll('.treemap-node');
        
        // Highlight cells that match the search
        cells.classed('highlighted', d => d.data.name.toLowerCase().includes(searchText));
    }
}

// Show details for the selected node
function showNodeDetails(node) {
    selectedNodeName.textContent = node.name;
    visualizationInfo.classList.remove('hidden');
    
    // Clear previous details
    nodeDetails.innerHTML = '';
    
    if (node.type === 'file') {
        // Show file details
        nodeDetails.innerHTML = `
            <div class="node-detail-item">
                <span class="node-detail-label">Path:</span>
                <span>${node.id || 'Unknown'}</span>
            </div>
            <div class="node-detail-item">
                <span class="node-detail-label">Type:</span>
                <span>${node.type}</span>
            </div>
            <div class="node-detail-item">
                <span class="node-detail-label">Language:</span>
                <span>${node.language || 'Unknown'}</span>
            </div>
            ${node.size ? `
            <div class="node-detail-item">
                <span class="node-detail-label">Size:</span>
                <span>${formatBytes(node.size)}</span>
            </div>
            ` : ''}
        `;
        
        // Show code details if available
        if (dependencyData.modules && dependencyData.modules[node.id]) {
            const moduleInfo = dependencyData.modules[node.id];
            
            // Show functions
            if (moduleInfo.functions && moduleInfo.functions.length > 0) {
                const functionsList = moduleInfo.functions.map(f => 
                    `<div class="detail-function">${f.name}(${f.args.join(', ')})</div>`
                ).join('');
                
                nodeDetails.innerHTML += `
                    <div class="node-detail-item">
                        <span class="node-detail-label">Functions:</span>
                        <div>${functionsList}</div>
                    </div>
                `;
            }
            
            // Show classes
            if (moduleInfo.classes && moduleInfo.classes.length > 0) {
                const classesList = moduleInfo.classes.map(c => 
                    `<div class="detail-class">${c.name}${c.bases.length > 0 ? `(${c.bases.join(', ')})` : ''}</div>`
                ).join('');
                
                nodeDetails.innerHTML += `
                    <div class="node-detail-item">
                        <span class="node-detail-label">Classes:</span>
                        <div>${classesList}</div>
                    </div>
                `;
            }
            
            // Show imports
            if (moduleInfo.imports && moduleInfo.imports.length > 0) {
                const importsList = moduleInfo.imports.map(i => 
                    `<div class="detail-import">${i.type === 'from' ? `from ${i.module} import ${i.name}` : `import ${i.name}`}</div>`
                ).join('');
                
                nodeDetails.innerHTML += `
                    <div class="node-detail-item">
                        <span class="node-detail-label">Imports:</span>
                        <div>${importsList}</div>
                    </div>
                `;
            }
        }
    } else if (node.isModule) {
        // Show module details
        const isExpanded = expandedModules.has(node.name);
        
        nodeDetails.innerHTML = `
            <div class="node-detail-item">
                <span class="node-detail-label">Module:</span>
                <span>${node.name}</span>
            </div>
            <div class="node-detail-item">
                <span class="node-detail-label">Files:</span>
                <span>${node.children ? node.children.length : 0}</span>
            </div>
            ${node.size ? `
            <div class="node-detail-item">
                <span class="node-detail-label">Size:</span>
                <span>${formatBytes(node.size)}</span>
            </div>
            ` : ''}
            <div class="node-detail-item">
                <span class="node-detail-label">Status:</span>
                <span>${isExpanded ? 'Expanded' : 'Collapsed'}</span>
                <button class="toggle-expand-btn" onclick="toggleExpansion('${node.name}')">
                    ${isExpanded ? 'Collapse' : 'Expand'}
                </button>
            </div>
        `;
        
        // List files in this module
        if (node.children && node.children.length > 0) {
            const filesList = node.children.map(file => 
                `<div class="detail-file">${file.name}</div>`
            ).join('');
            
            nodeDetails.innerHTML += `
                <div class="node-detail-item">
                    <span class="node-detail-label">Contains:</span>
                    <div>${filesList}</div>
                </div>
            `;
        }
    } else {
        // Show directory details
        const isExpanded = node.name ? expandedModules.has(node.name) : false;
        
        nodeDetails.innerHTML = `
            <div class="node-detail-item">
                <span class="node-detail-label">Directory:</span>
                <span>${node.name}</span>
            </div>
            <div class="node-detail-item">
                <span class="node-detail-label">Path:</span>
                <span>${node.id || 'Unknown'}</span>
            </div>
            ${node.size ? `
            <div class="node-detail-item">
                <span class="node-detail-label">Size:</span>
                <span>${formatBytes(node.size)}</span>
            </div>
            ` : ''}
            ${node.name ? `
            <div class="node-detail-item">
                <span class="node-detail-label">Status:</span>
                <span>${isExpanded ? 'Expanded' : 'Collapsed'}</span>
                <button class="toggle-expand-btn" onclick="toggleExpansion('${node.name}')">
                    ${isExpanded ? 'Collapse' : 'Expand'}
                </button>
            </div>
            ` : ''}
        `;
    }
}

// Helper functions
function getFileName(path) {
    return path.split('/').pop();
}

function getModuleName(path) {
    const parts = path.split('/');
    if (parts.length > 1) {
        return parts[0];
    }
    return 'root';
}

function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// Global function to toggle expansion from the details panel
window.toggleExpansion = function(name) {
    if (expandedModules.has(name)) {
        expandedModules.delete(name);
    } else {
        expandedModules.add(name);
    }
    updateVisualization();
}