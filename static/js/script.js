document.addEventListener('DOMContentLoaded', function() {
    const roleSelect = document.getElementById('role');
    const passwordField = document.getElementById('passwordField');
    const loginForm = document.getElementById('loginForm');

    // Show/hide password field based on role selection
    roleSelect.addEventListener('change', function() {
        if (this.value === 'Admin') {
            passwordField.classList.add('show');
            document.getElementById('password').required = true;
        } else {
            passwordField.classList.remove('show');
            document.getElementById('password').required = false;
            document.getElementById('password').value = '';
        }
    });

    // Form validation
    loginForm.addEventListener('submit', function(e) {
        const role = roleSelect.value;
        const password = document.getElementById('password').value;

        if (!role || role === '--Select role--') {
            e.preventDefault();
            showAlert('Please select a role', 'error');
            return;
        }

        if (role === 'Admin' && !password.trim()) {
            e.preventDefault();
            showAlert('Please enter admin password', 'error');
            return;
        }
    });

    // Show alert function
    function showAlert(message, type) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type}`;
        alertDiv.textContent = message;
        
        const flashContainer = document.querySelector('.flash-messages') || createFlashContainer();
        flashContainer.appendChild(alertDiv);
        
        setTimeout(() => {
            alertDiv.remove();
        }, 5000);
    }

    function createFlashContainer() {
        const container = document.createElement('div');
        container.className = 'flash-messages';
        const form = document.querySelector('.login-card');
        form.insertBefore(container, form.firstChild);
        return container;
    }
});
