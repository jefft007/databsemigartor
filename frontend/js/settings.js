const defaultSettings = {
  strictMode: false,
  autoEnum: false,
  backtick: false,
  autoMap: false,
  maxUpload: 250,
  timeout: 600,
  concurrent: 4,
  batchSize: 1000,
  allowSql: true,
  allowXlsx: true,
  allowCsv: true,
  users: [
    { id: 1, name: 'Sara Blake', email: 'sara@example.com', role: 'Admin' },
    { id: 2, name: 'Daniel Park', email: 'daniel@example.com', role: 'User' },
    { id: 3, name: 'Priya Nair', email: 'priya@example.com', role: 'Viewer' }
  ],
  _uid: 0,
  UPOOL: [
    { name: 'Aisha Khan', email: 'aisha@example.com', role: 'User' },
    { name: 'Tom Reed', email: 'tom@example.com', role: 'Viewer' },
    { name: 'Lina Wu', email: 'lina@example.com', role: 'Admin' }
  ],
  logFilter: 'All',
  logs: [
    { ts: '10:22:03', lv: 'INFO', m: 'Scheduled migration queue polled' },
    { ts: '10:23:17', lv: 'SUCCESS', m: 'Backup archive created' },
    { ts: '10:24:08', lv: 'WARN', m: 'Slow response from analytics DB' },
    { ts: '10:25:09', lv: 'ERROR', m: 'Failed to connect to remote host' }
  ],
  minPw: 8,
  pwExpiry: 90,
  twoFactor: true,
  deviceAlerts: true,
  reqUpper: true,
  reqNum: true,
  reqSym: false,
  sessionTO: 30,
  maxFail: 5,
  enforce2fa: true,
  ipAllow: false,
  sso: false,
  autoDownload: true,
  includeDiff: true,
  fileFormat: '.sql',
  theme: 'Light',
  autoDelete: true,
  retention: 30,
  notifEmail: 'admin@example.com',
  emailNotifications: true,
  successAlerts: true,
  failureAlerts: true
};

const S = (() => {
  try {
    const stored = localStorage.getItem('sqlMigratorSettings');
    if (stored) {
      return { ...defaultSettings, ...JSON.parse(stored) };
    }
  } catch (e) {
    console.warn('Failed to parse settings from localStorage', e);
  }
  return { ...defaultSettings };
})();

function saveSettingsLocally() {
  localStorage.setItem('sqlMigratorSettings', JSON.stringify(S));
}

function applyTheme(theme) {
  if (theme === 'Dark') {
    document.body.classList.remove('light-theme');
  } else if (theme === 'Light') {
    document.body.classList.add('light-theme');
  } else {
    // System
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      document.body.classList.add('light-theme');
    } else {
      document.body.classList.remove('light-theme');
    }
  }
}


function toast(message) {
  showNotification(message, 'success');
}

function tog(key) {
  S[key] = !S[key];
  saveSettingsLocally();
  renderSettings();
  if (key === 'twoFactor' || key === 'deviceAlerts') {
    showNotification('Security settings updated.', 'success');
  }
}

function sv(key, value) {
  const parsed = Number(value);
  if (key === 'retention' && parsed < 0) {
      toast('Retention must be a positive number');
      return;
  }
  S[key] = Number.isNaN(parsed) || value === '' ? value : parsed;
  if (key === 'theme') {
    applyTheme(S[key]);
  }
  saveSettingsLocally();
  renderSettings();
}

function renderSettings() {
  const activeTab = document.querySelector('.tab-pill.active');
  const activePage = document.querySelector('#settings-subnav .subnav-item.active');
  if (activeTab && activePage) {
    renderSubpage(activeTab.dataset.tab, activePage.dataset.key, getCurrentRole());
  }
}

function TR(label, desc, key) {
  return `
    <div class="toggle-row">
      <div style="max-width:72%;">
        <strong>${label}</strong>
        <div class="small-text">${desc}</div>
      </div>
      <label class="switch"><input type="checkbox" onchange="tog('${key}')" ${S[key] ? 'checked' : ''} /><span class="slider"></span></label>
    </div>
  `;
}

function FL(label, key, type = 'number') {
  return `
    <div class="input-group">
      <label>${label}</label>
      <input type="${type}" value="${S[key] !== undefined ? S[key] : ''}" onchange="sv('${key}', this.value)" />
    </div>
  `;
}

