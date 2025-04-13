// DOM Elements
const repoUrlInput = document.getElementById('repo-url');
const cloneBtn = document.getElementById('clone-btn');
const setupBtn = document.getElementById('setup-btn');
const questionInput = document.getElementById('question-input');
const askBtn = document.getElementById('ask-btn');
const messagesContainer = document.getElementById('messages');
const repoStatus = document.getElementById('repo-status');
const themeToggleBtn = document.getElementById('theme-toggle');
const htmlElement = document.documentElement;

// GitHub Auth Elements
const useGithubApiCheckbox = document.getElementById('use-github-api');
const authForm = document.getElementById('auth-form');
const githubTokenInput = document.getElementById('github-token');
const authBtn = document.getElementById('auth-btn');
const authStatus = document.getElementById('auth-status');

// Structure View Elements
const toggleCodeStructureBtn = document.getElementById('toggle-code-structure');
const visualizeCodeBtn = document.getElementById('visualize-code');
const clearChatBtn = document.getElementById('clear-chat');
const codeStructurePanel = document.getElementById('code-structure-panel');
const closeStructureBtn = document.getElementById('close-structure');
const structureContent = document.getElementById('structure-content');

// Search Settings Elements
const hybridSearchCheckbox = document.getElementById('hybrid-search');
const semanticWeightSlider = document.getElementById('semantic-weight');
const semanticWeightValue = document.getElementById('semantic-weight-value');

// Status indicators
const vectorizerStatus = document.getElementById('vectorizer-status');
const llmStatus = document.getElementById('llm-status');

// Loading elements
const repoLoading = document.getElementById('repo-loading');
const repoProgress = document.getElementById('repo-progress');
const modelLoading = document.getElementById('model-loading');
const modelProgress = document.getElementById('model-progress');
const modelPercent = document.getElementById('model-percent');
const thinkingContainer = document.getElementById('thinking-container');

// Enhanced thinking elements
const thinkingTimeElement = document.getElementById('thinking-time');
const thinkingMessageElement = document.getElementById('thinking-message');
const thinkingStep1 = document.getElementById('thinking-step-1');
const thinkingStep2 = document.getElementById('thinking-step-2');
const thinkingStep3 = document.getElementById('thinking-step-3');

// Initialize state
let chatHistory = [];
let monitoringProgress = false;
let activeOperations = {};
let progressInterval = null;
let modelsReady = false;
let githubToken = null;
let codeStructure = null;
let currentRepository = null;

// Add these variables for tracking thinking state
let thinkingStartTime = 0;
let thinkingTimer = null;
let currentThinkingStep = 1;

// Event Listeners
cloneBtn.addEventListener('click', cloneRepository);
setupBtn.addEventListener('click', setupSystem);
askBtn.addEventListener('click', askQuestion);
themeToggleBtn.addEventListener('click', toggleTheme);
useGithubApiCheckbox.addEventListener('change', toggleAuthForm);
authBtn.addEventListener('click', authenticateGithub);
toggleCodeStructureBtn.addEventListener('click', toggleCodeStructure);
visualizeCodeBtn.addEventListener('click', visualizeCode);
clearChatBtn.addEventListener('click', clearChat);
closeStructureBtn.addEventListener('click', hideCodeStructure);

// Add event listener for the semantic weight slider
semanticWeightSlider.addEventListener('input', updateSemanticWeightDisplay);

questionInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        askQuestion();
    }
});

// Start monitoring progress and load application state as soon as the page loads
document.addEventListener('DOMContentLoaded', () => {
    startProgressMonitoring();
    checkSystemStatus();
    loadUserPreferences();
    maintainScrollPosition();
});

