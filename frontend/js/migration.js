function initMigrationPage() {
  if (!requireAuth()) return;
  loadSharedComponent('header', () => {
    setProfileSummary();
    bindHeaderActions();
  });
  initSidebar();
  const headerTitle = document.getElementById('page-title');
  if (headerTitle) headerTitle.textContent = 'Migration';

  const tabs = document.querySelectorAll('.migration-tab');
  const panels = document.querySelectorAll('.migration-panel');
  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      tabs.forEach((item) => item.classList.remove('active'));
      panels.forEach((panel) => panel.classList.add('hidden'));
      tab.classList.add('active');
      document.getElementById(tab.dataset.target).classList.remove('hidden');
    });
  });

  // NOTE: Do NOT call injectDatabaseOptions here — the HTML already has
  // the correct <option> values (mysql, postgres, sqlite, etc.) that match
  // what the backend connection_manager expects.

  const sqlToSqlForm = document.getElementById('sql-to-sql-form');
  const sqlToFileForm = document.getElementById('sql-to-file-form');
  const fileToSqlForm = document.getElementById('file-to-sql-form');

  // --- SQL to SQL ---
  if (sqlToSqlForm) {
    sqlToSqlForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      resetProgress();
      appendLog('Collecting connection details...');

      const payload = {
        source_db_type: getVal('source-db-type'),
        source_host: getVal('source-host'),
        source_port: getVal('source-port'),
        source_username: getVal('source-username'),
        source_password: getVal('source-password'),
        source_database: getVal('source-db-name'),
        target_db_type: getVal('target-db-type'),
        target_host: getVal('target-host'),
        target_port: getVal('target-port'),
        target_username: getVal('target-username'),
        target_password: getVal('target-password'),
        target_database: getVal('target-db-name'),
        tables: getVal('sql-tables') ? getVal('sql-tables').split(',').map(s => s.trim()) : [],
      };

      appendLog(`Connecting to source (${payload.source_db_type}://${payload.source_host})...`);
      const progressSim = startProgressSimulation();
      const response = await apiRequest('/migration/sql-to-sql', 'POST', payload);

const flagged = response.flagged || response.warning_count > 0;

showMigrationResult(
  flagged
    ? `Migration completed with warnings. ${response.warning_count || 0} flagged record(s) found.`
    : 'Migration completed successfully.',
  flagged ? 'warning' : 'success'
);
    });
  }

  // --- SQL to File ---
  if (sqlToFileForm) {
    sqlToFileForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      resetProgress();
      appendLog('Preparing export...');

      const payload = {
        source_db_type: getVal('export-db-type'),
        source_host: getVal('export-host'),
        source_port: getVal('export-port'),
        source_username: getVal('export-username'),
        source_password: getVal('export-password'),
        source_database: getVal('export-db-name'),
        source_table: getVal('export-table-name'),
        export_format: getVal('export-format'),
        columns: getVal('export-columns') ? getVal('export-columns').split(',').map(s => s.trim()) : [],
      };

      appendLog(`Exporting from ${payload.source_db_type}...`);
      const progressSim = startProgressSimulation();
      const response = await apiRequest('/export/sql-to-file', 'POST', payload);
      alert(JSON.stringify(response, null, 2));
console.log(response);
handleMigrationResponse(response, progressSim);

const downloadArea = document.getElementById("download-area");

const filename = response?.filename || response?.result?.filename;
const downloadUrl = response?.download_url || response?.result?.download_url;

if (downloadArea && (filename || downloadUrl)) {
  const finalUrl = downloadUrl
    ? `${API_BASE_URL}${downloadUrl}`
    : `${API_BASE_URL}/export/download/${filename}`;

  downloadArea.innerHTML = `
    <a href="${finalUrl}" target="_blank" download
       style="display:inline-block;margin-top:20px;padding:14px 24px;background:#16a34a;color:white;text-decoration:none;border-radius:8px;font-weight:700;">
      ⬇️ Download ${filename || "File"}
    </a>
  `;
}

setTimeout(() => {
  const logs = document.getElementById('migration-logs');
  if (!logs) return;

  const filename =
    response?.filename ||
    response?.result?.filename;

  const downloadPath =
    response?.download_url ||
    response?.result?.download_url ||
    (filename ? `/export/download/${filename}` : "");

  if (!downloadPath) return;

  const finalUrl = downloadPath.startsWith("http")
    ? downloadPath
    : `${API_BASE_URL}${downloadPath}`;

  logs.innerHTML += `
    <div style="margin-top:20px;">
      <a href="${finalUrl}" target="_blank" download
         style="display:inline-block;padding:12px 20px;background:#16a34a;color:white;text-decoration:none;border-radius:8px;font-weight:600;">
        ⬇️ Download ${filename || "File"}
      </a>
    </div>
  `;

  logs.scrollTop = logs.scrollHeight;
}, 300);
    });
  }

  // --- File to SQL ---
  if (fileToSqlForm) {
    fileToSqlForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      resetProgress();
      appendLog('Preparing file import...');

      const fileInput = document.getElementById('source-file');
      const file = fileInput ? fileInput.files[0] : null;

      if (!file) {
        appendLog('<span class="status-error">Please select a file to import.</span>');
        return;
      }

      const ext = file.name.split('.').pop().toLowerCase();
      const isSqlDump = ext === 'sql';

      appendLog(`Detected file type: <strong>.${ext}</strong>${isSqlDump ? ' (SQL dump — executing directly)' : ' (tabular — importing via pandas)'}`);

      const payload = new FormData();
      payload.append('file', file);
      payload.append('target_db_type', getVal('file-target-db-type'));
      payload.append('target_host', getVal('file-target-host'));
      payload.append('target_port', getVal('file-target-port'));
      payload.append('target_username', getVal('file-target-username'));
      payload.append('target_password', getVal('file-target-password'));
      payload.append('target_database', getVal('file-target-db-name'));

      if (!isSqlDump) {
        payload.append('target_table', getVal('file-target-table'));
        payload.append('if_exists', getVal('file-if-exists'));
      }

      appendLog(`Importing to ${payload.get('target_db_type')}...`);
      await STAGING.open(payload);
    });
  }

  // File upload preview + drag-and-drop
  bindFileUploader();

  // Test Connection buttons
  bindTestConnections();

  // Bind DB type toggles
  bindDbToggles();
}