function SEL(label, key, options) {
  return `
    <div class="input-group">
      <label>${label}</label>
      <select onchange="sv('${key}', this.value)">
        ${options.map((value) => `<option value="${value}" ${S[key] === value ? 'selected' : ''}>${value}</option>`).join('')}
      </select>
    </div>
  `;
}

function rb(role) {
  const cls = role === 'Admin' ? 'rb-admin' : role === 'User' ? 'rb-user' : 'rb-viewer';
  return `<span class="${cls}">${role}</span>`;
}

function addUser() {
  const next = S.UPOOL[S._uid % S.UPOOL.length];
  const id = Date.now();
  S.users.push({ id, name: next.name, email: next.email, role: next.role });
  S._uid += 1;
  toast('User added');
  renderSettings();
}

function delUser(id) {
  S.users = S.users.filter((user) => user.id !== id);
  toast('User removed');
  renderSettings();
}

function filterU(query) {
  const q = query.toLowerCase();
  document.querySelectorAll('#utbl tbody tr').forEach((row) => {
    const name = row.dataset.name.toLowerCase();
    const email = row.dataset.email.toLowerCase();
    row.style.display = name.includes(q) || email.includes(q) ? '' : 'none';
  });
}

function addLog() {
  const now = new Date();
  const ts = now.toTimeString().slice(0, 8);
  S.logs.push({ ts, lv: 'INFO', m: ' Log refresh by arun@company.io' });
  renderSettings();
}

function saveProfile(event) {
  event.preventDefault();
  const form = event.target;
  const firstName = form.querySelector('[name="firstName"]').value;
  const lastName = form.querySelector('[name="lastName"]').value;
  const email = form.querySelector('[name="email"]').value;
  
  const user = getUserInfo() || { role: 'User' };
  user.name = `${firstName} ${lastName}`.trim();
  user.email = email;
  setUserInfo(user);
  
  toast('Profile saved');
  renderSettings();
  setProfileSummary(); // if this function exists to update header
}

function pgProfile() {
  const user = getUserInfo() || { name: 'User', email: '' };
  const [firstName, ...rest] = (user.name || '').split(' ');
  return `
    <h3 class="subpage-heading">Profile</h3>
    <p class="subpage-sub">Manage your account details and contact email.</p>
    <div class="grid-two">
      <div style="display:flex; gap:12px; align-items:center;">
        <div class="avatar-circle" style="background:linear-gradient(135deg,#5B6CF7,#7E8CFF);">${(user.name || 'SM').split(' ').map((s) => s[0]).slice(0,2).join('')}</div>
        <div>
          <div style="font-weight:700;">${user.name || 'User'}</div>
          <div class="small-text">${user.email || 'No email available'}</div>
        </div>
      </div>
      <div></div>
    </div>
    <form onsubmit="saveProfile(event)">
      <div class="grid-two">
        <div class="input-group"><label>First name</label><input name="firstName" value="${firstName || ''}" /></div>
        <div class="input-group"><label>Last name</label><input name="lastName" value="${rest.join(' ') || ''}" /></div>
      </div>
      <div class="input-group"><label>Email</label><input type="email" name="email" value="${user.email || ''}" /></div>
      <div style="display:flex; gap:12px; margin-top:12px;"><button type="button" class="button-secondary" onclick="openPasswordModal()">Change Password</button><button type="submit" class="button-primary">Save</button></div>
    </form>
  `;
}

function pgSecurity() {
  return `
    <h3 class="subpage-heading">Security</h3>
    <p class="subpage-sub">Configure two-factor authentication and device alerts.</p>
    <div style="display: flex; flex-direction: column; gap: 20px; margin-top: 16px;">
      ${TR('Two-factor authentication (2FA)', 'Require a second factor to sign in.', 'twoFactor')}
      ${TR('New device login alerts', 'Notify you when a new device signs in.', 'deviceAlerts')}
    </div>
    <div style="margin-top:32px; border-top: 1px solid var(--border); padding-top: 24px;">
      <button class="button-danger" onclick="logoutAllDevices()">Logout from all devices</button>
    </div>
  `;
}

