export function dashboardPathForRole(role) {
  if (role === 'admin') return '/admin';
  if (role === 'officer') return '/officer';
  return '/';
}

export function goToDashboardForUser(user) {
  window.location.replace(dashboardPathForRole(user?.role));
}
