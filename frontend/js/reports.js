async function loadReportHistory() {
  const userRole = String(getUserInfo()?.role || '').toLowerCase();
  const endpoint = userRole === 'admin' ? '/reports/all' : '/reports';
  return await apiRequest(endpoint, 'GET');
}

const _historyCache = {};

function initReportsPage() {
  if (!requireAuth()) return;

  loadSharedComponent('header', () => {
    setProfileSummary();
    bindHeaderActions();
  });

  initSidebar();

  const headerTitle = document.getElementById('page-title');
  if (headerTitle) headerTitle.textContent = 'Reports';

  injectReportModal();
  renderReportSummary();
  renderReportTable();

  const refreshBtn = document.getElementById('refresh-reports');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      refreshBtn.textContent = 'Refreshing...';
      refreshBtn.disabled = true;

      try {
        await renderReportSummary();
        await renderReportTable();
        showNotification('Reports refreshed successfully.', 'success');
      } catch (e) {
        showNotification('Failed to refresh reports.', 'error');
      } finally {
        refreshBtn.textContent = 'Refresh';
        refreshBtn.disabled = false;
      }
    });
  }
}

function normalizeType(type) {
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

function parseSummary(record) {
  if (!record) return {};

  try {
    if (typeof record.report_summary === 'string') {
      return JSON.parse(record.report_summary);
    }

    if (typeof record.report_summary === 'object' && record.report_summary !== null) {
      return record.report_summary;
    }
  } catch (error) {
    console.warn('Unable to parse report_summary:', error);
  }

  return {};
}

function isRecordRejected(record) {
  return String(record.status || '').toLowerCase() === 'rejected';
}

function isRecordFlagged(record) {
  const summary = parseSummary(record);
  const status = String(record.status || '').toLowerCase();
  const warnings = summary.warnings || record.warnings || [];
  const warningCount = Number(summary.warning_count || record.warning_count || warnings.length || 0);

  return Boolean(
    record.flagged ||
    record.is_flagged ||
    summary.flagged ||
    warningCount > 0 ||
    status === 'flagged' ||
    status === 'warning' ||
    status === 'completed_with_warnings' ||
    status === 'failed'
  );
}

function getStatusLabel(record) {
  const status = String(record.status || '').toLowerCase();

  if (isRecordRejected(record)) return 'Rejected';
  if (isRecordFlagged(record)) return 'Flagged';
  if (status === 'completed' || status === 'success') return 'completed';
  if (status === 'failed') return 'failed';
  if (status === 'running') return 'running';

  return record.status || 'Unknown';
}

function getStatusClass(record) {
  const status = String(record.status || '').toLowerCase();

  if (isRecordRejected(record)) return 'status-badge status-danger';
  if (isRecordFlagged(record)) return 'status-badge status-warning';
  if (status === 'completed' || status === 'success') return 'status-badge status-success';
  if (status === 'failed') return 'status-badge status-danger';
  if (status === 'running') return 'status-badge status-warning';

  return 'status-badge status-warning';
}

function formatDate(timestamp) {
  if (!timestamp || timestamp === 'N/A') return 'N/A';

  try {
    return new Date(timestamp).toLocaleString();
  } catch (error) {
    return timestamp;
  }
}

async function renderReportSummary() {
  try {
    const response = await loadReportHistory();
    const allRecords = response.reports || response.history || response.data?.reports || response.data?.history || [];

    const totalEl = document.getElementById('report-total');
    const flaggedEl = document.getElementById('report-flagged');
    const completedEl = document.getElementById('report-completed');
    const failedEl = document.getElementById('report-failed');

    const total = allRecords.length;
    const flagged = allRecords.filter(isRecordFlagged).length;
    const failed = allRecords.filter(r => String(r.status || '').toLowerCase() === 'failed').length;

    const completed = allRecords.filter(r => {
      const status = String(r.status || '').toLowerCase();
      return !isRecordFlagged(r) && (status === 'completed' || status === 'success' || status === 'generated');
    }).length;

    if (totalEl) totalEl.textContent = total;
    if (flaggedEl) flaggedEl.textContent = flagged;
    if (completedEl) completedEl.textContent = completed;
    if (failedEl) failedEl.textContent = failed;
  } catch (error) {
    console.error('Failed to render report summary:', error);
  }
}

async function renderReportTable() {
  const tableBody = document.getElementById('reports-table-body');
  if (!tableBody) return;

  tableBody.innerHTML = '<tr><td colspan="6" style="text-align:center">Loading reports...</td></tr>';

  try {
    const response = await loadReportHistory();
    const reports = response.reports || response.history || response.data?.reports || response.data?.history || [];

    Object.keys(_historyCache).forEach(key => delete _historyCache[key]);

    if (reports.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="6" style="text-align:center">No reports found.</td></tr>';
      return;
    }

    const currentUser = getUserInfo()?.name || getUserInfo()?.username || 'System';

    reports.forEach(report => {
      const cacheKey = String(report.id);
      report._cacheKey = cacheKey;
      _historyCache[cacheKey] = report;
    });

    tableBody.innerHTML = reports.map(report => {
      const reportName = report.report_name || `Migration Report #${report.id}`;
      const typeLabel = normalizeType(report.type || report.migration_type || 'Migration Report');
      const generatedBy = report.generated_by || currentUser;
      const dateFormatted = formatDate(report.date || report.timestamp || report.created_at || 'N/A');
      const statusLabel = report.status || 'Generated';

      return `
        <tr>
          <td>${reportName}</td>
          <td>${typeLabel}</td>
          <td>${generatedBy}</td>
          <td>${dateFormatted}</td>
          <td>
            <span class="${getStatusClass(report)}">${statusLabel}</span>
          </td>
          <td class="report-actions">
  <button
    class="btn-view"
    type="button"
    onclick="window.viewReport('${report._cacheKey}')">
    View
  </button>

  <button
    class="btn-delete"
    type="button"
    onclick="window.deleteReport('${report.id}')">
    Delete
  </button>
</td>
        </tr>
      `;
    }).join('');
  } catch (error) {
    console.error('Failed to load reports:', error);
    tableBody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:red">Failed to load reports.</td></tr>';
  }
}

async function deleteReport(reportId) {
  const confirmed = confirm('Are you sure you want to delete this report?');
  if (!confirmed) return;

  try {
    await apiRequest(`/reports/${reportId}`, 'DELETE');

    showNotification?.('Report deleted successfully.', 'success');

    await renderReportSummary();
    await renderReportTable();
  } catch (error) {
    console.error('Failed to delete report:', error);
    showNotification?.('Failed to delete report.', 'error');
    alert('Failed to delete report.');
  }
}

function viewReport(recordId) {
  const record = _historyCache[String(recordId)];

  if (!record) {
    alert('Report data not found. Please refresh reports.');
    return;
  }

  openReportModal(record);
}

function injectReportModal() {
  if (document.getElementById('report-modal')) return;

  const modal = document.createElement('div');
  modal.id = 'report-modal';
  modal.className = 'report-modal';
  modal.style.display = 'none';

  modal.innerHTML = `
    <div class="report-modal-backdrop" onclick="window.closeReportModal()"></div>
    <div class="report-modal-content">
      <div class="report-modal-header">
        <h2>Migration Report Details</h2>
        <button type="button" onclick="window.closeReportModal()">×</button>
      </div>
      <div id="report-modal-body" class="report-modal-body"></div>
      <div id="report-modal-footer" style="margin-top: 24px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.12); display: flex; justify-content: flex-end;">
      </div>
    </div>
  `;

  document.body.appendChild(modal);
}

function closeReportModal() {
  const modal = document.getElementById('report-modal');
  if (modal) modal.style.display = 'none';
}

function openReportModal(record) {
  const summary = parseSummary(record);

  const warnings = summary.warnings || record.warnings || [];
  const warningCount = Number(summary.warning_count || record.warning_count || warnings.length || 0);

  const summaryList = Array.isArray(summary.summary) ? summary.summary : [];

  const totalRecords =
    summary.rows_imported ||
    summary.total_records ||
    summaryList.reduce((sum, item) => sum + Number(item.rows_transferred || 0), 0) ||
    0;

  const failedCount =
    summary.failed_count ||
    summaryList.reduce((sum, item) => sum + Number(item.rows_failed || 0), 0) ||
    0;

  const successCount =
    summary.success_count ||
    summaryList.reduce((sum, item) => sum + Number(item.rows_transferred || 0), 0) ||
    totalRecords;

  const status = getStatusLabel(record);

  let flagReason;
  if (isRecordRejected(record)) {
    flagReason = `This import was blocked before anything was written to the database. ${warningCount} row(s) had missing or invalid values that must be corrected, then the file can be re-uploaded.`;
  } else if (isRecordFlagged(record)) {
    flagReason = `This report is flagged because ${warningCount} warning record(s) were found.`;
  } else {
    flagReason = 'This report is completed because no warning, failed, or empty/null records were found.';
  }

  const body = document.getElementById('report-modal-body');
  if (!body) return;

  body.innerHTML = `
    <div class="report-detail-grid">
      <p><strong>Migration ID:</strong> MIG-${String(record.id).padStart(3, '0')}</p>
      <p><strong>Source DB:</strong> ${record.source_db || 'N/A'}</p>
      <p><strong>Target DB:</strong> ${record.target_db || 'N/A'}</p>
      <p><strong>Type:</strong> ${normalizeType(record.migration_type)}</p>
      <p><strong>Status:</strong> ${status}</p>
      ${
        isRecordRejected(record)
          ? `<p><strong>Records Processed:</strong> 0 (blocked before import)</p>`
          : `
            <p><strong>Total Records:</strong> ${totalRecords}</p>
            <p><strong>Success Count:</strong> ${successCount}</p>
            <p><strong>Failed Count:</strong> ${failedCount}</p>
          `
      }
      <p><strong>Warning / Flagged Records:</strong> ${warningCount}</p>
    </div>

    <h3>Why this status?</h3>
    <p>${flagReason}</p>

    <h3>Warning Details</h3>
    ${
      warnings.length
        ? warnings.map(w => `
          <div class="report-warning-item">
            <strong>Row:</strong> ${w.row_index || w.original_index || '-'} |
            <strong>Column:</strong> ${w.column || '-'} |
            <strong>Reason:</strong> ${w.reason || w.error || 'Warning found'}
          </div>
        `).join('')
        : '<p>No warning records found.</p>'
    }

    <h3>Error Details</h3>
    ${
      record.errors
        ? `<p>${record.errors}</p>`
        : '<p>No errors found.</p>'
    }
  `;

  const footer = document.getElementById('report-modal-footer');
  if (footer) {
    footer.innerHTML = `
      <button class="button-primary" onclick="window.downloadReportDetails('${record.id}')">
        Download Report
      </button>
    `;
  }

  const modal = document.getElementById('report-modal');

  if (!modal) {
    alert('Report modal not found.');
    return;
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

function downloadReportDetails(reportId) {
  const record = _historyCache[String(reportId)];
  if (!record) {
    alert('Unable to download report.');
    return;
  }

  const summary = parseSummary(record);
  const warnings = summary.warnings || record.warnings || [];
  const summaryList = Array.isArray(summary.summary) ? summary.summary : [];

  const totalRecords =
    summary.rows_imported ||
    summary.total_records ||
    summaryList.reduce((sum, item) => sum + Number(item.rows_transferred || 0), 0) ||
    0;

  const failedCount =
    summary.failed_count ||
    summaryList.reduce((sum, item) => sum + Number(item.rows_failed || 0), 0) ||
    0;

  const successCount =
    summary.success_count ||
    summaryList.reduce((sum, item) => sum + Number(item.rows_transferred || 0), 0) ||
    totalRecords;

  const warningCount = Number(summary.warning_count || record.warning_count || warnings.length || 0);

  const status = getStatusLabel(record);
  const typeLabel = normalizeType(record.type || record.migration_type || 'Migration Report');
  const dateFormatted = formatDate(record.date || record.timestamp || record.created_at || 'N/A');

  let content = `====================================================\n`;
  content += `               MIGRATION REPORT                     \n`;
  content += `====================================================\n\n`;

  content += `Report ID: ${record.id}\n`;
  content += `Migration ID: MIG-${String(record.id).padStart(3, '0')}\n`;
  content += `Source Database: ${record.source_db || 'N/A'}\n`;
  content += `Target Database: ${record.target_db || 'N/A'}\n`;
  content += `Migration Type: ${typeLabel}\n`;
  content += `Status: ${status}\n`;
  content += `Date & Time: ${dateFormatted}\n\n`;

  content += `--- Summary ---\n`;
  content += `Total Records: ${totalRecords}\n`;
  content += `Success Count: ${successCount}\n`;
  content += `Failed Count: ${failedCount}\n`;
  content += `Warning/Flagged Count: ${warningCount}\n\n`;

  if (warnings.length > 0) {
    content += `--- Warning Details ---\n`;
    warnings.forEach(w => {
      content += `- Row: ${w.row_index || w.original_index || '-'} | Column: ${w.column || '-'} | Reason: ${w.reason || w.error || 'Warning found'}\n`;
    });
    content += `\n`;
  }

  if (record.errors) {
    content += `--- Error Details ---\n`;
    content += `${record.errors}\n\n`;
  }

  const blob = new Blob([content], { type: 'text/plain' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.style.display = 'none';
  a.href = url;
  a.download = `migration-report-${record.id}.txt`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  a.remove();
}

window.viewReport = viewReport;
window.deleteReport = deleteReport;
window.closeReportModal = closeReportModal;
window.openReportModal = openReportModal;
window.downloadReportDetails = downloadReportDetails;