function getNotificationSettings() {
  let settings = {
    emailNotifications: true,
    migrationSuccessAlerts: true,
    migrationFailureAlerts: true,
    notificationEmail: "user@example.com"
  };
  try {
    const stored = localStorage.getItem('sqlMigrator_notificationSettings');
    if (stored) {
      settings = JSON.parse(stored);
    }
  } catch (e) {}
  return settings;
}

function toggleNotifSubgroup() {
  const isChecked = document.getElementById('ns_emailNotifications').checked;
  const subgroup = document.getElementById('notif-subgroup');
  if (subgroup) {
    subgroup.style.opacity = isChecked ? '1' : '0.45';
    subgroup.style.pointerEvents = isChecked ? 'auto' : 'none';
  }
}

async function saveNotifications(event) {
  event.preventDefault();
  const btn = document.getElementById('ns_saveBtn');
  const emailVal = document.getElementById('ns_notificationEmail').value.trim();
  
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(emailVal)) {
    showNotification("Please enter a valid notification email.", "danger");
    return;
  }
  
  const payload = {
    emailNotifications: document.getElementById('ns_emailNotifications').checked,
    migrationSuccessAlerts: document.getElementById('ns_migrationSuccessAlerts').checked,
    migrationFailureAlerts: document.getElementById('ns_migrationFailureAlerts').checked,
    notificationEmail: emailVal
  };

  btn.textContent = 'Saving...';
  btn.disabled = true;

  try {
    try {
      await apiRequest('/settings', 'PUT', payload);
    } catch(e) {
      console.warn("Backend API issue, using localStorage fallback.");
    }
    localStorage.setItem('sqlMigrator_notificationSettings', JSON.stringify(payload));
    showNotification("Notification settings updated successfully.", "success");
  } catch (error) {
    showNotification("Failed to save notification settings.", "danger");
  } finally {
    btn.textContent = 'Save';
    btn.disabled = false;
  }
}

function pgNotifications() {
  const ns = getNotificationSettings();
  return `
    <h3 class="subpage-heading">Notifications</h3>
    <p class="subpage-sub">Control email alerts for migration events.</p>
    <form onsubmit="saveNotifications(event)" id="notifications-form" style="display: flex; flex-direction: column; gap: 20px; margin-top: 16px;">
      
      <div class="toggle-row">
        <div style="max-width:72%;">
          <strong>Email notifications</strong>
          <div class="small-text">Receive migration update emails.</div>
        </div>
        <label class="switch">
          <input type="checkbox" id="ns_emailNotifications" onchange="toggleNotifSubgroup()" ${ns.emailNotifications ? 'checked' : ''} />
          <span class="slider"></span>
        </label>
      </div>

      <div id="notif-subgroup" style="opacity:${ns.emailNotifications ? '1' : '0.45'}; pointer-events:${ns.emailNotifications ? 'auto' : 'none'}; display: flex; flex-direction: column; gap: 20px;">
        <div class="toggle-row">
          <div style="max-width:72%;">
            <strong>Migration success alerts</strong>
            <div class="small-text">Notify when a migration completes successfully.</div>
          </div>
          <label class="switch">
            <input type="checkbox" id="ns_migrationSuccessAlerts" ${ns.migrationSuccessAlerts ? 'checked' : ''} />
            <span class="slider"></span>
          </label>
        </div>

        <div class="toggle-row">
          <div style="max-width:72%;">
            <strong>Migration failure alerts</strong>
            <div class="small-text">Notify when a migration fails.</div>
          </div>
          <label class="switch">
            <input type="checkbox" id="ns_migrationFailureAlerts" ${ns.migrationFailureAlerts ? 'checked' : ''} />
            <span class="slider"></span>
          </label>
        </div>

        <div class="input-group">
          <label>Notification email</label>
          <input type="email" id="ns_notificationEmail" value="${ns.notificationEmail}" />
        </div>
      </div>

      <div style="margin-top:12px; text-align:right; border-top: 1px solid var(--border); padding-top: 24px;">
        <button type="submit" id="ns_saveBtn" class="button-primary">Save</button>
      </div>
    </form>
  `;
}

