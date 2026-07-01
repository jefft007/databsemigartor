function initDashboardPage() {
  const isadminDashboard = location.pathname.includes('admin_dashboard');
  if (isadminDashboard) {
    if (!requireAdmin()) return;
  } else {
    if (!requireAuth()) return;
  }

  const user = getUserInfo();

  document.title =
    user.role === 'Admin'
      ? 'Admin Dashboard | SQL Migrator'
      : 'Dashboard | SQL Migrator';

  loadSharedComponent('header', () => {
    setProfileSummary();
    bindHeaderActions();
  });

  initSidebar();

  const headerTitle = document.getElementById('page-title');
  if (headerTitle) {
    headerTitle.textContent =
      user.role === 'Admin' ? 'Admin Dashboard' : 'User Dashboard';
  }

  injectQuickActions();
  loadDashboardData(user);
}

async function loadDashboardData(user) {
  try {
    const historyEndpoint = String(user.role).toLowerCase() === 'admin' ? '/history/all' : '/history';
    const [historyRes, statsRes] = await Promise.all([
      apiRequest(historyEndpoint, 'GET'),
      String(user.role).toLowerCase() === 'admin'
        ? apiRequest('/admin/stats', 'GET')
        : apiRequest('/user/stats', 'GET'),
    ]);

    const history = normalizeHistoryResponse(historyRes);
    const stats = statsRes || {};

    renderSummary(history, stats, user);
    renderDashboardCharts(history, stats, user);
    
    if (String(user.role).toLowerCase() === 'admin') {
      renderRecentActivity(stats.recent_migrations || history.slice(0, 5));
    } else {
      renderRecentActivity(stats.recent_migrations || history.slice(0, 5));
    }
    
    // Auto-refresh every 10 seconds
    if (!window._dashboardRefreshInterval) {
      window._dashboardRefreshInterval = setInterval(() => loadDashboardData(user), 10000);
    }
  } catch (error) {
    console.error('Dashboard load failed:', error);
  }
}

function normalizeHistoryResponse(historyRes) {
  if (Array.isArray(historyRes)) return historyRes;
  if (Array.isArray(historyRes?.history)) return historyRes.history;
  if (Array.isArray(historyRes?.result?.history)) return historyRes.result.history;
  if (Array.isArray(historyRes?.data)) return historyRes.data;
  if (Array.isArray(historyRes?.records)) return historyRes.records;
  return [];
}

function getStatus(record) {
  return String(record.status || '').toLowerCase();
}

function renderSummary(history, stats, user) {
  const total = stats.total_migrations || 0;
  const successful = stats.successful_migrations || 0;
  const failed = stats.failed_migrations || 0;
  const reports = stats.total_reports || 0;

  const summaryContainer = document.getElementById('dashboard-summary');
  if (!summaryContainer) return;

  const isAdmin = user && String(user.role).toLowerCase() === 'admin';
  const prefix = isAdmin ? 'Total ' : 'My ';

  let html = `
    <div class="card metric-card"><h3>${prefix}Migrations</h3><strong>${total}</strong></div>
    <div class="card metric-card"><h3>${isAdmin ? '' : 'My '}Successful</h3><strong>${successful}</strong></div>
    <div class="card metric-card"><h3>${isAdmin ? '' : 'My '}Failed</h3><strong>${failed}</strong></div>
    <div class="card metric-card"><h3>${prefix}Reports</h3><strong>${reports}</strong></div>
  `;

  if (isAdmin) {
    const totalUsers = stats.total_users || 0;
    html += `<div class="card metric-card"><h3>Total Users</h3><strong>${totalUsers}</strong></div>`;
  }

  summaryContainer.innerHTML = html;
}


function injectQuickActions() {
  const quickActions = document.getElementById('quick-actions');
  if (!quickActions) return;

  quickActions.innerHTML = `
    <button class="button-primary"
      onclick="window.location.href='../pages/migration.html'">
      New Migration
    </button>

    <button class="button-secondary"
      onclick="window.location.href='../pages/migration_history.html'">
      View History
    </button>
  `;
}

