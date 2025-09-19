class UserModel:
    def __init__(self):
        self.admin_password = "admin123"  # Replace with hashed and secure storage in production
    
    def validate_admin_password(self, password):
        return password == self.admin_password
    
    def get_user_by_role(self, role):
        return {
            'role': role,
            'permissions': self.get_permissions_by_role(role)
        }
    
    def get_permissions_by_role(self, role):
        permissions = {
            'Student': ['view_evaluations', 'submit_evaluations'],
            'Admin': ['view_evaluations', 'submit_evaluations', 'manage_users', 'view_reports', 'system_settings']
        }
        return permissions.get(role, [])