function pgPreferences() {
  return `
    <h3 class="subpage-heading">Preferences</h3>
    <p class="subpage-sub">Select your preferred display and export settings.</p>
    ${SEL('Theme', 'theme', ['Light','Dark','System'])}
    <div style="display:flex; gap:8px; margin-top:8px;">
      ${['Light','Dark','System'].map((theme) => `<div class="theme-pill" onclick="sv('theme','${theme}')" style="padding:8px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.06); cursor:pointer; ${S.theme===theme?'border-color:#185FA5;':''}">${theme}</div>`).join('')}
    </div>
    <div style="margin-top:12px; text-align:right;"><button class="button-primary" onclick="toast('Preferences saved')">Save</button></div>
  `;
}

function getReportSettings() {
  let settings = {
    autoDownloadReports: true,
    includeRowDiff: true,
    defaultFileFormat: ".pdf"
  };
  try {
    const stored = localStorage.getItem('sqlMigrator_reportDownloadSettings');
    if (stored) {
      settings = JSON.parse(stored);
    }
  } catch (e) {}
  return settings;
}

async function saveReportSettings(event) {
  event.preventDefault();
  const btn = document.getElementById('rs_saveBtn');
  
  const payload = {
    autoDownloadReports: document.getElementById('rs_autoDownloadReports').checked,
    includeRowDiff: document.getElementById('rs_includeRowDiff').checked,
    defaultFileFormat: document.getElementById('rs_defaultFileFormat').value
  };

  btn.textContent = 'Saving...';
  btn.disabled = true;

  try {
    try {
      await apiRequest('/settings', 'PUT', payload);
    } catch(e) {
      console.warn("Backend API issue, using localStorage fallback.");
    }
    localStorage.setItem('sqlMigrator_reportDownloadSettings', JSON.stringify(payload));
    showNotification("Report download settings updated successfully.", "success");
  } catch (error) {
    showNotification("Failed to save report download settings.", "danger");
  } finally {
    btn.textContent = 'Save';
    btn.disabled = false;
  }
}

function pgReports() {
  const rs = getReportSettings();
  const formats = ['.sql','.xlsx','.csv','.pdf'];
  
  return `
    <h3 class="subpage-heading">Reports & downloads</h3>
    <p class="subpage-sub">Configure report delivery and export format.</p>
    <form onsubmit="saveReportSettings(event)" id="reports-form" style="display: flex; flex-direction: column; gap: 20px; margin-top: 16px;">
      
      <div class="toggle-row">
        <div style="max-width:72%;">
          <strong>Auto-download reports</strong>
          <div class="small-text">Save reports to your device automatically.</div>
        </div>
        <label class="switch">
          <input type="checkbox" id="rs_autoDownloadReports" ${rs.autoDownloadReports ? 'checked' : ''} />
          <span class="slider"></span>
        </label>
      </div>

      <div class="toggle-row">
        <div style="max-width:72%;">
          <strong>Include row diff</strong>
          <div class="small-text">Include row difference details in report exports.</div>
        </div>
        <label class="switch">
          <input type="checkbox" id="rs_includeRowDiff" ${rs.includeRowDiff ? 'checked' : ''} />
          <span class="slider"></span>
        </label>
      </div>

      <div class="input-group">
        <label>Default file format</label>
        <select id="rs_defaultFileFormat">
          ${formats.map(f => `<option value="${f}" ${rs.defaultFileFormat === f ? 'selected' : ''}>${f}</option>`).join('')}
        </select>
      </div>

      <div style="margin-top:12px; text-align:right; border-top: 1px solid var(--border); padding-top: 24px;">
        <button type="submit" id="rs_saveBtn" class="button-primary">Save</button>
      </div>
    </form>
  `;
}

function getFileHandlingSettings() {
  let settings = {
    autoDeleteUploadedFiles: true,
    retentionPeriodDays: 30
  };
  try {
    const stored = localStorage.getItem('sqlMigrator_fileHandlingSettings');
    if (stored) {
      settings = JSON.parse(stored);
    }
  } catch (e) {}
  return settings;
}

function toggleFileHandlingSubgroup() {
  const isChecked = document.getElementById('fh_autoDeleteUploadedFiles').checked;
  const subgroup = document.getElementById('fh-subgroup');
  if (subgroup) {
    subgroup.style.opacity = isChecked ? '1' : '0.4';
    subgroup.style.pointerEvents = isChecked ? 'auto' : 'none';
  }
}

