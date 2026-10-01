/* Admin Password Show/Hide Functionality */
(function() {
    'use strict';
    
    function addPasswordToggleButtons() {
        // Get all password input fields
        const passwordInputs = document.querySelectorAll('input[type="password"]');
        
        passwordInputs.forEach((input, index) => {
            // Check if toggle button already exists
            if (input.nextElementSibling && input.nextElementSibling.classList.contains('password-toggle-btn')) {
                return;
            }
            
            // Create toggle button
            const toggleBtn = document.createElement('button');
            toggleBtn.type = 'button';
            toggleBtn.className = 'password-toggle-btn';
            toggleBtn.innerHTML = '👁️';
            toggleBtn.title = 'Show/Hide Password';
            toggleBtn.style.cssText = `
                position: absolute;
                right: 10px;
                top: 50%;
                transform: translateY(-50%);
                background: none;
                border: none;
                cursor: pointer;
                font-size: 18px;
                padding: 5px 10px;
                color: #666;
                z-index: 10;
            `;
            
            // Create wrapper for positioning
            const wrapper = document.createElement('div');
            wrapper.style.cssText = `
                position: relative;
                display: inline-block;
                width: 100%;
            `;
            
            // Insert wrapper before input
            input.parentNode.insertBefore(wrapper, input);
            
            // Move input into wrapper
            wrapper.appendChild(input);
            
            // Add button after input
            wrapper.appendChild(toggleBtn);
            
            // Toggle password visibility
            toggleBtn.addEventListener('click', function(e) {
                e.preventDefault();
                if (input.type === 'password') {
                    input.type = 'text';
                    toggleBtn.innerHTML = '👁️‍🗨️';
                    toggleBtn.title = 'Hide Password';
                } else {
                    input.type = 'password';
                    toggleBtn.innerHTML = '👁️';
                    toggleBtn.title = 'Show Password';
                }
            });
        });
    }
    
    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', addPasswordToggleButtons);
    } else {
        addPasswordToggleButtons();
    }
    
    // Also run on any dynamic content load (for Django admin)
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.addedNodes.length) {
                addPasswordToggleButtons();
            }
        });
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: false
    });
})();
