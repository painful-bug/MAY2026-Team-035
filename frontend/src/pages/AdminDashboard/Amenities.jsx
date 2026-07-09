import React, { useState } from 'react';
import { useApp } from '../../store/useApp';
import { Calendar, Plus, Trash2, Clock, Users, X, Edit2, Pause } from 'lucide-react';

export default function AdminAmenities() {
  const { amenities, addAmenity, deleteAmenity, editAmenity, toggleAmenityHold } = useApp();
  const [modalOpen, setModalOpen] = useState(false);
  
  // Add Form state
  const [name, setName] = useState('');
  const [timing, setTiming] = useState('06:00 AM - 10:00 PM');
  const [capacity, setCapacity] = useState('50');
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');

  // Edit Form state
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingFacility, setEditingFacility] = useState(null);
  const [editName, setEditName] = useState('');
  const [editTiming, setEditTiming] = useState('06:00 AM - 10:00 PM');
  const [editCapacity, setEditCapacity] = useState('50');
  const [editDescription, setEditDescription] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Please enter a facility name.');
      return;
    }
    
    addAmenity({
      name,
      timing,
      capacity: Number(capacity),
      description
    });

    // Reset Form
    setName('');
    setTiming('06:00 AM - 10:00 PM');
    setCapacity('50');
    setDescription('');
    setError('');
    setModalOpen(false);
  };

  const handleStartEdit = (facility) => {
    setEditingFacility(facility);
    setEditName(facility.name);
    setEditTiming(facility.timing);
    setEditCapacity(facility.capacity.toString());
    setEditDescription(facility.description);
    setEditModalOpen(true);
  };

  const handleEditSubmit = (e) => {
    e.preventDefault();
    if (!editName.trim()) {
      return;
    }
    
    editAmenity(editingFacility.id, {
      name: editName,
      timing: editTiming,
      capacity: Number(editCapacity),
      description: editDescription
    });

    setEditModalOpen(false);
    setEditingFacility(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Amenities Management</h1>
          <p className="text-xs font-semibold text-slate-400 mt-1">Add, edit, delete, or place hold on common areas and facilities inside the society gates.</p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-4 py-2.5 rounded-xl transition-all shadow-md shadow-indigo-100 flex items-center gap-1.5 self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          Add Amenity
        </button>
      </div>

      {/* Grid List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {amenities.map((facility) => (
          <div key={facility.id} className="bg-white border border-slate-100 rounded-3xl p-6 shadow-sm flex flex-col justify-between hover:shadow-md transition-all relative overflow-hidden group">
            {/* Header info */}
            <div className="space-y-3">
              <div className="flex justify-between items-start gap-4">
                <div className="flex items-center gap-2">
                  <div className="p-3 bg-indigo-50 text-indigo-655 rounded-2xl">
                    <Calendar className="w-5 h-5" />
                  </div>
                  {facility.status === 'Under Maintenance' && (
                    <span className="text-[9px] font-extrabold px-2 py-0.5 bg-rose-50 border border-rose-100 text-rose-600 rounded-lg uppercase tracking-wider">
                      On Hold / Maintenance
                    </span>
                  )}
                </div>
                
                <div className="flex items-center gap-1">
                  {/* Hold/Unhold button */}
                  <button
                    onClick={() => toggleAmenityHold(facility.id)}
                    className={`p-2 rounded-xl transition-colors ${
                      facility.status === 'Under Maintenance'
                        ? 'bg-rose-100 text-rose-600'
                        : 'text-slate-400 hover:bg-amber-50 hover:text-amber-600'
                    }`}
                    title={facility.status === 'Under Maintenance' ? 'Activate facility' : 'Put facility on Hold'}
                  >
                    <Pause className="w-4 h-4" />
                  </button>

                  {/* Edit button */}
                  <button
                    onClick={() => handleStartEdit(facility)}
                    className="p-2 text-slate-400 hover:bg-indigo-50 hover:text-indigo-600 rounded-xl transition-colors"
                    title="Edit facility"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>

                  {/* Delete button */}
                  <button
                    onClick={() => deleteAmenity(facility.id)}
                    className="p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600 rounded-xl transition-colors"
                    title="Delete facility"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="space-y-1">
                <h3 className="text-sm font-extrabold text-slate-800 tracking-tight">{facility.name}</h3>
                <p className="text-[11px] text-slate-455 font-semibold leading-relaxed line-clamp-2">{facility.description}</p>
              </div>
            </div>

            {/* Bottom details */}
            <div className="mt-6 pt-4 border-t border-slate-50 flex items-center justify-between text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-indigo-500" />
                {facility.timing}
              </span>
              <span className="flex items-center gap-1">
                <Users className="w-3.5 h-3.5 text-indigo-500" />
                Cap: {facility.capacity}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Add Amenity Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in">
          <div className="bg-white border border-slate-100 rounded-3xl w-full max-w-md p-6 shadow-2xl relative animate-scale-up">
            <button
              onClick={() => setModalOpen(false)}
              className="absolute top-4 right-4 p-1.5 text-slate-400 hover:bg-slate-50 rounded-xl transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-base font-extrabold text-slate-900 tracking-tight mb-4">Add Society Facility</h3>

            {error && (
              <div className="mb-4 bg-rose-50 text-rose-805 text-xs font-semibold p-3 rounded-xl text-center border border-rose-100">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4 text-xs font-semibold text-slate-650">
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Facility Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                    setError('');
                  }}
                  placeholder="e.g. Badminton Court, Swimming Pool"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Operational Hours</label>
                  <input
                    type="text"
                    value={timing}
                    onChange={(e) => setTiming(e.target.value)}
                    placeholder="e.g. 06:00 AM - 10:00 PM"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Slot Capacity</label>
                  <input
                    type="number"
                    value={capacity}
                    onChange={(e) => setCapacity(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Facility Description</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Rules, location inside society, or reservation guidelines..."
                  rows={3}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold resize-none"
                />
              </div>

              <div className="pt-2 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2.5 border border-slate-200 hover:bg-slate-50 text-slate-705 text-xs font-bold rounded-xl transition-all"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-755 text-white text-xs font-bold rounded-xl transition-all shadow-md shadow-indigo-100"
                >
                  Confirm Facility
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Amenity Modal */}
      {editModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in">
          <div className="bg-white border border-slate-100 rounded-3xl w-full max-w-md p-6 shadow-2xl relative animate-scale-up">
            <button
              onClick={() => setEditModalOpen(false)}
              className="absolute top-4 right-4 p-1.5 text-slate-400 hover:bg-slate-50 rounded-xl transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-base font-extrabold text-slate-900 tracking-tight mb-4">Edit Society Facility</h3>

            <form onSubmit={handleEditSubmit} className="space-y-4 text-xs font-semibold text-slate-650">
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Facility Name</label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  placeholder="e.g. Badminton Court, Swimming Pool"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Operational Hours</label>
                  <input
                    type="text"
                    value={editTiming}
                    onChange={(e) => setEditTiming(e.target.value)}
                    placeholder="e.g. 06:00 AM - 10:00 PM"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Slot Capacity</label>
                  <input
                    type="number"
                    value={editCapacity}
                    onChange={(e) => setEditCapacity(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Facility Description</label>
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  placeholder="Rules, location inside society, or reservation guidelines..."
                  rows={3}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold resize-none"
                />
              </div>

              <div className="pt-2 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setEditModalOpen(false)}
                  className="px-4 py-2.5 border border-slate-200 hover:bg-slate-50 text-slate-705 text-xs font-bold rounded-xl transition-all"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-755 text-white text-xs font-bold rounded-xl transition-all shadow-md shadow-indigo-100"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