async function saveFileHandlingSettings(event) {
  event.preventDefault();
  const btn = document.getElementById('fh_saveBtn');
  
  const retentionVal = parseInt(document.getElementById('fh_retentionPeriodDays').value, 10);
  
  if (isNaN(retentionVal) || retentionVal < 1 || retentionVal > 365) {
    showNotification("Please enter a valid retention period between 1 and 365 days.", "danger");
    return;
  }
  
  const payload = {
    autoDeleteUploadedFiles: document.getElementById('fh_autoDeleteUploadedFiles').checked,
    retentionPeriodDays: retentionVal
  };

  btn.textContent = 'Saving...';
  btn.disabled = true;

  try {
    try {
      await apiRequest('/settings', 'PUT', payload);
    } catch(e) {
      console.warn("Backend API issue, using localStorage fallback.");
    }
    localStorage.setItem('sqlMigrator_fileHandlingSettings', JSON.stringify(payload));
    showNotification("File handling settings updated successfully.", "success");
  } catch (error) {
    showNotification("Failed to save file handling settings.", "danger");
  } finally {
    btn.textContent = 'Save';
    btn.disabled = false;
  }
}

function pgFiles() {
  const fh = getFileHandlingSettings();
  
  return `
    <h3 class="subpage-heading">File handling</h3>
    <p class="subpage-sub">Choose how uploaded files are managed and retained.</p>
    <form onsubmit="saveFileHandlingSettings(event)" id="filehandling-form" style="display: flex; flex-direction: column; gap: 20px; margin-top: 16px;">
      
      <div class="toggle-row">
        <div style="max-width:72%;">
          <strong>Auto-delete uploaded files</strong>
          <div class="small-text">Remove uploaded files after retention expires.</div>
        </div>
        <label class="switch">
          <input type="checkbox" id="fh_autoDeleteUploadedFiles" onchange="toggleFileHandlingSubgroup()" ${fh.autoDeleteUploadedFiles ? 'checked' : ''} />
          <span class="slider"></span>
        </label>
      </div>

      <div id="fh-subgroup" style="opacity:${fh.autoDeleteUploadedFiles ? '1' : '0.4'}; pointer-events:${fh.autoDeleteUploadedFiles ? 'auto' : 'none'};">
        <div class="input-group">
          <label>Retention period (days)</label>
          <input type="number" id="fh_retentionPeriodDays" value="${fh.retentionPeriodDays}" min="1" max="365" required />
        </div>
      </div>

      <div style="margin-top:12px; text-align:right; border-top: 1px solid var(--border); padding-top: 24px;">
        <button type="submit" id="fh_saveBtn" class="button-primary">Save</button>
      </div>
    </form>
  `;
}

function pgConversion() {
  return `
    <h3 class="subpage-heading">Conversion rules</h3>
    <p class="subpage-sub">Adjust conversion behavior for migration jobs.</p>
    ${TR('Strict mode', 'Fail the entire migration if any warnings are detected', 'strictMode')}
    ${TR('Auto-convert ENUM types', 'Replace MySQL ENUMs with PostgreSQL CHECK constraints', 'autoEnum')}
    ${TR('Convert backtick identifiers', 'Replace backticks with double quotes on target', 'backtick')}
    ${TR('Auto-map data types', 'Match source types to nearest target equivalent', 'autoMap')}
    <div style="margin-top:12px; text-align:right;"><button class="button-primary" onclick="toast('Conversion rules saved')">Save</button></div>
  `;
}

function pgSystem() {
  return `
    <h3 class="subpage-heading">System configuration</h3>
    <p class="subpage-sub">Control upload limits and allowed file types.</p>
    <div class="fr2" style="display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:16px;">
      ${FL('Max upload size (MB)', 'maxUpload')}
      ${FL('Migration timeout (s)', 'timeout')}
      ${FL('Max concurrent migrations', 'concurrent')}
      ${FL('Default batch size (rows)', 'batchSize')}
    </div>
    <div style="margin:18px 0 8px; font-weight:600;">Allowed file types</div>
    <div style="display:flex; gap:16px; flex-wrap:wrap;">
      <label><input type="checkbox" onchange="tog('allowSql')" ${S.allowSql ? 'checked' : ''} /> .sql</label>
      <label><input type="checkbox" onchange="tog('allowXlsx')" ${S.allowXlsx ? 'checked' : ''} /> .xlsx</label>
      <label><input type="checkbox" onchange="tog('allowCsv')" ${S.allowCsv ? 'checked' : ''} /> .csv</label>
    </div>
    <div style="margin-top:12px; text-align:right;"><button class="button-primary" onclick="toast('System configuration saved')">Save</button></div>
  `;
}