// Functions
function loadUserPreferences() {
    // Load theme preference
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        htmlElement.setAttribute('data-theme', savedTheme);
        updateThemeIcon(savedTheme);
    } else {
        // Check for OS preference
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            htmlElement.setAttribute('data-theme', 'dark');
            updateThemeIcon('dark');
        }
    }
    
    // Load GitHub token
    const savedToken = localStorage.getItem('github_token');
    if (savedToken) {
        githubToken = savedToken;
        useGithubApiCheckbox.checked = true;
        authStatus.textContent = 'Authenticated';
        authStatus.classList.add('authenticated');
        toggleAuthForm();
    }
    
    // Load search settings
    const savedHybridSearch = localStorage.getItem('hybrid_search');
    if (savedHybridSearch !== null) {
        hybridSearchCheckbox.checked = savedHybridSearch === 'true';
    }
    
    const savedSemanticWeight = localStorage.getItem('semantic_weight');
    if (savedSemanticWeight !== null) {
        semanticWeightSlider.value = savedSemanticWeight;
        updateSemanticWeightDisplay();
    }
    
    // Load chat history
    const savedChatHistory = localStorage.getItem('chat_history');
    if (savedChatHistory) {
        try {
            const parsedHistory = JSON.parse(savedChatHistory);
            if (Array.isArray(parsedHistory) && parsedHistory.length > 0) {
                chatHistory = parsedHistory;
                
                // Check if we should restore the last session
                const restoreLast = localStorage.getItem('restore_last_session');
                if (restoreLast === 'true') {
                    restoreLastChatSession();
                }
            }
        } catch (error) {
            console.error('Error loading chat history:', error);
        }
    }
}

function updateSemanticWeightDisplay() {
    // Update the display value with the current slider value
    semanticWeightValue.textContent = `${semanticWeightSlider.value}%`;
    
    // Save the value to localStorage
    localStorage.setItem('semantic_weight', semanticWeightSlider.value);
}

function toggleTheme() {
    const currentTheme = htmlElement.getAttribute('data-theme') || 'light';
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    
    htmlElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const icon = themeToggleBtn.querySelector('i');
    if (theme === 'dark') {
        icon.className = 'fas fa-sun';
    } else {
        icon.className = 'fas fa-moon';
    }
}

function toggleAuthForm() {
    if (useGithubApiCheckbox.checked) {
        authForm.style.display = 'block';
    } else {
        authForm.style.display = 'none';
        // If already authenticated, show warning
        if (githubToken) {
            const confirmUnauthenticate = confirm('You are currently authenticated. Do you want to proceed without GitHub authentication?');
            if (confirmUnauthenticate) {
                githubToken = null;
                localStorage.removeItem('github_token');
                authStatus.textContent = 'Not authenticated';
                authStatus.classList.remove('authenticated');
            } else {
                useGithubApiCheckbox.checked = true;
                authForm.style.display = 'block';
            }
        }
    }
}

function authenticateGithub() {
    const token = githubTokenInput.value.trim();
    
    if (!token) {
        alert('Please enter a valid GitHub token');
        return;
    }
    
    // Validate token
    fetch('https://api.github.com/user', {
        headers: {
            'Authorization': `token ${token}`
        }
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        }
        throw new Error('Invalid token');
    })
    .then(user => {
        // Save token
        githubToken = token;
        localStorage.setItem('github_token', token);
        
        // Update UI
        authStatus.textContent = `Authenticated as ${user.login}`;
        authStatus.classList.add('authenticated');
        
        // Clear input for security
        githubTokenInput.value = '';
        
        // Show success message
        addMessage(`Successfully authenticated with GitHub as ${user.login}`, 'system');
    })
    .catch(error => {
        console.error('Authentication error:', error);
        authStatus.textContent = 'Authentication failed';
        authStatus.classList.remove('authenticated');
        alert('Authentication failed: ' + error.message);
    });
}

async function checkSystemStatus() {
    try {
        const response = await fetch('/api/system-status');
        const data = await response.json();
        
        // Update model status indicators
        updateModelStatus(data.vectorizer.exists, vectorizerStatus, 'Vectorizer');
        updateModelStatus(data.llm.exists, llmStatus, 'LLM');
        
        // Show setup button if models are not ready
        if (!data.vectorizer.exists || !data.llm.exists) {
            setupBtn.style.display = 'block';
            modelsReady = false;
        } else {
            setupBtn.style.display = 'none';
            modelsReady = true;
        }
        
        // Update repository status if available
        if (data.repository) {
            currentRepository = data.repository;
            repoUrlInput.value = data.repository.url;
            updateStatus(repoStatus, `Repository: ${data.repository.name}`, 'success');
            
            if (data.repository.indexed) {
                // Enable question input if repository is indexed
                questionInput.disabled = false;
                askBtn.disabled = false;
                visualizeCodeBtn.disabled = false;
                
                // Add a welcome message with repository information
                addMessage(`The repository "${data.repository.name}" is loaded and indexed. You can ask questions about the code.`, 'system');
                
                // Load code structure
                loadCodeStructure();
            }
        } else {
            // Disable visualization if no repository
            visualizeCodeBtn.disabled = true;
        }
    } catch (error) {
        console.error('Error checking system status:', error);
        updateStatus(repoStatus, 'Error checking system status. Please refresh the page.', 'error');
    }
}

