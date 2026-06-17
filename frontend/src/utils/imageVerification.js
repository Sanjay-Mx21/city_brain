export function imageVerificationLabel(complaint) {
  const status = complaint?.image_verification_status;
  if (!status) return 'No image verification';
  if (status === 'verified') return 'Image verified';
  if (status === 'needs_review') return 'Image needs review';
  if (status === 'rejected') return 'Image rejected';
  return status.replace(/_/g, ' ');
}

export function imageVerificationClass(complaint) {
  const status = complaint?.image_verification_status;
  if (status === 'verified') return 'bg-green-100 text-green-700';
  if (status === 'needs_review') return 'bg-orange-100 text-orange-700';
  if (status === 'rejected') return 'bg-red-100 text-red-700';
  return 'bg-slate-100 text-slate-600';
}