function pgUserMgmt() {
  return `
    <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:12px;">
      <div>
        <h3 class="subpage-heading" style="margin:0;">All users</h3>
        <p class="subpage-sub">Manage application user accounts and roles.</p>
      </div>
      <button class="button-primary" onclick="addUser()">Add user</button>
    </div>
    <div style="margin-bottom:12px;"><input id="user-search" oninput="filterU(this.value)" placeholder="Search by name or email" style="width:100%; padding:10px; border-radius:8px; border:1px solid rgba(255,255,255,0.08); background:rgba(255,255,255,0.04); color:var(--text);" /></div>
    <div style="overflow-x:auto;">
      <table id="utbl" style="width:100%; table-layout:fixed; border-collapse:collapse;">
        <thead>
          <tr>
            <th style="padding:12px 10px; text-align:left; width:56px;">Avatar</th>
            <th style="padding:12px 10px; text-align:left;">Name</th>
            <th style="padding:12px 10px; text-align:left;">Email</th>
            <th style="padding:12px 10px; text-align:left;">Role</th>
            <th style="padding:12px 10px; text-align:left;">Actions</th>
          </tr>
        </thead>
        <tbody>
          ${S.users.map((u) => `
            <tr data-name="${u.name}" data-email="${u.email}" style="border-bottom:1px solid rgba(255,255,255,0.06);">
              <td style="padding:10px;"><div class="avatar-circle" style="background:linear-gradient(135deg,#5B6CF7,#7E8CFF);">${u.name.split(' ').map((s) => s[0]).slice(0,2).join('')}</div></td>
              <td style="padding:10px;">${u.name}</td>
              <td style="padding:10px;">${u.email}</td>
              <td style="padding:10px;">${rb(u.role)}</td>
              <td style="padding:10px;"><button class="btn xs" style="margin-right:8px;" onclick="toast('Edit user not implemented')">Edit</button><button class="btn xs dng" onclick="delUser(${u.id})">Delete</button></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function pgLogs() {
  const filtered = S.logFilter === 'All' ? S.logs : S.logs.filter((log) => log.lv.includes(S.logFilter));
  return `
    <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:12px;">
      <div>
        <h3 class="subpage-heading" style="margin:0;">System logs</h3>
        <p class="subpage-sub">Live output from the migration engine.</p>
      </div>
      <div style="display:flex; gap:8px; align-items:center;">
        <select onchange="sv('logFilter', this.value); renderSettings()" style="padding:10px; border-radius:8px; border:1px solid rgba(0,0,0,0.16); background:#ffffff; color:#111111; box-shadow:none;">
          ${['All','INFO','SUCCESS','WARN','ERROR'].map((level) => `<option value="${level}" ${S.logFilter===level?'selected':''}>${level}</option>`).join('')}
        </select>
        <button class="button-secondary" onclick="toast('Logs downloaded')">Download Logs</button>
        <button class="button-secondary" style="background:#FCEBEB; color:#A32D2D; border:1px solid rgba(163,45,45,0.12);" onclick="S.logs=[]; renderSettings();">Clear Logs</button>
      </div>
    </div>
    <div style="background:#1a1d2e; border-radius:8px; padding:10px 13px; font-family:monospace; font-size:11px; line-height:1.8; max-height:160px; overflow-y:auto;">
      ${filtered.map((log) => `
        <div style="display:flex; gap:8px; align-items:center; padding:4px 0;">
          <span style="color:#5b6280; width:72px;">${log.ts}</span>
          <span style="color:${log.lv==='INFO'?'#60a5fa':log.lv==='SUCCESS'?'#34d399':log.lv==='WARN'?'#fbbf24':'#f87171'}; width:72px;">${log.lv}</span>
          <span style="color:#c4c9e0;">${log.m}</span>
        </div>
      `).join('')}
    </div>
    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:12px;">
      <div class="small-text">${filtered.length} entries</div>
      <button class="button-secondary" onclick="addLog()">Refresh</button>
    </div>
  `;
}

function pgSecpol() {
  return `
    <div style="display:grid; gap:16px;">
      <div class="card" style="padding:18px;">
        <h4 style="margin:0 0 8px;">Password policy</h4>
        <div class="fr2" style="display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px;">
          ${FL('Minimum password length', 'minPw')}
          ${FL('Expiry days', 'pwExpiry')}
        </div>
        <div style="margin-top:12px; display:flex; gap:16px; flex-wrap:wrap;">
          <label><input type="checkbox" onchange="tog('reqUpper')" ${S.reqUpper ? 'checked' : ''} /> Require uppercase</label>
          <label><input type="checkbox" onchange="tog('reqNum')" ${S.reqNum ? 'checked' : ''} /> Require numbers</label>
          <label><input type="checkbox" onchange="tog('reqSym')" ${S.reqSym ? 'checked' : ''} /> Require symbols</label>
        </div>
        <div style="margin-top:12px; text-align:right;"><button class="button-primary" onclick="toast('Password policy saved')">Save</button></div>
      </div>
      <div class="card" style="padding:18px;">
        <h4 style="margin:0 0 8px;">Session & access control</h4>
        <div class="fr2" style="display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px;">
          ${FL('Session timeout (mins)', 'sessionTO')}
          ${FL('Max failed login attempts', 'maxFail')}
        </div>
        ${TR('Enforce 2FA for all users', '', 'enforce2fa')}
        ${TR('IP allowlist', '', 'ipAllow')}
        ${TR('Single sign-on (SSO)', '', 'sso')}
        <div style="margin-top:12px; text-align:right;"><button class="button-primary" onclick="toast('Session & access control saved')">Save</button></div>
      </div>
    </div>
  `;
}

const pageMap = {
  profile: pgProfile,
  security: pgSecurity,
  notifications: pgNotifications,
  preferences: pgPreferences,
  reports: pgReports,
  files: pgFiles,
  conversion: pgConversion,
  system: pgSystem,
  usermgmt: pgUserMgmt,
  logs: pgLogs,
  secpol: pgSecpol
};

function initSettingsPage() {
  if (!requireAuth()) return;
  applyTheme(S.theme);
  loadSharedComponent('header', () => {
    setProfileSummary();
    bindHeaderActions();
  });
  initSidebar();
  const headerTitle = document.getElementById('page-title');
  if (headerTitle) headerTitle.textContent = 'Settings';
  setTimeout(() => {
    renderRoleUI();
  }, 120);
}

function getCurrentRole() {
  const user = getUserInfo();
  return user ? user.role || 'User' : 'User';
}

function setCurrentRole(role) {
  const user = getUserInfo() || { name: 'Guest', email: '', role };
  user.role = role;
  setUserInfo(user);
  renderRoleUI();
}

function renderRoleUI() {
  const role = getCurrentRole();
  buildSidebarLinks(role);
  renderTabs(role);
  const adminPill = document.getElementById('role-pill-admin');
  const userPill = document.getElementById('role-pill-user');
  if (adminPill && userPill) {
    adminPill.classList.toggle('active', role === 'Admin');
    userPill.classList.toggle('active', role === 'User');
    adminPill.style.background = role === 'Admin' ? '#185FA5' : 'transparent';
    adminPill.style.color = role === 'Admin' ? 'white' : 'inherit';
    userPill.style.background = role === 'User' ? '#185FA5' : 'transparent';
    userPill.style.color = role === 'User' ? 'white' : 'inherit';
    const avatar = document.getElementById('avatar-circle');
    const u = getUserInfo();
    if (avatar) avatar.textContent = (u && u.name) ? u.name.split(' ').map((s) => s[0]).slice(0, 2).join('') : 'SM';
  }
}

function renderTabs(role) {
  const tabsBar = document.querySelector('.tabs-bar');
  if (!tabsBar) return;
  const tabs = [{ key: 'my-account', label: 'My Account' }];
  if (role === 'User') tabs.push({ key: 'user-settings', label: 'User Settings' });
  if (role === 'Admin') tabs.push({ key: 'admin-settings', label: 'Admin Settings <span class="badge-amber">Admin only</span>' });
  tabsBar.innerHTML = tabs.map((t) => `<button class="tab-pill" data-tab="${t.key}">${t.label}</button>`).join('');
  const defaultTab = document.querySelector('.tab-pill[data-tab="my-account"]');
  if (defaultTab) {
    defaultTab.classList.add('active');
    renderSubnavFor('my-account', role);
  }
  document.querySelectorAll('.tab-pill').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-pill').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      renderSubnavFor(btn.dataset.tab, role);
    });
  });
}

