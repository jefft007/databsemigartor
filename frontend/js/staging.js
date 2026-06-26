/**
 * staging.js — Pre-import validation review modal.
 *
 * Flow:
 *  1. User fills File to SQL form and clicks "Import To Database"
 *  2. migration.js calls openStagingModal(formData)
 *  3. We POST to /api/import/validate, show all rows with issues highlighted
 *  4. User can change column types and re-validate
 *  5. User clicks "Approve & Import" → POST to /api/import/file-to-sql with original formData
 */

const STAGING = (() => {
  let _formData = null;
  let _validation = null;
  let _currentPage = 1;
  let _showOnlyErrors = false;
  let _typeOverrides = {};
  let _corrections = {}; // "rowIndex:column" -> corrected value, persists across pages
  const PAGE_SIZE = 100;

  // ── inject modal HTML once ──────────────────────────────────────
  function inject() {
    if (document.getElementById('staging-modal')) return;
    const el = document.createElement('div');
    el.id = 'staging-modal';
    el.className = 'staging-overlay';
    el.innerHTML = `
      <div class="staging-box">
        <div class="staging-header">
          <h2>Review Before Import</h2>
          <button class="button-secondary staging-close" onclick="STAGING.close()">Close</button>
        </div>

        <div class="staging-stats" id="staging-stats"></div>

        <div>
          <p style="font-size:0.85rem;color:var(--muted);margin:0 0 10px;">Column Type Mapping — change types before importing:</p>
          <div class="col-type-grid" id="staging-col-types"></div>
          <button class="button-secondary" style="margin-top:10px;font-size:0.82rem;padding:7px 16px;"
            onclick="STAGING.revalidate()">Re-validate with updated types</button>
        </div>

        <div class="staging-filter-bar">
          <label>
            <input type="checkbox" id="staging-errors-only" onchange="STAGING.toggleFilter(this.checked)" />
            Show only rows with errors
          </label>
          <span id="staging-row-count" style="margin-left:auto;"></span>
        </div>

        <div class="staging-table-wrap">
          <table class="staging-table">
            <thead id="staging-thead"></thead>
            <tbody id="staging-tbody"></tbody>
          </table>
        </div>

        <div class="staging-pagination" id="staging-pagination"></div>

        <div class="staging-footer">
          <button class="button-secondary" onclick="STAGING.close()">Cancel</button>
          <button class="button-primary" id="staging-approve-btn" onclick="STAGING.approve()">
            Approve &amp; Import
          </button>
        </div>
      </div>
    `;
    el.addEventListener('click', (e) => { if (e.target === el) STAGING.close(); });
    document.body.appendChild(el);
  }

  // ── open: called from migration.js ──────────────────────────────
  async function open(formData) {
    inject();
    _formData = formData;
    _currentPage = 1;
    _showOnlyErrors = false;
    _typeOverrides = {};
    _corrections = {};
    document.getElementById('staging-errors-only').checked = false;
    document.getElementById('staging-modal').classList.add('open');
    document.body.classList.add('modal-active');
    await _validate();
  }

  function close() {
    const modal = document.getElementById('staging-modal');
    if (modal) modal.classList.remove('open');
    document.body.classList.remove('modal-active');
  }

  // ── validate call ────────────────────────────────────────────────
  async function _validate() {
    _renderLoading();
    try {
      const validateFd = new FormData();
      for (const [k, v] of _formData.entries()) validateFd.append(k, v);
      validateFd.set('page', _currentPage);
      validateFd.set('page_size', PAGE_SIZE);
      validateFd.set('column_type_overrides', JSON.stringify(_typeOverrides));

      const resp = await apiRequest('/import/validate', 'POST', validateFd);

      if (!resp || resp.message === 'Cannot connect to server. Make sure the backend is running on http://127.0.0.1:5000/api') {
        throw new Error('Cannot reach the backend. Make sure Flask is running on port 5000.');
      }
      if (!resp.validation) {
        throw new Error(resp.message || resp.error || 'Unexpected response from server.');
      }

      _validation = resp.validation;
      _render();
    } catch (e) {
      const errEl = document.getElementById('staging-tbody');
      if (errEl) errEl.innerHTML =
        `<tr><td colspan="99" style="color:var(--danger);padding:24px;text-align:center;">
          Validation failed: ${e.message || e}
        </td></tr>`;
      document.getElementById('staging-stats').innerHTML =
        `<div class="staging-stat error"><label>Error</label><strong>Check console</strong></div>`;
      console.error('Staging validation error:', e);
    }
  }

  async function revalidate() {
    // Collect current dropdown values as overrides
    document.querySelectorAll('.col-type-select').forEach(sel => {
      _typeOverrides[sel.dataset.col] = sel.value;
    });
    _currentPage = 1;
    await _validate();
  }

  function toggleFilter(errorsOnly) {
    _showOnlyErrors = errorsOnly;
    _renderTable();
  }

  // ── render helpers ───────────────────────────────────────────────
  function _renderLoading() {
    const tbody = document.getElementById('staging-tbody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="99" style="color:var(--muted);text-align:center;padding:32px;">Validating...</td></tr>';
  }

  function _render() {
    if (!_validation) return;
    _renderStats();
    _renderColTypes();
    _renderTable();
    _renderPagination();
  }

  function _renderStats() {
    const v = _validation;
    document.getElementById('staging-stats').innerHTML = `
      <div class="staging-stat"><label>Total Rows</label><strong>${v.total_rows}</strong></div>
      <div class="staging-stat ok"><label>Valid</label><strong>${v.total_rows - v.total_issues}</strong></div>
      <div class="staging-stat error"><label>Issues</label><strong>${v.total_issues}</strong></div>
      <div class="staging-stat"><label>Columns</label><strong>${v.columns.length}</strong></div>
    `;
  }

  function _renderColTypes() {
    const v = _validation;
    const types = v.supported_type_overrides || ['TEXT','INTEGER','FLOAT','BOOLEAN','DATETIME'];
    document.getElementById('staging-col-types').innerHTML = v.columns.map(col => {
      const current = _typeOverrides[col] || v.column_types[col] || 'TEXT';
      const options = types.map(t =>
        `<option value="${t}" ${t === current ? 'selected' : ''}>${t}</option>`
      ).join('');
      return `
        <div class="col-type-item">
          <label title="${col}">${col.length > 14 ? col.slice(0,12) + '…' : col}</label>
          <select class="col-type-select" data-col="${col}">${options}</select>
        </div>`;
    }).join('');
  }

  function _renderTable() {
    const v = _validation;
    const rows = _showOnlyErrors ? v.issue_rows : v.rows;

    document.getElementById('staging-row-count').textContent =
      _showOnlyErrors
        ? `Showing ${rows.length} problem row(s) of ${v.total_rows} total`
        : `Showing ${rows.length} row(s) (page ${_currentPage} of ${v.pagination.total_pages})`;

    // Header
    document.getElementById('staging-thead').innerHTML =
      `<tr><th>#</th>${v.columns.map(c => `<th>${c}</th>`).join('')}<th>Issues</th></tr>`;

    if (rows.length === 0) {
      document.getElementById('staging-tbody').innerHTML =
        `<tr><td colspan="${v.columns.length + 2}" style="text-align:center;color:var(--muted);padding:24px;">
          ${_showOnlyErrors ? 'No issues found — all rows are valid.' : 'No rows to display.'}
        </td></tr>`;
      return;
    }

    document.getElementById('staging-tbody').innerHTML = rows.map(row => {
      const isError = row.status === 'error';
      const issueMap = {};
      (row.issues || []).forEach(i => { issueMap[i.column] = i.message; });

      const cells = v.columns.map(col => {
        const correctionKey = `${row.row_index}:${col}`;
        const hasCorrection = Object.prototype.hasOwnProperty.call(_corrections, correctionKey);
        const val = hasCorrection ? _corrections[correctionKey] : row.data[col];
        const issue = issueMap[col];

        if (issue) {
          const inputVal = val === null || val === undefined ? '' : String(val).replace(/"/g, '&quot;');
          return `<td class="staging-cell-error" title="${issue}">
            <input
              type="text"
              class="staging-cell-input"
              data-row="${row.row_index}"
              data-col="${col}"
              value="${inputVal}"
              placeholder="Enter value..."
              oninput="STAGING.recordCorrection(${row.row_index}, '${col.replace(/'/g, "\\'")}', this.value)"
            />
            <br><span class="staging-issue-badge">${issue}</span>
          </td>`;
        }

        const display = val === null || val === undefined ? '<span style="color:var(--muted)">null</span>' : String(val);
        return `<td>${display}</td>`;
      }).join('');

      const issueSummary = (row.issues || []).length > 0
        ? `<span style="color:var(--danger);font-size:0.78rem;">${row.issues.length} issue(s)</span>`
        : `<span style="color:var(--success);font-size:0.78rem;">OK</span>`;

      return `<tr class="${isError ? 'staging-row-error' : 'staging-row-ok'}">
        <td style="color:var(--muted)">${row.row_index + 1}</td>
        ${cells}
        <td>${issueSummary}</td>
      </tr>`;
    }).join('');
  }

  // ── track an in-browser correction; persists across pages/filters ──
  function recordCorrection(rowIndex, column, value) {
    _corrections[`${rowIndex}:${column}`] = value;
  }

  function _renderPagination() {
    const v = _validation;
    if (_showOnlyErrors || v.pagination.total_pages <= 1) {
      document.getElementById('staging-pagination').innerHTML = '';
      return;
    }
    const pg = v.pagination;
    document.getElementById('staging-pagination').innerHTML = `
      <button class="button-secondary" onclick="STAGING.goPage(${pg.page - 1})"
        ${pg.page <= 1 ? 'disabled' : ''}>Previous</button>
      <span>Page ${pg.page} of ${pg.total_pages}</span>
      <button class="button-secondary" onclick="STAGING.goPage(${pg.page + 1})"
        ${pg.page >= pg.total_pages ? 'disabled' : ''}>Next</button>
    `;
  }

  async function goPage(page) {
    const v = _validation;
    if (!v || page < 1 || page > v.pagination.total_pages) return;
    _currentPage = page;
    await _validate();
  }

  // ── approve: run the actual import, applying any corrections made ──
  async function approve() {
    const btn = document.getElementById('staging-approve-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Importing...'; }

    // Apply current column-type dropdown values as overrides
    document.querySelectorAll('.col-type-select').forEach(sel => {
      _typeOverrides[sel.dataset.col] = sel.value;
    });

    const filePath = _validation && _validation.file_path;
    const hasCorrections = Object.keys(_corrections).length > 0;

    try {
      let response;

      if (hasCorrections && filePath) {
        // User edited at least one flagged cell — re-read the original file
        // server-side and apply corrections by row/column before importing,
        // rather than resubmitting the unmodified file.
        const targetFields = {};
        for (const [k, v] of _formData.entries()) {
          if (k === 'file') continue; // already uploaded; re-use the saved path instead
          targetFields[k] = v;
        }

        response = await apiRequest('/import/file-to-sql/corrected', 'POST', {
          ...targetFields,
          file_path: filePath,
          corrections: _corrections,
          column_type_overrides: _typeOverrides,
        });
      } else {
        // No corrections made — original behavior: resubmit the file as-is.
        const finalFd = new FormData();
        for (const [k, v] of _formData.entries()) finalFd.append(k, v);
        finalFd.set('column_type_overrides', JSON.stringify(_typeOverrides));
        response = await apiRequest('/import/file-to-sql', 'POST', finalFd);
      }

      // If the backend still finds issues (e.g. a correction was left blank,
      // or a new issue was introduced), stay open and show what's still wrong
      // instead of closing as if it succeeded.
      if (response && response.rejected) {
        if (btn) { btn.disabled = false; btn.textContent = 'Approve & Import'; }
        await _validate();
        alert(`${response.warning_count || 0} row(s) still have issues. Please fix the highlighted cells.`);
        return;
      }

      close();
      if (typeof handleMigrationResponse === 'function') {
        handleMigrationResponse(response, null);
      }
    } catch (e) {
      if (btn) { btn.disabled = false; btn.textContent = 'Approve & Import'; }
      alert('Import failed: ' + (e.message || e));
    }
  }

  return { open, close, revalidate, toggleFilter, goPage, approve, recordCorrection };
})();