/* ---------- File Uploader ---------- */
function bindFileUploader() {
  const uploadInput = document.getElementById('source-file');
  const filePreview = document.getElementById('file-preview');
  const dropZone = document.getElementById('drop-zone');

  if (!uploadInput) return;

  uploadInput.addEventListener('change', () => {
    const file = uploadInput.files[0];
    updateFilePreview(file, filePreview);
  });

  if (dropZone) {
    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.classList.add('drag-over');
    });

    ['dragleave', 'dragend'].forEach(evt =>
      dropZone.addEventListener(evt, () => dropZone.classList.remove('drag-over'))
    );

    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
      const file = e.dataTransfer.files[0];
      if (file) {
        // Transfer the dropped file to the file input
        const dt = new DataTransfer();
        dt.items.add(file);
        uploadInput.files = dt.files;
        updateFilePreview(file, filePreview);
      }
    });
  }
}

function updateFilePreview(file, previewEl) {
  if (!file || !previewEl) return;
  const ext = file.name.split('.').pop().toLowerCase();
  const sizeKB = (file.size / 1024).toFixed(1);
  const typeLabel = ext === 'sql' ? '🗄 SQL Dump' : ext === 'csv' ? '📄 CSV' : ext === 'json' ? '📋 JSON' : '📊 Excel';
  previewEl.innerHTML = `${typeLabel} &nbsp;·&nbsp; <strong>${file.name}</strong> &nbsp;·&nbsp; ${sizeKB} KB`;
}