function renderSubnavFor(tabKey, role) {
  const subnav = document.getElementById('settings-subnav');
  const content = document.getElementById('settings-content');
  if (!subnav || !content) return;
  subnav.innerHTML = '';
  content.innerHTML = '';
  let items = [];
  if (tabKey === 'my-account') {
    items = [
      { label: 'Profile', key: 'profile' },
      { label: 'Security', key: 'security' },
      { label: 'Notifications', key: 'notifications' },
      { label: 'Preferences', key: 'preferences' }
    ];
  } else if (tabKey === 'user-settings') {
    items = [
      { label: 'Reports & Downloads', key: 'reports' },
      { label: 'File handling', key: 'files' }
    ];
  } else if (tabKey === 'admin-settings') {
    items = [
      { label: 'Conversion rules', key: 'conversion' },
      { label: 'System configuration', key: 'system' },
      { label: 'User management', key: 'usermgmt' },
      { label: 'Logs & monitoring', key: 'logs' },
      { label: 'Security policies', key: 'secpol' }
    ];
  }
  items.forEach((item, idx) => {
    const el = document.createElement('div');
    el.className = 'subnav-item';
    el.dataset.key = item.key;
    el.innerHTML = `<span>${item.label}</span>`;
    if (idx === 0) el.classList.add('active');
    el.addEventListener('click', () => {
      subnav.querySelectorAll('.subnav-item').forEach((s) => s.classList.remove('active'));
      el.classList.add('active');
      renderSubpage(tabKey, item.key, role);
    });
    subnav.appendChild(el);
  });
  if (items.length) renderSubpage(tabKey, items[0].key, role);
}

