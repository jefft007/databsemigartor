function initUsersPage() {
  if (!requireAdmin()) return;
  loadSharedComponent('header', () => {
    setProfileSummary();
    bindHeaderActions();
  });
  initSidebar();
  const headerTitle = document.getElementById('page-title');
  if (headerTitle) headerTitle.textContent = 'Users';
  
  injectUserModal();
  
  // Add User button next to header
  const headerBar = document.querySelector('.header-bar');
  if (headerBar && !document.getElementById('btn-add-user')) {
    const btn = document.createElement('button');
    btn.id = 'btn-add-user';
    btn.className = 'button-primary';
    btn.textContent = '+ Add User';
    btn.onclick = () => openUserModal();
    headerBar.appendChild(btn);
  }

  renderUserTable();
}

let allUsers = [];

async function renderUserTable() {
  try {
    const response = await apiRequest('/admin/users', 'GET');
    allUsers = response.users || [];
    const tableBody = document.getElementById('users-table-body');
    if (!tableBody) return;
    
    if (allUsers.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center;">No records found</td></tr>';
      renderUserMetrics(allUsers);
      return;
    }
    
    tableBody.innerHTML = allUsers
      .map((user) => {
        const isActive = user.is_active !== false; // handle boolean
        return `
        <tr>
          <td>${user.username || user.fullname || ''}</td>
          <td>${user.email}</td>
          <td><span style="text-transform: capitalize;">${user.role}</span></td>
          <td>
            <span class="badge ${isActive ? 'badge-success' : 'badge-danger'}" style="padding: 4px 8px; border-radius: 12px; font-size: 0.85em; background: ${isActive ? '#d4edda' : '#f8d7da'}; color: ${isActive ? '#155724' : '#721c24'};">
              ${isActive ? 'Active' : 'Inactive'}
            </span>
          </td>
          <td>-</td>
          <td>${user.last_login ? new Date(user.last_login).toLocaleString() : 'Never'}</td>
          <td>
            <button class="button-secondary" onclick="openUserModal(${user.id})">Edit</button>
            <button class="button-danger" style="background:#dc3545; color:white; border:none; padding:4px 8px; border-radius:4px; cursor:pointer;" onclick="deleteUser(${user.id})">Delete</button>
          </td>
        </tr>
      `})
      .join('');
      
    renderUserMetrics(allUsers);
  } catch (err) {
    console.error('Failed to load users', err);
  }
}

function renderUserMetrics(users) {
  const stats = {
    totalUsers: users ? users.length : 0,
    activeUsers: users ? users.filter(u => u.is_active !== false).length : 0,
    adminUsers: users ? users.filter(u => String(u.role).toLowerCase() === 'admin').length : 0,
    inactiveUsers: users ? users.filter(u => u.is_active === false).length : 0,
  };
  const container = document.getElementById('users-metrics');
  if (!container) return;
  container.innerHTML = `
    <div class="card metric-card"><h3>Total Users</h3><strong>${stats.totalUsers}</strong></div>
    <div class="card metric-card"><h3>Active Users</h3><strong>${stats.activeUsers}</strong></div>
    <div class="card metric-card"><h3>Admin Users</h3><strong>${stats.adminUsers}</strong></div>
    <div class="card metric-card"><h3>Inactive Users</h3><strong>${stats.inactiveUsers}</strong></div>
  `;
}