function updateModelStatus(exists, element, label) {
    if (exists) {
        element.className = 'status-badge ready';
        element.querySelector('.value').textContent = 'Ready';
    } else {
        element.className = 'status-badge not-found';
        element.querySelector('.value').textContent = 'Not Found';
    }
}

async function setupSystem() {
    try {
        // Disable buttons
        setupBtn.disabled = true;
        cloneBtn.disabled = true;
        
        // Show status message
        addMessage('Setting up system components. This may take a few minutes...', 'system');
        
        // Start setup process
        const response = await fetch('/api/setup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        const data = await response.json();
        
        // Handle response
        if (data.status === 'success') {
            addMessage('System setup completed successfully! You can now clone a repository.', 'system');
            setupBtn.style.display = 'none';
            modelsReady = true;
            
            // Update status indicators
            updateModelStatus(true, vectorizerStatus, 'Vectorizer');
            updateModelStatus(true, llmStatus, 'LLM');
        } else {
            addMessage(`Error setting up system: ${data.message}`, 'system');
        }
        
        // Re-enable buttons
        setupBtn.disabled = false;
        cloneBtn.disabled = false;
        
    } catch (error) {
        console.error('Error setting up system:', error);
        addMessage(`Error setting up system: ${error.message}`, 'system');
        setupBtn.disabled = false;
        cloneBtn.disabled = false;
    }
}

async function cloneRepository() {
    const repoUrl = repoUrlInput.value.trim();
    
    if (!repoUrl) {
        updateStatus(repoStatus, 'Please enter a valid GitHub repository URL.', 'error');
        return;
    }
    
    try {
        // Check if we need to set up models first
        if (!modelsReady) {
            const setupConfirm = confirm('Models need to be downloaded first. Do you want to set up the system now?');
            if (setupConfirm) {
                await setupSystem();
                if (!modelsReady) {
                    return; // Setup failed or was cancelled
                }
            } else {
                return; // User declined setup
            }
        }
        
        // Disable buttons and show loading
        cloneBtn.disabled = true;
        repoLoading.style.display = 'block';
        
        // Reset progress
        repoProgress.style.width = '0%';
        
        // Show status message
        addMessage(`Cloning and indexing repository: ${repoUrl}. This might take a few minutes...`, 'system');
        
        // Prepare request data
        const requestData = { repo_url: repoUrl };
        
        // Add GitHub token if available
        if (githubToken && useGithubApiCheckbox.checked) {
            requestData.token = githubToken;
        }
        
        // Send request to clone and index repository
        const response = await fetch('/api/clone', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData),
        });
        
        const data = await response.json();
        
        // Handle response
        if (data.status === 'success') {
            updateStatus(repoStatus, `Repository ${data.repo_name} cloned and indexed successfully`, 'success');
            
            // Update current repository
            currentRepository = {
                name: data.repo_name,
                url: repoUrl,
                indexed: true
            };
            
            // Enable question input and visualization
            questionInput.disabled = false;
            askBtn.disabled = false;
            visualizeCodeBtn.disabled = false;
            
            // Set progress to 100%
            repoProgress.style.width = '100%';
            
            // Add success message
            addMessage(`Repository ${data.repo_name} is ready. You can now ask questions about the code.`, 'system');
            
            // Hide loading after a delay
            setTimeout(() => {
                repoLoading.style.display = 'none';
            }, 1000);
            
            // Load code structure
            loadCodeStructure();
            
            // Save chat history for new repository session
            saveChat();
        } else {
            updateStatus(repoStatus, data.message, 'error');
            repoLoading.style.display = 'none';
            addMessage(`Error: ${data.message}`, 'system');
        }
        
        cloneBtn.disabled = false;
        
    } catch (error) {
        console.error('Error cloning repository:', error);
        repoLoading.style.display = 'none';
        updateStatus(repoStatus, 'Error: ' + error.message, 'error');
        addMessage(`Error: ${error.message}`, 'system');
        cloneBtn.disabled = false;
    }
}