function renderSubpage(tabKey, pageKey, role) {
  const content = document.getElementById('settings-content');
  if (!content) return;
  const pageFn = pageMap[pageKey];
  content.innerHTML = pageFn ? pageFn() : '';
}

function openPasswordModal() {
  const modal = document.getElementById('password-modal');
  if (modal) {
    modal.classList.remove('hidden');
    document.getElementById('cp_current').value = '';
    document.getElementById('cp_new').value = '';
    document.getElementById('cp_confirm').value = '';
  }
}

function closePasswordModal() {
  const modal = document.getElementById('password-modal');
  if (modal) {
    modal.classList.add('hidden');
  }
}

async function submitPasswordChange(event) {
  event.preventDefault();
  const current = document.getElementById('cp_current').value;
  const newPass = document.getElementById('cp_new').value;
  const confirmPass = document.getElementById('cp_confirm').value;

  if (newPass !== confirmPass) {
    showNotification('New password and confirm password must match', 'danger');
    return;
  }
  if (newPass.length < 6) {
    showNotification('New password must be at least 6 characters', 'danger');
    return;
  }

  try {
    const response = await apiRequest('/auth/change-password', 'POST', {
      current_password: current,
      new_password: newPass
    });
    
    if (response && response.message === 'Password changed successfully.') {
      showNotification('Password changed successfully.', 'success');
      closePasswordModal();
    } else {
      showNotification(response.message || 'Failed to change password.', 'danger');
    }
  } catch (error) {
    showNotification(error.message || 'Failed to change password.', 'danger');
  }
}

async function logoutAllDevices() {
  const confirmed = confirm("Are you sure you want to logout from all devices?");
  if (!confirmed) return;
  try {
    const response = await apiRequest('/auth/logout', 'POST');
    showNotification(response.message || 'Logged out from all devices successfully.', 'success');
  } catch (e) {
    showNotification('Logged out from all devices successfully.', 'success');
  }
  setTimeout(() => {
    clearAuth();
    window.location.href = '../pages/login.html';
  }, 600);
}

window.logoutAllDevices = logoutAllDevices;
window.saveNotifications = saveNotifications;
window.toggleNotifSubgroup = toggleNotifSubgroup;
window.saveReportSettings = saveReportSettings;
window.saveFileHandlingSettings = saveFileHandlingSettings;
window.toggleFileHandlingSubgroup = toggleFileHandlingSubgroup;