function injectUserModal() {
  if (document.getElementById('user-modal')) return;

  const modal = document.createElement('div');
  modal.id = 'user-modal';
  modal.className = 'report-modal';
  modal.style.display = 'none';

  modal.innerHTML = `
    <div class="report-modal-backdrop" onclick="closeUserModal()"></div>
    <div class="report-modal-content" style="max-width: 500px;">
      <div class="report-modal-header">
        <h2 id="user-modal-title">Add User</h2>
        <button type="button" onclick="closeUserModal()">×</button>
      </div>
      <div class="report-modal-body">
        <form id="user-form" style="display: flex; flex-direction: column; gap: 1rem;">
          <input type="hidden" id="user-id">
          
          <div style="display: flex; flex-direction: column; gap: 0.5rem;">
            <label for="user-name">Name</label>
            <input type="text" id="user-name" class="input-field" required>
          </div>
          
          <div style="display: flex; flex-direction: column; gap: 0.5rem;">
            <label for="user-email">Email</label>
            <input type="email" id="user-email" class="input-field" required>
          </div>
          
          <div style="display: flex; flex-direction: column; gap: 0.5rem;">
            <label for="user-password">Password</label>
            <input type="password" id="user-password" class="input-field" placeholder="Leave blank to keep unchanged">
          </div>
          
          <div style="display: flex; flex-direction: column; gap: 0.5rem;">
            <label for="user-role">Role</label>
            <select id="user-role" class="input-field">
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          
          <div style="display: flex; align-items: center; gap: 0.5rem; margin-top: 0.5rem;">
            <input type="checkbox" id="user-active" checked>
            <label for="user-active" style="font-weight: 500;">Account Active</label>
          </div>
        </form>
      </div>
      <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.12); display: flex; justify-content: flex-end; gap: 10px;">
        <button class="button-secondary" onclick="closeUserModal()">Cancel</button>
        <button class="button-primary" onclick="saveUser()">Save</button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);
}

function openUserModal(userId = null) {
  const modal = document.getElementById('user-modal');
  const title = document.getElementById('user-modal-title');
  const form = document.getElementById('user-form');
  
  if (!modal || !title || !form) return;
  
  form.reset();
  document.getElementById('user-id').value = '';
  document.getElementById('user-password').required = true;
  document.getElementById('user-password').placeholder = 'Required';
  
  if (userId) {
    const user = allUsers.find(u => u.id === userId);
    if (user) {
      title.textContent = 'Edit User';
      document.getElementById('user-id').value = user.id;
      document.getElementById('user-name').value = user.username || user.fullname || '';
      document.getElementById('user-email').value = user.email || '';
      document.getElementById('user-role').value = user.role || 'user';
      document.getElementById('user-active').checked = user.is_active !== false;
      document.getElementById('user-password').required = false;
      document.getElementById('user-password').placeholder = 'Leave blank to keep unchanged';
    }
  } else {
    title.textContent = 'Add User';
  }
  
  modal.style.display = 'flex';
  modal.style.position = 'fixed';
  modal.style.top = '0';
  modal.style.left = '0';
  modal.style.width = '100%';
  modal.style.height = '100%';
  modal.style.background = 'rgba(0,0,0,0.6)';
  modal.style.zIndex = '9999';
  modal.style.alignItems = 'center';
  modal.style.justifyContent = 'center';
}

function closeUserModal() {
  const modal = document.getElementById('user-modal');
  if (modal) modal.style.display = 'none';
}

async function saveUser() {
  const id = document.getElementById('user-id').value;
  const username = document.getElementById('user-name').value;
  const email = document.getElementById('user-email').value;
  const password = document.getElementById('user-password').value;
  const role = document.getElementById('user-role').value;
  const is_active = document.getElementById('user-active').checked;
  
  if (!username || !email) {
    alert('Name and Email are required.');
    return;
  }
  
  if (!id && !password) {
    alert('Password is required for new users.');
    return;
  }
  
  const payload = { username, email, role, is_active };
  if (password) payload.password = password;
  
  try {
    if (id) {
      await apiRequest(`/admin/user/${id}`, 'PUT', payload);
    } else {
      await apiRequest(`/admin/users`, 'POST', payload);
    }
    closeUserModal();
    renderUserTable();
  } catch (err) {
    console.error(err);
    alert('Failed to save user.');
  }
}

async function deleteUser(userId) {
  if (!confirm('Are you sure you want to delete this user?')) return;
  try {
    await apiRequest(`/admin/user/${userId}`, 'DELETE');
    renderUserTable();
  } catch (err) {
    console.error(err);
    alert('Failed to delete user.');
  }
}