/* ---------- Test Connection ---------- */

/**
 * Configuration map: button id → {statusId, fields to read}
 */
const _TEST_CONN_CONFIGS = [
  {
    btnId: 'test-conn-source',
    statusId: 'conn-status-source',
    fields: {
      db_type: 'source-db-type',
      host: 'source-host',
      port: 'source-port',
      username: 'source-username',
      password: 'source-password',
      database: 'source-db-name',
    },
  },
  {
    btnId: 'test-conn-target',
    statusId: 'conn-status-target',
    fields: {
      db_type: 'target-db-type',
      host: 'target-host',
      port: 'target-port',
      username: 'target-username',
      password: 'target-password',
      database: 'target-db-name',
    },
  },
  {
    btnId: 'test-conn-export',
    statusId: 'conn-status-export',
    fields: {
      db_type: 'export-db-type',
      host: 'export-host',
      port: 'export-port',
      username: 'export-username',
      password: 'export-password',
      database: 'export-db-name',
    },
  },
  {
    btnId: 'test-conn-file-target',
    statusId: 'conn-status-file-target',
    fields: {
      db_type: 'file-target-db-type',
      host: 'file-target-host',
      port: 'file-target-port',
      username: 'file-target-username',
      password: 'file-target-password',
      database: 'file-target-db-name',
    },
  },
];

function bindTestConnections() {
  _TEST_CONN_CONFIGS.forEach(({ btnId, statusId, fields }) => {
    const btn = document.getElementById(btnId);
    const statusEl = document.getElementById(statusId);
    if (!btn || !statusEl) return;

    btn.addEventListener('click', async () => {
      // Build payload from the card's fields
      const payload = {};
      for (const [key, fieldId] of Object.entries(fields)) {
        payload[key] = getVal(fieldId);
      }

      // Show spinner
      setConnStatus(statusEl, 'loading', 'Testing…');
      btn.disabled = true;

      try {
        const response = await apiRequest('/test-connection', 'POST', payload);
        if (response && response.status === 'ok') {
          setConnStatus(statusEl, 'ok', `✅ Connected`);
        } else {
          const msg = (response && response.message) ? response.message : 'Connection failed.';
          setConnStatus(statusEl, 'error', `❌ ${truncate(msg, 80)}`);
        }
      } catch (err) {
        setConnStatus(statusEl, 'error', '❌ Network error');
      } finally {
        btn.disabled = false;
        // Auto-clear after 8 s
        setTimeout(() => setConnStatus(statusEl, '', ''), 8000);
      }
    });
  });
}

function setConnStatus(el, state, message) {
  el.className = 'conn-status' + (state ? ` conn-status--${state}` : '');
  el.innerHTML = message;
}

/* ---------- Helpers ---------- */

function getVal(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : '';
}

