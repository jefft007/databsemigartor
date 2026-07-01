(function initTheme() {
  try {
    const stored = localStorage.getItem('sqlMigratorSettings');
    let theme = 'System';
    if (stored) {
      const parsed = JSON.parse(stored);
      if (parsed.theme) theme = parsed.theme;
    }
    
    if (theme === 'Dark') {
      document.body.classList.remove('light-theme');
    } else if (theme === 'Light') {
      document.body.classList.add('light-theme');
    } else {
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
        document.body.classList.add('light-theme');
      } else {
        document.body.classList.remove('light-theme');
      }
    }
  } catch (e) {
    console.warn('Failed to parse settings for theme', e);
  }
})();

function loadSharedComponent(componentName, callback) {
  return fetch(`../components/${componentName}.html`)
    .then((response) => response.text())
    .then((html) => {
      const container = document.getElementById(`${componentName}-container`);
      if (container) {
        container.innerHTML = html;
        if (typeof callback === 'function') callback();
      }
    })
    .catch(() => {
      console.warn(`Unable to load ${componentName} component.`);
    });
}

function showNotification(message, type = 'success') {
  const notice = document.createElement('div');
  notice.className = `notification notification-${type}`;
  notice.textContent = message;
  document.body.appendChild(notice);
  setTimeout(() => notice.classList.add('visible'), 10);
  setTimeout(() => notice.classList.remove('visible'), 3200);
  setTimeout(() => notice.remove(), 3600);
}

function navigateToPage(path) {
  window.location.href = path;
}

function isLoggedIn() {
  return Boolean(getAuthToken());
}

function requireAuth() {
  const user = getUserInfo();
  if (!isLoggedIn() || !user) {
    window.location.href = '../pages/login.html';
    return false;
  }
  return true;
}

function requireAdmin() {
  const user = getUserInfo();
  if (!isLoggedIn() || !user) {
    window.location.href = '../pages/login.html';
    return false;
  }
  if (String(user.role).toLowerCase() !== 'admin') {
    window.location.href = '../pages/dashboard.html';
    return false;
  }
  return true;
}

function buildSidebarLinks(role) {
  const nav = document.querySelector('.sidebar-nav');
  if (!nav) return;
  const adminLinks = [
    { label: 'Dashboard', path: '../pages/admin_dashboard.html', icon: '🏠' },
    { label: 'Migration', path: '../pages/migration.html', icon: '🔄' },
    { label: 'Users', path: '../pages/users.html', icon: '👥' },
    { label: 'Migration History', path: '../pages/migration_history.html', icon: '📜' },
    { label: 'Reports', path: '../pages/reports.html', icon: '📊' },
    { label: 'Settings', path: '../pages/settings.html', icon: '⚙️' },
  ];
  const userLinks = [
    { label: 'Dashboard', path: '../pages/dashboard.html', icon: '🏠' },
    { label: 'Migration', path: '../pages/migration.html', icon: '🔄' },
    { label: 'Migration History', path: '../pages/migration_history.html', icon: '📜' },
    { label: 'Reports', path: '../pages/reports.html', icon: '📊' },
    { label: 'About', path: '../pages/about.html', icon: 'ℹ️' },
    { label: 'Settings', path: '../pages/settings.html', icon: '⚙️' },
  ];
  const links = String(role).toLowerCase() === 'admin' ? adminLinks : userLinks;
  nav.innerHTML = links
    .map((item) => `
      <a href="${item.path}" class="sidebar-link" data-path="${item.path}">
        <span class="icon">${item.icon}</span>
        <span class="link-text">${item.label}</span>
      </a>
    `)
    .join('');

  highlightSidebarLink();
}

function highlightSidebarLink() {
  const currentPath = location.pathname;
  document.querySelectorAll('.sidebar-nav a').forEach((link) => {
    const targetPath = link.dataset.path;
    if (currentPath.endsWith(targetPath)) {
      link.classList.add('active');
    }
  });
}

function bindHeaderActions() {
  const profileButton = document.getElementById('profile-button');
  const profileMenu = document.getElementById('profile-menu');
  const themeToggle = document.getElementById('theme-toggle');
  const menuButton = document.getElementById('mobile-menu-button');
  const sidebar = document.querySelector('.sidebar');
  if (profileButton && profileMenu) {
    profileButton.addEventListener('click', () => profileMenu.classList.toggle('open'));
    document.addEventListener('click', (event) => {
      if (!profileButton.contains(event.target) && !profileMenu.contains(event.target)) {
        profileMenu.classList.remove('open');
      }
    });
  }
  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const isLight = document.body.classList.toggle('light-theme');
      
      // Update saved theme if possible
      try {
        const stored = localStorage.getItem('sqlMigratorSettings');
        if (stored) {
          const parsed = JSON.parse(stored);
          parsed.theme = isLight ? 'Light' : 'Dark';
          localStorage.setItem('sqlMigratorSettings', JSON.stringify(parsed));
        }
      } catch(e) {}
      
      showNotification('Theme updated', 'success');
    });
  }
  if (menuButton && sidebar) {
    menuButton.addEventListener('click', () => sidebar.classList.toggle('open'));
  }
}

function bindLogout() {
  const logout = document.getElementById('logout-link');
  if (!logout) return;
  logout.addEventListener('click', (event) => {
    event.preventDefault();
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    window.location.href = '../pages/login.html';
  });
}

function setProfileSummary() {
  const user = getUserInfo();
  if (!user) return;
  const profileName = document.querySelector('.profile-name');
  const profileRole = document.querySelector('.profile-role');
  if (profileName) profileName.textContent = user.name || 'Guest';
  if (profileRole) profileRole.textContent = user.role || 'User';
}

function mapDatabaseOptions() {
  return [
    { value: 'mysql', label: 'MySQL' },
    { value: 'postgres', label: 'PostgreSQL' },
    { value: 'oracle', label: 'Oracle' },
    { value: 'sqlite', label: 'SQLite' },
    { value: 'sqlserver', label: 'SQL Server' },
  ];
}

function injectDatabaseOptions(elementId) {
  const select = document.getElementById(elementId);
  if (!select) return;
  select.innerHTML = mapDatabaseOptions()
    .map((item) => `<option value="${item.value}">${item.label}</option>`)
    .join('');
}
