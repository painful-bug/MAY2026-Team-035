import React from 'react';

const normalizeClickCoordinates = (event) => {
  const bounds = event.currentTarget.getBoundingClientRect();
  const clamp = (value) => Math.min(100, Math.max(0, value));

  return {
    x: Number(
      clamp(((event.clientX - bounds.left) / bounds.width) * 100).toFixed(4)
    ),
    y: Number(
      clamp(((event.clientY - bounds.top) / bounds.height) * 100).toFixed(4)
    ),
  };
};

export default function MapCard({ imageSrc, onMapClick, children }) {
  const handleClick = (event) => {
    onMapClick(normalizeClickCoordinates(event));
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-label="Simulated community map. Click to place a marker."
      className="relative block min-h-[420px] w-full cursor-crosshair overflow-hidden rounded-2xl border border-slate-200 bg-slate-100 text-left shadow-inner focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2 lg:min-h-[520px]"
    >
      <img
        src={imageSrc}
        alt="Fictional residential neighborhood map"
        draggable="false"
        className="absolute inset-0 h-full w-full select-none object-cover"
      />
      <span className="absolute inset-0 bg-slate-900/5" aria-hidden="true" />
      {children}
    </button>
  );
}
