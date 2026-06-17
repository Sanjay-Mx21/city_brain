export const SLA_STYLES = {
  overdue: 'bg-red-100 text-red-700',
  due_soon: 'bg-orange-100 text-orange-700',
  on_track: 'bg-green-100 text-green-700',
  met: 'bg-green-100 text-green-700',
  missed: 'bg-red-100 text-red-700',
};

export function formatSlaStatus(complaint) {
  const status = complaint?.sla_status;
  const hours = complaint?.sla_hours_remaining;

  if (!status) return 'SLA N/A';
  if (status === 'met') return 'SLA Met';
  if (status === 'missed') return 'SLA Missed';
  if (status === 'overdue') return `Overdue by ${formatHours(Math.abs(hours))}`;
  if (status === 'due_soon') return `Due in ${formatHours(hours)}`;
  return `SLA ${formatHours(hours)} left`;
}

export function getSlaClass(complaint) {
  return SLA_STYLES[complaint?.sla_status] || 'bg-slate-100 text-slate-600';
}

function formatHours(value) {
  if (value == null) return '';
  if (value < 24) return `${Math.max(0, Math.round(value))}h`;
  return `${Math.round(value / 24)}d`;
}