async function loadCodeStructure() {
    if (!currentRepository || !currentRepository.indexed) {
        return;
    }
    
    try {
        // Show loading message
        structureContent.innerHTML = '<div class="structure-loading">Loading code structure...</div>';
        
        // Fetch code structure
        const response = await fetch('/api/code-structure', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            codeStructure = data.structure;
            renderCodeStructure(codeStructure);
        } else {
            structureContent.innerHTML = `<div class="error">Error loading code structure: ${data.message}</div>`;
        }
    } catch (error) {
        console.error('Error loading code structure:', error);
        structureContent.innerHTML = `<div class="error">Error loading code structure: ${error.message}</div>`;
    }
}

function renderCodeStructure(structure) {
    if (!structure) {
        structureContent.innerHTML = '<div class="error">No structure data available</div>';
        return;
    }
    
    const treeHtml = buildTreeHtml(structure);
    structureContent.innerHTML = `<div class="structure-tree">${treeHtml}</div>`;
    
    // Add event listeners to toggles
    const toggles = structureContent.querySelectorAll('.tree-toggle');
    toggles.forEach(toggle => {
        toggle.addEventListener('click', () => {
            toggle.classList.toggle('open');
        });
    });
    
    // Add event listeners to files
    const files = structureContent.querySelectorAll('.tree-file');
    files.forEach(file => {
        file.addEventListener('click', () => {
            const path = file.getAttribute('data-path');
            if (path) {
                askAboutFile(path);
            }
        });
    });
}

function buildTreeHtml(node) {
    if (node.type === 'file') {
        return `<div class="tree-item">
            <span class="tree-file" data-path="${node.path}">${node.name}</span>
        </div>`;
    } else if (node.type === 'directory') {
        let childrenHtml = '';
        if (node.children && node.children.length > 0) {
            childrenHtml = node.children.map(child => buildTreeHtml(child)).join('');
        }
        
        return `<div class="tree-item">
            <span class="tree-toggle tree-folder">${node.name}</span>
            <div class="tree-children">${childrenHtml}</div>
        </div>`;
    }
    
    return '';
}

function askAboutFile(filePath) {
    if (!questionInput.disabled) {
        questionInput.value = `Explain what the file "${filePath}" does.`;
        questionInput.focus();
    }
}

function toggleCodeStructure() {
    toggleCodeStructureBtn.classList.toggle('active');
    
    if (toggleCodeStructureBtn.classList.contains('active')) {
        codeStructurePanel.style.display = 'flex';
        if (!codeStructure) {
            loadCodeStructure();
        }
    } else {
        codeStructurePanel.style.display = 'none';
    }
}

function visualizeCode() {
    // Redirect to the visualization page in the same window
    if (currentRepository && currentRepository.indexed) {
        window.location.href = '/visualization';
    } else {
        alert('Please clone and index a repository first before visualizing code.');
    }
}

function hideCodeStructure() {
    codeStructurePanel.style.display = 'none';
    toggleCodeStructureBtn.classList.remove('active');
}

function clearChat() {
    // Confirm clear
    if (chatHistory.length > 0) {
        const confirmClear = confirm('Are you sure you want to clear the current chat history?');
        if (!confirmClear) {
            return;
        }
    }
    
    // Clear chat history
    chatHistory = [];
    
    // Clear chat display
    messagesContainer.innerHTML = `
        <div class="message system">
            <div class="message-content">
                <p>Chat history cleared. You can start a new conversation.</p>
            </div>
        </div>
    `;
    
    // Save empty chat history
    saveChat();
}

