import React, { useId, useRef } from 'react';
import { ImagePlus, Trash2 } from 'lucide-react';

export default function AmenityImagePicker({ image, onSelect, onRemove }) {
  const inputId = useId();
  const inputRef = useRef(null);

  const handleImageChange = (event) => {
    onSelect(event.target.files?.[0]);
  };

  const handleRemove = () => {
    onRemove();
    if (inputRef.current) {
      inputRef.current.value = '';
    }
  };

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-dashed border-slate-200 bg-slate-50 p-4 sm:flex-row sm:items-center">
      {image ? (
        <img
          src={image}
          alt="Amenity preview"
          className="h-24 w-full rounded-xl object-cover sm:w-36"
        />
      ) : (
        <div className="flex h-24 w-full items-center justify-center rounded-xl bg-slate-100 text-slate-400 sm:w-36">
          <ImagePlus className="h-6 w-6" />
        </div>
      )}

      <div className="space-y-2">
        <p className="text-xs font-medium text-slate-400">
          This image will be shown with the amenity after it is saved.
        </p>
        <div className="flex flex-wrap gap-2">
          <input
            ref={inputRef}
            id={inputId}
            type="file"
            accept="image/*"
            onChange={handleImageChange}
            className="sr-only"
          />
          <label
            htmlFor={inputId}
            className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 transition-colors hover:border-indigo-200 hover:text-indigo-600"
          >
            <ImagePlus className="h-4 w-4" />
            Choose Image
          </label>
          {image && (
            <button
              type="button"
              onClick={handleRemove}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-500 transition-colors hover:border-rose-200 hover:text-rose-600"
            >
              <Trash2 className="h-4 w-4" />
              Remove
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
