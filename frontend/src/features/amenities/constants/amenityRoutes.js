export const AMENITIES_ADMIN_PATH = '/admin/amenities';
export const AMENITIES_REPORTS_PATH = `${AMENITIES_ADMIN_PATH}/reports`;

export const AMENITY_DETAIL_TABS = [
  { label: 'Dashboard', segment: '', end: true },
  { label: 'Approvals', segment: 'approvals' },
  { label: 'Ledger', segment: 'ledger' },
  { label: 'Settings', segment: 'settings' },
];

export const getAmenityDetailPath = (amenityId) =>
  `${AMENITIES_ADMIN_PATH}/${encodeURIComponent(amenityId)}`;

export const getAmenityTabPath = (amenityId, segment) => {
  const detailPath = getAmenityDetailPath(amenityId);
  return segment ? `${detailPath}/${segment}` : detailPath;
};