function truncate(str, max) {
  return str.length > max ? str.slice(0, max) + '…' : str;
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function resetProgress() {
  const progress = document.getElementById('migration-progress-fill');
  const progressText = document.getElementById('migration-progress-status');
  const logs = document.getElementById('migration-logs');
  if (progress) { progress.style.width = '0%'; progress.style.background = ''; }
  if (progressText) progressText.textContent = 'Pending';
  const pct = document.getElementById('migration-progress-percentage');
  if (pct) pct.textContent = '0%';
  if (logs) logs.innerHTML = '<p class="log-line">Initializing migration...</p>';
}

function appendLog(message) {
  const logs = document.getElementById('migration-logs');
  if (logs) {
    logs.innerHTML += `<p class="log-line">${message}</p>`;
    logs.scrollTop = logs.scrollHeight;
  }
}

function handleMigrationResponse(response, progressSim) {
  // Validation blocked the import entirely — nothing was written to the
  // database. This is distinct from both success and a generic error: show
  // the specific rows/columns that need fixing so the user can correct the
  // file and re-upload.
  if (response && response.rejected) {
    if (progressSim && progressSim.clear) progressSim.clear();

    const progressText = document.getElementById('migration-progress-status');
    const progress = document.getElementById('migration-progress-fill');
    const pct = document.getElementById('migration-progress-percentage');

    if (progressText) progressText.textContent = 'Needs correction';
    if (progress) {
      progress.style.width = '100%';
      progress.style.background = '#f59e0b';
    }
    if (pct) pct.textContent = '100%';

    const logs = document.getElementById('migration-logs');
    if (logs) {
      logs.innerHTML += `
        <p class="log-line" style="color:#f59e0b;">
          ⚠️ Import blocked — ${escapeHtml(String(response.warning_count || 0))} issue(s) found. Nothing was imported.
        </p>
      `;

      const warnings = response.warnings || [];
      if (warnings.length > 0) {
        logs.innerHTML += `
          <div style="margin-top:10px;padding:10px;background:#fef3c7;border-left:4px solid #f59e0b;border-radius:4px;">
            <p style="margin:0 0 8px 0;font-weight:600;">Fix these rows and re-upload:</p>
            <ul style="margin:0;padding-left:18px;">
              ${warnings.map((w) => `
                <li style="margin-bottom:4px;">
                  Row ${escapeHtml(String(w.row_index))}, column "<strong>${escapeHtml(String(w.column))}</strong>": ${escapeHtml(w.reason || 'Missing value')}
                </li>
              `).join('')}
            </ul>
          </div>
        `;
      }
      logs.scrollTop = logs.scrollHeight;
    }

    return;
  }

  const isError =
    !response ||
    response.error ||
    (
      !response.report &&
      !response.result &&
      !response.summary &&
      response.message &&
      /required|failed|error|not found|invalid|denied|placeholder/i.test(response.message)
    );

  if (isError) {
    if (progressSim && progressSim.clear) progressSim.clear();

    const errorDetail = response?.error || response?.message || 'Unknown error';
    appendLog(`<span class="status-error">Error: ${escapeHtml(errorDetail)}</span>`);

    const progressText = document.getElementById('migration-progress-status');
    const progress = document.getElementById('migration-progress-fill');
    const pct = document.getElementById('migration-progress-percentage');

    if (progressText) progressText.textContent = 'Failed';
    if (progress) {
      progress.style.width = '100%';
      progress.style.background = '#ef4444';
    }
    if (pct) pct.textContent = '100%';

    return;
  }

  if (response.message) {
    appendLog(response.message);
  }

  finishProgressSimulation(progressSim, response);
}


function startProgressSimulation() {
  const progress = document.getElementById('migration-progress-fill');
  const progressText = document.getElementById('migration-progress-status');
  const progressNumber = document.getElementById('migration-progress-percentage');
  const logs = document.getElementById('migration-logs');
  let percentage = 0;
  let intervalId;
  let postUploadId;
  
  const sim = {
    start: () => {
      intervalId = setInterval(() => {
        const remaining = 90 - percentage;
        if (remaining > 0) {
          percentage += Math.max(1, Math.floor(remaining * 0.15));
        }
        sim.render('Running');
      }, 600);
    },
    render: (statusText) => {
      if (progress) progress.style.width = `${percentage}%`;
      if (progressText) progressText.textContent = statusText;
      if (progressNumber) progressNumber.textContent = `${percentage}%`;
      if (logs && percentage % 15 === 0 && percentage < 90 && statusText === 'Running') {
        logs.innerHTML += `<p class="log-line">Working... ${percentage}%</p>`;
        logs.scrollTop = logs.scrollHeight;
      }
    },
    updateUpload: (uploadPercent) => {
      if (intervalId) { clearInterval(intervalId); intervalId = null; }
      
      percentage = Math.floor(uploadPercent / 2); // 0 to 50
      sim.render('Uploading...');
      
      if (uploadPercent === 100 && !postUploadId) {
        if (logs) {
          logs.innerHTML += `<p class="log-line">Upload complete. Processing data...</p>`;
          logs.scrollTop = logs.scrollHeight;
        }
        postUploadId = setInterval(() => {
          const remaining = 90 - percentage;
          if (remaining > 0) {
            percentage += Math.max(1, Math.floor(remaining * 0.15));
            sim.render('Processing...');
          }
        }, 600);
      }
    },
    clear: () => {
      if (intervalId) clearInterval(intervalId);
      if (postUploadId) clearInterval(postUploadId);
    }
  };
  
  sim.start();
  return sim;
}

function finishProgressSimulation(progressSim, response) {
    console.log("FINISH RESPONSE:", response);
  if (progressSim && progressSim.clear) progressSim.clear();

  const progress = document.getElementById('migration-progress-fill');
  const progressText = document.getElementById('migration-progress-status');
  const progressNumber = document.getElementById('migration-progress-percentage');
  const logs = document.getElementById('migration-logs');

  if (progress) {
    progress.style.width = '100%';
    progress.style.background = '';
  }
  if (progressText) progressText.textContent = 'Completed';
  if (progressNumber) progressNumber.textContent = '100%';

  if (!logs) return;

  logs.innerHTML += '<p class="log-line status-success">✅ Operation completed successfully.</p>';

  // SQL → SQL response can come as response.summary or response.report.summary
  const sqlSummary =
    response?.summary ||
    response?.report?.summary ||
    [];

  if (Array.isArray(sqlSummary) && sqlSummary.length > 0) {
    logs.innerHTML += '<p class="log-line"><strong>SQL to SQL Migration Summary:</strong></p>';

    sqlSummary.forEach((item) => {
      logs.innerHTML += `
        <div style="margin-top:10px;padding:10px;background-color:var(--bg-hover);border-left:4px solid var(--accent);border-radius:4px;">
          <p style="margin:0 0 5px 0;"><strong>Table:</strong> ${escapeHtml(item.table || '')}</p>
          <p style="margin:0 0 5px 0;"><strong>Status:</strong> ${escapeHtml(item.status || '')}</p>
          <p style="margin:0 0 5px 0;"><strong>Rows Transferred:</strong> ${item.rows_transferred ?? 0}</p>
        <p style="margin:0 0 5px 0;"><strong>Rows Cancelled:</strong> ${item.rows_cancelled ?? 0}</p>
        <p style="margin:0 0 5px 0;"><strong>Rows Failed:</strong> ${item.rows_failed ?? 0}</p>
          ${
            item.validation
              ? `<p style="margin:0;"><strong>Validation:</strong> Source ${item.validation.source_row_count ?? 0}, Target ${item.validation.target_row_count ?? 0}</p>`
              : ''
          }
        ${item.migration_report && item.migration_report.cancelled_rows && item.migration_report.cancelled_rows.length > 0 ? `
          <div style="margin-top:10px;padding:10px;border-radius:4px;background:#fef3c7;">
            <p style="margin:0 0 5px 0;font-weight:600;">Cancelled rows:</p>
            <ul style="margin:0 0 0 16px;padding:0;list-style:disc;">
              ${item.migration_report.cancelled_rows.slice(0,3).map(r => `<li>${escapeHtml(`Row ${r.original_index}: ${r.reason || r.error || 'Cancelled'}`)}</li>`).join('')}
              ${item.migration_report.cancelled_rows.length > 3 ? `<li>And ${item.migration_report.cancelled_rows.length - 3} more...</li>` : ''}
            </ul>
          </div>` : ''}
        </div>
      `;

      if (item.warnings && item.warnings.length > 0) {
        item.warnings.forEach((warning) => {
          logs.innerHTML += `
            <p class="log-line" style="color:#f59e0b;">
              ⚠️ Warning: ${escapeHtml(warning.message || '')}
            </p>
          `;
        });
      }
    });
  }

  // SQL → File
  if (response?.result?.rows_exported !== undefined) {
    logs.innerHTML += `<p class="log-line">Rows exported: <strong>${response.result.rows_exported}</strong></p>`;
  }

  // File → SQL
  if (response?.result?.rows_imported !== undefined) {
    const r = response.result;
    logs.innerHTML += `
      <div style="margin-top:10px;padding:10px;background-color:var(--bg-hover);border-left:4px solid var(--accent);border-radius:4px;">
        <p style="margin:0 0 5px 0;"><strong>Table:</strong> ${escapeHtml(r.table_name || '')}</p>
        <p style="margin:0 0 5px 0;"><strong>Rows Imported:</strong> ${r.rows_imported}</p>
        <p style="margin:0 0 5px 0;"><strong>Rows Cancelled:</strong> ${r.rows_cancelled ?? 0}</p>
        <p style="margin:0 0 5px 0;"><strong>Rows Failed:</strong> ${r.rows_failed ?? 0}</p>
        <p style="margin:0;"><strong>Database:</strong> ${escapeHtml(r.target_database || '')}</p>
      </div>
    `;
  }

 
  // Download button for SQL → File only
let downloadPath =
  response?.download_url ||
  response?.result?.download_url ||
  "";

let filename =
  response?.filename ||
  response?.result?.filename ||
  "exported_file";

if (downloadPath) {
  let finalDownloadUrl = "";

  if (downloadPath.startsWith("http")) {
    finalDownloadUrl = downloadPath;
  } else if (downloadPath.startsWith("/api")) {
    finalDownloadUrl = `http://localhost:5000${downloadPath}`;
  } else if (downloadPath.startsWith("/")) {
    finalDownloadUrl = `${API_BASE_URL}${downloadPath}`;
  }

  if (finalDownloadUrl) {
    logs.innerHTML += `
      <div style="margin-top:20px;">
        <a href="${finalDownloadUrl}"
           target="_blank"
           download
           class="btn btn-primary"
           style="display:inline-block;padding:12px 20px;background:#16a34a;color:white;text-decoration:none;border-radius:8px;font-weight:600;">
          ⬇️ Download ${escapeHtml(filename)}
        </a>
      </div>
    `;
  }
}
  


  logs.scrollTop = logs.scrollHeight;
}

function toggleDbFields(prefix) {
  const dbTypeSelect = document.getElementById(`${prefix}-db-type`);
  if (!dbTypeSelect) return;
  
  const dbType = dbTypeSelect.value;
  const isSqlite = dbType === 'sqlite';

  const hostInput = document.getElementById(`${prefix}-host`);
  if (!hostInput) return;

  const hostGroup = hostInput.parentElement;
  const portGroup = document.getElementById(`${prefix}-port`).parentElement;
  const userGroup = document.getElementById(`${prefix}-username`).parentElement;
  const passGroup = document.getElementById(`${prefix}-password`).parentElement;

  const displayStyle = isSqlite ? 'none' : 'block';
  if (hostGroup) hostGroup.style.display = displayStyle;
  if (portGroup) portGroup.style.display = displayStyle;
  if (userGroup) userGroup.style.display = displayStyle;
  if (passGroup) passGroup.style.display = displayStyle;

  const dbLabel = document.querySelector(`label[for="${prefix}-db-name"]`);
  if (dbLabel) {
    dbLabel.textContent = isSqlite ? 'Database File' : 'Database Name';
  }
}


function bindDbToggles() {
  const prefixes = ['source', 'target', 'export', 'file-target'];
  prefixes.forEach(prefix => {
    const select = document.getElementById(`${prefix}-db-type`);
    if (select) {
      select.addEventListener('change', () => toggleDbFields(prefix));
      // Initialize state on load
      toggleDbFields(prefix);
    }
  });
}