function renderRecentActivity(migrations) {
  const tbody = document.getElementById('admin-recent-activity');
  if (!tbody) return;
  if (!migrations || migrations.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No records found</td></tr>';
    return;
  }
  tbody.innerHTML = migrations.map(m => `
    <tr>
      <td>${m.user_name || 'System'}</td>
      <td>${m.user_email || '-'}</td>
      <td>${m.source_type || '-'} &rarr; ${m.target_type || '-'}</td>
      <td><span class="badge ${m.status && m.status.toLowerCase().includes('success') ? 'badge-success' : 'badge-error'}">${m.status || 'Unknown'}</span></td>
      <td>${m.created_at ? new Date(m.created_at).toLocaleString() : '-'}</td>
    </tr>
  `).join('');
}

function renderDashboardCharts(history, stats, user) {
  if (!window.Chart) return;

  const trends = document.getElementById('migration-trends-chart');
  if (trends) {
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const counts = Array(7).fill(0);
    const now = new Date();

    history.forEach((r) => {
      if (!r.timestamp) return;
      const d = new Date(r.timestamp);
      const diffDays = Math.floor((now - d) / 86400000);
      if (diffDays < 7) {
        counts[6 - diffDays]++;
      }
    });

    const labels = Array.from({ length: 7 }, (_, i) => {
      const d = new Date(now);
      d.setDate(d.getDate() - (6 - i));
      return days[d.getDay()];
    });

    new Chart(trends, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Migrations',
            data: counts,
            borderColor: '#8B7CFF',
            backgroundColor: 'rgba(139,124,255,0.14)',
            tension: 0.35,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#9CA3AF' } },
          y: {
            grid: { color: 'rgba(255,255,255,0.08)' },
            ticks: { color: '#9CA3AF' },
          },
        },
      },
    });
  }

  const activity = document.getElementById('user-activity-chart');
  if (activity) {
    const isAdmin = user && String(user.role).toLowerCase() === 'admin';
    const totalUsers = isAdmin ? Number(stats.total_users || 0) : null;
    const totalMigrations = stats.total_migrations || 0;
    const totalReports = stats.total_reports || 0;

    const labels = isAdmin ? ['Users', 'Migrations', 'Reports'] : ['Migrations', 'Reports'];
    const data = isAdmin ? [totalUsers, totalMigrations, totalReports] : [totalMigrations, totalReports];
    const backgroundColor = isAdmin ? ['#6366F1', '#22C55E', '#F59E0B'] : ['#22C55E', '#F59E0B'];

    new Chart(activity, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Total',
            data: data,
            backgroundColor: backgroundColor,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: '#9CA3AF' } },
          y: {
            grid: { color: 'rgba(255,255,255,0.08)' },
            ticks: { color: '#9CA3AF' },
          },
        },
      },
    });
  }

  const usage = document.getElementById('database-usage-chart');
  if (usage) {
    const dbCounts = {
      MySQL: 0,
      PostgreSQL: 0,
      Oracle: 0,
      SQLite: 0,
      Other: 0,
    };

    history.forEach((r) => {
      const src = `${r.source_db || ''} ${r.target_db || ''}`.toLowerCase();

      if (src.includes('mysql')) dbCounts.MySQL++;
      else if (src.includes('postgres')) dbCounts.PostgreSQL++;
      else if (src.includes('oracle')) dbCounts.Oracle++;
      else if (src.includes('sqlite') || src.includes('.db')) dbCounts.SQLite++;
      else dbCounts.Other++;
    });

    const labels = Object.keys(dbCounts).filter((k) => dbCounts[k] > 0);
    const data = labels.map((k) => dbCounts[k]);

    new Chart(usage, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [
          {
            data,
            backgroundColor: [
              '#8B7CFF',
              '#22C55E',
              '#F59E0B',
              '#EF4444',
              '#60A5FA',
            ],
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { color: '#9CA3AF' },
          },
        },
      },
    });
  }
}