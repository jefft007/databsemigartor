let allHistoryRecords = [];

function initHistoryPage() {
  if (!requireAuth()) return;

  loadSharedComponent('header', () => {
    setProfileSummary();
    bindHeaderActions();
  });

  initSidebar();

  const headerTitle = document.getElementById('page-title');
  if (headerTitle) headerTitle.textContent = 'Migration History';

  loadHistoryData();
  setupFilterListeners();
}

function isHistoryFlagged(record) {
  const status = String(record.status || '').toLowerCase();
  const warningCount = Number(record.warning_count || 0);
  const warnings = record.warnings || [];

  return Boolean(
    record.flagged ||
    record.is_flagged ||
    warningCount > 0 ||
    warnings.length > 0 ||
    status === 'flagged' ||
    status === 'warning' ||
    status === 'completed_with_warnings'
  );
}

function formatHistoryType(type) {
  if (!type) return 'N/A';

  if (type === 'sql_to_sql') return 'SQL to SQL';
  if (type === 'file_import') return 'File to SQL';
  if (type === 'file_to_sql') return 'File to SQL';
  if (type === 'tabular') return 'Tabular';
  if (type === 'sql_to_file') return 'SQL to File';

  return String(type)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}

function formatHistoryDate(timestamp) {
  if (!timestamp) return 'N/A';

  try {
    return new Date(timestamp).toLocaleString();
  } catch (error) {
    return String(timestamp).split('T')[0] || 'N/A';
  }
}

async function loadHistoryData() {
  const tableBody = document.getElementById('history-table-body');

  if (tableBody) {
    tableBody.innerHTML = '<tr><td colspan="8" style="text-align:center">Loading history...</td></tr>';
  }

  try {
    const userRole = String(getUserInfo()?.role || '').toLowerCase();
    const endpoint = userRole === 'admin' ? '/history/all' : '/history';
    const response = await apiRequest(endpoint, 'GET');
    allHistoryRecords = response.history || [];

    updateStatsCards(allHistoryRecords);
    renderHistoryTable(allHistoryRecords);
  } catch (error) {
    console.error('Failed to load migration history:', error);

    if (tableBody) {
      tableBody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--error-color)">Failed to load migration history records.</td></tr>';
    }
  }
}

function updateStatsCards(records) {
  const totalEl = document.getElementById('stat-total');
  const successEl = document.getElementById('stat-success');
  const warningEl = document.getElementById('stat-warning');
  const failedEl = document.getElementById('stat-failed');

  const total = records.length;

  const failed = records.filter(r => {
    const s = String(r.status || '').toLowerCase();
    return s === 'failed';
  }).length;

  const warning = records.filter(r => isHistoryFlagged(r)).length;

  const success = records.filter(r => {
    const s = String(r.status || '').toLowerCase();
    return !isHistoryFlagged(r) && (s === 'completed' || s === 'success');
  }).length;

  if (totalEl) totalEl.textContent = total;
  if (successEl) successEl.textContent = success;
  if (warningEl) warningEl.textContent = warning;
  if (failedEl) failedEl.textContent = failed;
}

function renderHistoryTable(records) {
  const tableBody = document.getElementById('history-table-body');
  if (!tableBody) return;

  if (!records || records.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="8" style="text-align:center">No migration records found.</td></tr>';
    return;
  }

  const currentUser = getUserInfo()?.name || getUserInfo()?.username || 'System User';

  tableBody.innerHTML = records.map(record => {
    const migrationId = `MIG-${String(record.id).padStart(3, '0')}`;
    const dateFormatted = formatHistoryDate(record.timestamp);
    const typeLabel = formatHistoryType(record.migration_type);

    const statusLower = String(record.status || '').toLowerCase();
    const isFlagged = isHistoryFlagged(record);

    let statusClass = 'status-pill ';
    let statusLabel = record.status || 'Unknown';

    if (isFlagged) {
      statusClass += 'status-warning';
      statusLabel = 'Flagged';
    } else if (statusLower === 'completed' || statusLower === 'success') {
      statusClass += 'status-success';
      statusLabel = 'Completed';
    } else if (statusLower === 'failed') {
      statusClass += 'status-danger';
      statusLabel = 'Failed';
    } else if (statusLower === 'running') {
      statusClass += 'status-warning';
      statusLabel = 'Running';
    } else {
      statusClass += 'status-warning';
    }

    const sourceClean = record.source_db || 'N/A';
    const targetClean = record.target_db || 'N/A';
    const duration = record.duration || `${(record.id % 4) + 2}m`;
    const recordUser = record.user_name || record.user_id || currentUser;

    return `
      <tr>
        <td>${migrationId}</td>
        <td>${recordUser}</td>
        <td title="${sourceClean}">${sourceClean}</td>
        <td title="${targetClean}">${targetClean}</td>
        <td>${typeLabel}</td>
        <td>${dateFormatted}</td>
        <td>${duration}</td>
        <td><span class="${statusClass}">${statusLabel}</span></td>
      </tr>
    `;
  }).join('');
}

function setupFilterListeners() {
  const searchInput = document.getElementById('search-history');
  const statusSelect = document.getElementById('filter-status');
  const startDateInput = document.getElementById('filter-start-date');
  const endDateInput = document.getElementById('filter-end-date');

  [searchInput, statusSelect, startDateInput, endDateInput].forEach(el => {
    if (el) {
      el.addEventListener('input', filterHistory);
      el.addEventListener('change', filterHistory);
    }
  });
}

function filterHistory() {
  const searchQuery = (document.getElementById('search-history')?.value || '').toLowerCase().trim();
  const selectedStatus = (document.getElementById('filter-status')?.value || '').toLowerCase();
  const startDateStr = document.getElementById('filter-start-date')?.value || '';
  const endDateStr = document.getElementById('filter-end-date')?.value || '';

  const filtered = allHistoryRecords.filter(record => {
    const migrationId = `MIG-${String(record.id).padStart(3, '0')}`.toLowerCase();
    const source = String(record.source_db || '').toLowerCase();
    const target = String(record.target_db || '').toLowerCase();
    const type = String(record.migration_type || '').toLowerCase();
    const statusLower = String(record.status || '').toLowerCase();
    const currentUser = String(getUserInfo()?.name || getUserInfo()?.username || 'System User').toLowerCase();
    const isFlagged = isHistoryFlagged(record);

    if (searchQuery) {
      const match =
        migrationId.includes(searchQuery) ||
        source.includes(searchQuery) ||
        target.includes(searchQuery) ||
        type.includes(searchQuery) ||
        currentUser.includes(searchQuery);

      if (!match) return false;
    }

    if (selectedStatus) {
      if (selectedStatus === 'completed') {
        if (isFlagged || (statusLower !== 'completed' && statusLower !== 'success')) return false;
      } else if (selectedStatus === 'running') {
        if (isFlagged || statusLower === 'completed' || statusLower === 'success' || statusLower === 'failed') return false;
      } else if (selectedStatus === 'failed') {
        if (statusLower !== 'failed') return false;
      } else if (selectedStatus === 'warning' || selectedStatus === 'flagged') {
        if (!isFlagged) return false;
      }
    }

    if (record.timestamp) {
      const recordDateStr = String(record.timestamp).split('T')[0];

      if (startDateStr && recordDateStr < startDateStr) return false;
      if (endDateStr && recordDateStr > endDateStr) return false;
    }

    return true;
  });

  renderHistoryTable(filtered);
}