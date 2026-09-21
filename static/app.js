document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chatForm');
    const queryInput = document.getElementById('queryInput');
    const chatHistory = document.getElementById('chatHistory');
    const userSelect = document.getElementById('userSelect');
    const sendBtn = document.getElementById('sendBtn');

    function scrollToBottom() {
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    function addMessage(content, type) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${type}-msg`;
        
        const bubble = document.createElement('div');
        bubble.className = 'msg-bubble';
        
        // Handle markdown-like line breaks
        bubble.innerHTML = content.replace(/\n/g, '<br>');
        
        msgDiv.appendChild(bubble);
        chatHistory.appendChild(msgDiv);
        scrollToBottom();
        return msgDiv;
    }

    function addTypingIndicator() {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message ai-msg typing-container';
        
        const bubble = document.createElement('div');
        bubble.className = 'msg-bubble typing-indicator';
        bubble.innerHTML = `
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        `;
        
        msgDiv.appendChild(bubble);
        chatHistory.appendChild(msgDiv);
        scrollToBottom();
        return msgDiv;
    }

    // Handle user change
    userSelect.addEventListener('change', (e) => {
        chatHistory.innerHTML = ''; // Clear chat
        const name = e.target.options[e.target.selectedIndex].text;
        addMessage(`<span class="icon">🔄</span> Switched context to <b>${name}</b>. Try asking about salaries or financials.`, 'system');
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const query = queryInput.value.trim();
        if (!query) return;
        
        const username = userSelect.value;
        
        // Add user message
        addMessage(query, 'user');
        
        // Clear input and disable
        queryInput.value = '';
        queryInput.disabled = true;
        sendBtn.disabled = true;
        
        // Add loading indicator
        const typingIndicator = addTypingIndicator();
        
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    username: username,
                    query: query
                })
            });
            
            const data = await response.json();
            
            // Remove typing indicator
            typingIndicator.remove();
            
            if (response.ok) {
                addMessage(data.response, 'ai');
            } else {
                addMessage(`❌ Error: ${data.detail || 'Failed to connect to server'}`, 'system');
            }
        } catch (err) {
            typingIndicator.remove();
            addMessage(`❌ Connection Error: Ensure the server is running.`, 'system');
        } finally {
            queryInput.disabled = false;
            sendBtn.disabled = false;
            queryInput.focus();
        }
    });
});
