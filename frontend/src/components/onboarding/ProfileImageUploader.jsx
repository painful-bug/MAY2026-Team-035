import React, { useRef } from 'react';
import { Camera, ImagePlus, Trash2 } from 'lucide-react';
import { getProfileInitials } from '../../utils/adminProfile';

export default function ProfileImageUploader({
  fullName,
  profileImage,
  onImageChange,
}) {
  const inputRef = useRef(null);

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];

    if (!file || !file.type.startsWith('image/')) {
      return;
    }

    const reader = new FileReader();
    reader.addEventListener('load', () => {
      onImageChange(String(reader.result));
    });
    reader.readAsDataURL(file);
  };

  const handleRemove = () => {
    onImageChange('');
    if (inputRef.current) {
      inputRef.current.value = '';
    }
  };

  return (
    <div className="flex flex-col items-center gap-5 text-center sm:flex-row sm:text-left">
      <div className="relative">
        <div className="flex h-28 w-28 items-center justify-center overflow-hidden rounded-full border-4 border-white bg-indigo-100 text-2xl font-extrabold text-indigo-700 shadow-lg shadow-indigo-100">
          {profileImage ? (
            <img
              src={profileImage}
              alt="Administrator profile preview"
              className="h-full w-full object-cover"
            />
          ) : (
            <span>{getProfileInitials(fullName)}</span>
          )}
        </div>
        <span className="absolute bottom-0 right-0 flex h-9 w-9 items-center justify-center rounded-full border-2 border-white bg-indigo-600 text-white shadow-md">
          <Camera className="h-4 w-4" />
        </span>
      </div>

      <div className="space-y-3">
        <p className="text-xs font-medium text-slate-500">
          Preview an image locally. Nothing will be uploaded yet.
        </p>

        <div className="flex flex-wrap justify-center gap-2 sm:justify-start">
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            className="sr-only"
            id="admin-profile-image"
          />
          <label
            htmlFor="admin-profile-image"
            className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-sm transition-colors hover:bg-indigo-700"
          >
            <ImagePlus className="h-4 w-4" />
            Choose Image
          </label>

          {profileImage && (
            <button
              type="button"
              onClick={handleRemove}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-500 transition-colors hover:border-rose-200 hover:text-rose-600"
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