function restoreLastChatSession() {
    // Clear current messages
    messagesContainer.innerHTML = '';
    
    // Add messages from history
    chatHistory.forEach(msg => {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${msg.sender}`;
        
        const contentElement = document.createElement('div');
        contentElement.className = 'message-content';
        
        // Format code blocks in the message
        if (msg.sender === 'assistant') {
            contentElement.innerHTML = formatCodeBlocks(msg.text);
        } else {
            contentElement.textContent = msg.text;
        }
        
        messageElement.appendChild(contentElement);
        messagesContainer.appendChild(messageElement);
    });
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * Maintains scroll position when thinking indicator shows/hides
 * This ensures users can still browse chat history during processing
 */
function maintainScrollPosition() {
    // Get current scroll position
    const scrollPosition = messagesContainer.scrollTop;
    
    // Store latest scroll position in an attribute
    messagesContainer.setAttribute('data-last-scroll', scrollPosition);
    
    // Observer for the thinking container visibility changes
    const thinkingObserver = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.attributeName === 'style') {
                const isThinkingVisible = thinkingContainer.style.display !== 'none';
                
                // Get stored scroll position
                const lastScroll = parseInt(messagesContainer.getAttribute('data-last-scroll') || '0');
                
                // If thinking became visible, ensure messages area stays scrollable
                if (isThinkingVisible) {
                    // Add a small delay to ensure DOM updates are complete
                    setTimeout(() => {
                        // Restore scroll position
                        messagesContainer.scrollTop = lastScroll;
                    }, 50);
                }
            }
        });
    });
    
    // Start observing the thinking container for style changes
    thinkingObserver.observe(thinkingContainer, { attributes: true });
    
    // Also add event listener to save scroll position when user scrolls
    messagesContainer.addEventListener('scroll', () => {
        const currentScroll = messagesContainer.scrollTop;
        messagesContainer.setAttribute('data-last-scroll', currentScroll);
    });
}

// Enhanced thinking functions
function updateThinkingTimer() {
    const elapsedSeconds = Math.floor((Date.now() - thinkingStartTime) / 1000);
    let timeDisplay;
    
    if (elapsedSeconds < 60) {
        timeDisplay = `${elapsedSeconds}s`;
    } else {
        const minutes = Math.floor(elapsedSeconds / 60);
        const seconds = elapsedSeconds % 60;
        timeDisplay = `${minutes}m ${seconds}s`;
    }
    
    thinkingTimeElement.textContent = timeDisplay;
    
    // Add messages based on elapsed time
    if (elapsedSeconds > 10 && elapsedSeconds < 20) {
        thinkingMessageElement.textContent = "This might take a moment for complex questions...";
    } else if (elapsedSeconds >= 20 && elapsedSeconds < 40) {
        thinkingMessageElement.textContent = "Analyzing the code in detail...";
    } else if (elapsedSeconds >= 40) {
        thinkingMessageElement.textContent = "Still working on it. Complex questions may take a bit longer...";
    }
}

function startThinking() {
    // First save current scroll position
    const scrollPosition = messagesContainer.scrollTop;
    
    // Reset the thinking UI
    resetThinkingUI();
    
    // Show thinking container
    thinkingContainer.style.display = 'block';
    
    // Record start time and start timer
    thinkingStartTime = Date.now();
    thinkingTimer = setInterval(updateThinkingTimer, 1000);
    
    // Start with step 1 active
    setThinkingStep(1);
    
    // Restore scroll position after a short delay
    setTimeout(() => {
        messagesContainer.scrollTop = scrollPosition;
    }, 50);
}

function stopThinking() {
    // Hide thinking container
    thinkingContainer.style.display = 'none';
    
    // Clear timer
    if (thinkingTimer) {
        clearInterval(thinkingTimer);
        thinkingTimer = null;
    }
}

function resetThinkingUI() {
    // Reset all steps
    thinkingStep1.className = "thinking-step";
    thinkingStep2.className = "thinking-step";
    thinkingStep3.className = "thinking-step";
    
    // Clear statuses
    thinkingStep1.querySelector('.step-status').innerHTML = "";
    thinkingStep2.querySelector('.step-status').innerHTML = "";
    thinkingStep3.querySelector('.step-status').innerHTML = "";
    
    // Reset message and time
    thinkingMessageElement.textContent = "Starting processing...";
    thinkingTimeElement.textContent = "0s";
    
    // Reset current step
    currentThinkingStep = 1;
}

function setThinkingStep(step) {
    // Update current step
    currentThinkingStep = step;
    
    // Mark previous steps as completed
    for (let i = 1; i < step; i++) {
        const prevStep = document.getElementById(`thinking-step-${i}`);
        prevStep.className = "thinking-step completed";
        prevStep.querySelector('.step-status').innerHTML = '<i class="fas fa-check-circle"></i>';
    }
    
    // Set current step as active
    const activeStep = document.getElementById(`thinking-step-${step}`);
    activeStep.className = "thinking-step active";
    activeStep.querySelector('.step-status').innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    
    // Update message based on step
    if (step === 1) {
        thinkingMessageElement.textContent = "Finding relevant code snippets...";
    } else if (step === 2) {
        thinkingMessageElement.textContent = "Analyzing code context...";
    } else if (step === 3) {
        thinkingMessageElement.textContent = "Generating detailed response...";
    }
}

function simulateThinkingProgress() {
    // Note: In a production app, you'd ideally get real updates from the backend
    // This is a simplified simulation for demonstration
    
    // Schedule step 2 after 3 seconds
    setTimeout(() => {
        if (thinkingTimer) {  // Only proceed if we're still thinking
            setThinkingStep(2);
        }
    }, 3000);
    
    // Schedule step 3 after 6 seconds
    setTimeout(() => {
        if (thinkingTimer) {  // Only proceed if we're still thinking
            setThinkingStep(3);
        }
    }, 6000);
}

async function askQuestion() {
    const question = questionInput.value.trim();
    
    if (!question) {
        return;
    }
    
    try {
        // Add user message to chat
        addMessage(question, 'user');
        
        // Clear input
        questionInput.value = '';
        
        // Disable inputs during processing
        questionInput.disabled = true;
        askBtn.disabled = true;
        
        // Show enhanced thinking indicator with steps
        startThinking();
        simulateThinkingProgress();  // Start the automatic progression
        
        // Prepare request data
        const requestData = {
            question: question,
            hybrid_search: hybridSearchCheckbox.checked,
            semantic_weight: parseFloat(semanticWeightSlider.value) / 100
        };
        
        // Save search settings
        localStorage.setItem('hybrid_search', hybridSearchCheckbox.checked);
        
        // Send request to ask question
        const response = await fetch('/api/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData),
        });
        
        const data = await response.json();
        
        // Hide thinking indicator
        stopThinking();
        
        // Handle response
        if (data.status === 'success') {
            // Add assistant response to chat
            addMessage(data.answer, 'assistant');
        } else {
            // Add error message
            addMessage(`Error: ${data.message}`, 'system');
        }
        
        // Re-enable inputs
        questionInput.disabled = false;
        askBtn.disabled = false;
        questionInput.focus();
        
    } catch (error) {
        console.error('Error asking question:', error);
        stopThinking();
        addMessage(`Error: ${error.message}`, 'system');
        questionInput.disabled = false;
        askBtn.disabled = false;
    }
}

// Helper Functions
function addMessage(text, sender) {
    // Add to chat history
    chatHistory.push({ text, sender });
    
    // Create message element
    const messageElement = document.createElement('div');
    messageElement.className = `message ${sender}`;
    
    const contentElement = document.createElement('div');
    contentElement.className = 'message-content';
    
    // Format code blocks in the message
    if (sender === 'assistant') {
        contentElement.innerHTML = formatCodeBlocks(text);
    } else {
        contentElement.textContent = text;
    }
    
    messageElement.appendChild(contentElement);
    messagesContainer.appendChild(messageElement);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    // Save chat history
    saveChat();
}

function saveChat() {
    // Save chat history to localStorage
    localStorage.setItem('chat_history', JSON.stringify(chatHistory));
    localStorage.setItem('restore_last_session', 'true');
}

function formatCodeBlocks(text) {
    // Replace markdown code blocks with HTML
    let formattedText = text.replace(/```(\w+)?\n([\s\S]*?)```/g, function(match, language, code) {
        return `<pre><code class="language-${language || 'text'}">${escapeHTML(code)}</code></pre>`;
    });
    
    // Replace inline code
    formattedText = formattedText.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Convert newlines to <br>
    formattedText = formattedText.replace(/\n/g, '<br>');
    
    return formattedText;
}

function escapeHTML(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function updateStatus(element, message, type) {
    element.textContent = message;
    element.className = `status ${type}`;
}

// Progress monitoring
async function startProgressMonitoring() {
    if (monitoringProgress) return;
    
    monitoringProgress = true;
    
    // Start polling for progress updates
    progressInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/progress');
            const data = await response.json();
            
            if (data.operations) {
                updateProgressUI(data.operations);
            }
        } catch (error) {
            console.error('Error fetching progress:', error);
        }
    }, 500); // Poll every 500ms
}

function stopProgressMonitoring() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
    monitoringProgress = false;
}

function updateProgressUI(operations) {
    // Update progress bars based on operation status
    
    for (const [opId, op] of Object.entries(operations)) {
        // Track this operation
        activeOperations[opId] = op;
        
        // Handle different types of operations
        if (opId === 'vectorizer_model_loading' || opId === 'llm_model_loading' || opId === 'setup') {
            // Model loading operations - show in model loading bar
            handleLoadingProgress(op, modelProgress, modelLoading, modelPercent);
            
            // Update status badges when complete
            if (op.status === 'success') {
                if (opId === 'vectorizer_model_loading') {
                    updateModelStatus(true, vectorizerStatus, 'Vectorizer');
                } else if (opId === 'llm_model_loading') {
                    updateModelStatus(true, llmStatus, 'LLM');
                } else if (opId === 'setup') {
                    updateModelStatus(true, vectorizerStatus, 'Vectorizer');
                    updateModelStatus(true, llmStatus, 'LLM');
                    modelsReady = true;
                    setupBtn.style.display = 'none';
                }
            }
        } 
        else if (opId === 'repo_processing') {
            // Repository processing - show in repo loading bar
            handleLoadingProgress(op, repoProgress, repoLoading);
        }
        else if (opId === 'question_answering') {
            // Question answering - show enhanced thinking indicator
            if (op.status === 'in_progress') {
                // Make sure thinking indicator is shown
                if (thinkingContainer.style.display === 'none') {
                    startThinking();
                }
                
                // Update thinking step based on progress
                if (op.progress < 0.3) {
                    setThinkingStep(1); // Finding relevant code
                } else if (op.progress < 0.6) {
                    setThinkingStep(2); // Analyzing context
                } else {
                    setThinkingStep(3); // Generating response
                }
                
                // Update message if provided
                if (op.message) {
                    thinkingMessageElement.textContent = op.message;
                }
            } else {
                // Hide thinking indicator after a short delay
                setTimeout(() => {
                    stopThinking();
                }, 500);
            }
        }
    }
}

function handleLoadingProgress(operation, progressBar, loadingContainer, percentElement = null) {
    // Update progress bar
    const percentage = Math.round(operation.progress * 100);
    progressBar.style.width = `${percentage}%`;
    
    // Show loading container
    loadingContainer.style.display = 'block';
    
    // Update percentage display if available
    if (percentElement) {
        percentElement.textContent = `${percentage}%`;
    }
    
    // Update loading text if there's a message
    const loadingText = loadingContainer.querySelector('.loading-text');
    if (loadingText && operation.message) {
        loadingText.textContent = operation.message;
    }
    
    // If operation is complete, update view
    if (operation.status === 'success' || operation.status === 'error') {
        // When an operation completes, we'll leave the progress bar at 100% briefly
        // before hiding it, for better UX
        if (operation.status === 'success') {
            progressBar.style.width = '100%';
            if (percentElement) {
                percentElement.textContent = '100%';
            }
            
            setTimeout(() => {
                // Only hide if this is still the most recent status for this operation
                if (activeOperations[operation.id]?.end_time === operation.end_time) {
                    loadingContainer.style.display = 'none';
                }
            }, 1000);
        } else {
            // For errors, keep the current progress and show the error message
            setTimeout(() => {
                // Only hide if this is still the most recent status for this operation
                if (activeOperations[operation.id]?.end_time === operation.end_time) {
                    loadingContainer.style.display = 'none';
                }
            }, 3000); // Show errors longer
        }
    }
}