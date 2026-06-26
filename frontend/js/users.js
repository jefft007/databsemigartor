function initUsersPage() {
  if (!requireAdmin()) return;
  loadSharedComponent('header', () => {
    setProfileSummary();
    bindHeaderActions();
  });
  initSidebar();
  const headerTitle = document.getElementById('page-title');
  if (headerTitle) headerTitle.textContent = 'Users';
  renderUserMetrics();
  renderUserTable();
}

async function renderUserTable() {
  try {
    const response = await apiRequest('/admin/users', 'GET');
    const rows = response.users || [];
    const tableBody = document.getElementById('users-table-body');
    if (!tableBody) return;
    
    if (rows.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center;">No records found</td></tr>';
      renderUserMetrics(rows);
      return;
    }
    
    tableBody.innerHTML = rows
      .map((user) => `
        <tr>
          <td>${user.username}</td>
          <td>${user.email}</td>
          <td>${user.role}</td>
          <td><span class="badge badge-success">Active</span></td>
          <td>-</td>
          <td>${new Date(user.created_at).toLocaleDateString()}</td>
          <td><button class="button-secondary">View</button></td>
        </tr>
      `)
      .join('');
      
    renderUserMetrics(rows);
  } catch (err) {
    console.error('Failed to load users', err);
  }
}

function renderUserMetrics(users) {
  const stats = {
    totalUsers: users ? users.length : 0,
    activeUsers: users ? users.length : 0,
    adminUsers: users ? users.filter(u => String(u.role).toLowerCase() === 'admin').length : 0,
    inactiveUsers: 0,
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
