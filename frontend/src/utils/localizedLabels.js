const STATUS_LABELS = {
  en: {
    pending: 'Pending',
    assigned: 'Assigned',
    in_progress: 'In Progress',
    resolved: 'Resolved',
    escalated: 'Escalated',
    closed: 'Closed',
  },
  hi: {
    pending: 'लंबित',
    assigned: 'सौंपा गया',
    in_progress: 'कार्य जारी',
    resolved: 'समाधान',
    escalated: 'बढ़ाया गया',
    closed: 'बंद',
  },
  kn: {
    pending: 'ಬಾಕಿ',
    assigned: 'ನಿಯೋಜಿಸಲಾಗಿದೆ',
    in_progress: 'ಪ್ರಗತಿಯಲ್ಲಿದೆ',
    resolved: 'ಪರಿಹಾರವಾಗಿದೆ',
    escalated: 'ಹೆಚ್ಚಿಸಲಾಗಿದೆ',
    closed: 'ಮುಚ್ಚಲಾಗಿದೆ',
  },
};

export function statusLabel(status, language = 'en') {
  const labels = STATUS_LABELS[language] || STATUS_LABELS.en;
  return labels[status] || status?.replace(/_/g, ' ') || 'Unknown';
}
