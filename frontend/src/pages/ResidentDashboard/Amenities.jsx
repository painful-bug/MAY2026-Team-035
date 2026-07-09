import React, { useState } from 'react';
import { useApp } from '../../store/useApp';
import { Calendar, Clock, Users, CalendarDays, CheckCircle, Plus } from 'lucide-react';

export default function Amenities() {
  const { amenities, bookings, currentUser, bookAmenity, searchQuery } = useApp();
  
  const [amenityId, setAmenityId] = useState('a1');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [timeSlot, setTimeSlot] = useState('07:00 AM - 08:30 AM');

  const userBookings = bookings.filter(b => b.userId === currentUser?.id);

  const filteredAmenitiesCatalog = amenities.filter(a => 
    a.name.toLowerCase().includes((searchQuery || '').toLowerCase()) ||
    (a.description && a.description.toLowerCase().includes((searchQuery || '').toLowerCase()))
  );

  const selectedAmenity = amenities.find(a => a.id === amenityId);
  const isMaintenance = selectedAmenity?.status === 'Under Maintenance';

  const handleSubmit = (e) => {
    e.preventDefault();
    if (isMaintenance) return;
    bookAmenity({ amenityId, date, timeSlot });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Amenities Booking</h1>
        <p className="text-xs font-semibold text-slate-400 mt-1">Reserve society assets like the Gym, Swimming Pool, Banquet Hall, or Tennis Courts.</p>
      </div>

      {/* Facilities Catalog */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {filteredAmenitiesCatalog.map((am) => (
          <div key={am.id} className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm space-y-4 flex flex-col justify-between hover:shadow-md transition-shadow">
            <div className="space-y-2">
              <span className={`text-[10px] font-extrabold px-2.5 py-1 rounded-lg uppercase tracking-wider inline-block border ${
                am.status === 'Under Maintenance'
                  ? 'bg-rose-50 border-rose-100 text-rose-650'
                  : 'bg-slate-50 border-slate-100 text-slate-500'
              }`}>
                {am.status}
              </span>
              <h3 className="text-base font-extrabold text-slate-805">{am.name}</h3>
              <p className="text-xs text-slate-450 leading-relaxed font-semibold">{am.description}</p>
            </div>

            <div className="pt-3 border-t border-slate-50 space-y-2 text-xs font-bold text-slate-500">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-indigo-500" />
                <span>{am.timing}</span>
              </div>
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-indigo-500" />
                <span>Max Capacity: {am.capacity} people</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Booking Form and Logs */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Book slot Form */}
        <div className="lg:col-span-4 bg-white p-6 border border-slate-100 rounded-2xl h-fit space-y-4 shadow-sm">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-50">
            <Calendar className="w-5 h-5 text-indigo-650" />
            <h3 className="font-extrabold text-slate-855 text-sm">Reserve a Slot</h3>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Choose Amenity</label>
              <select
                value={amenityId}
                onChange={(e) => setAmenityId(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
              >
                {amenities.map(a => (
                  <option key={a.id} value={a.id} disabled={a.status === 'Under Maintenance'}>
                    {a.name} {a.status === 'Under Maintenance' ? '(Under Maintenance)' : ''}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Date</label>
                <input
                  type="date"
                  required
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Time Slot</label>
                <select
                  value={timeSlot}
                  onChange={(e) => setTimeSlot(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                >
                  <option value="07:00 AM - 08:30 AM">07:00 AM - 08:30 AM</option>
                  <option value="09:00 AM - 10:30 AM">09:00 AM - 10:30 AM</option>
                  <option value="04:00 PM - 05:30 PM">04:00 PM - 05:30 PM</option>
                  <option value="06:00 PM - 07:30 PM">06:00 PM - 07:30 PM</option>
                  <option value="08:00 PM - 09:30 PM">08:00 PM - 09:30 PM</option>
                </select>
              </div>
            </div>

            <button
              type="submit"
              disabled={isMaintenance}
              className={`w-full py-2.5 text-white font-bold rounded-xl transition-all text-xs flex items-center justify-center gap-1.5 ${
                isMaintenance 
                  ? 'bg-slate-300 cursor-not-allowed shadow-none' 
                  : 'bg-indigo-600 hover:bg-indigo-700 shadow-md shadow-indigo-100'
              }`}
            >
              <Plus className="w-4 h-4" />
              {isMaintenance ? 'Under Maintenance' : 'Book Selected Slot'}
            </button>
          </form>
        </div>

        {/* Bookings log */}
        <div className="lg:col-span-8 bg-white border border-slate-100 rounded-2xl shadow-sm overflow-hidden flex flex-col justify-between">
          <div className="p-6 border-b border-slate-50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CalendarDays className="w-5 h-5 text-indigo-650" />
              <h3 className="font-extrabold text-slate-800 text-sm">Your Upcoming Bookings</h3>
            </div>
            <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-50 px-2.5 py-1 border border-slate-100 rounded-lg text-slate-450">
              {userBookings.length} Bookings
            </span>
          </div>

          <div className="overflow-x-auto flex-1">
            {userBookings.length === 0 ? (
              <div className="text-center py-12 text-xs text-slate-400 font-semibold">
                You have no active slot reservations.
              </div>
            ) : (
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50/55 border-b border-slate-100 text-[10px] font-extrabold text-slate-400 uppercase tracking-wider">
                    <th className="px-6 py-3.5">Facility</th>
                    <th className="px-6 py-3.5">Reserved Date</th>
                    <th className="px-6 py-3.5">Time Slot</th>
                    <th className="px-6 py-3.5">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50 text-xs font-semibold text-slate-600">
                  {userBookings.map((bk) => (
                    <tr key={bk.id} className="hover:bg-slate-55/30 transition-colors">
                      <td className="px-6 py-4 font-bold text-slate-850">{bk.amenityName}</td>
                      <td className="px-6 py-4">{bk.date}</td>
                      <td className="px-6 py-4 font-mono text-indigo-755">{bk.timeSlot}</td>
                      <td className="px-6 py-4">
                        <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-100 px-2 py-0.5 rounded-full flex items-center gap-1 w-fit">
                          <CheckCircle className="w-3 h-3 text-emerald-600" />
                          {bk.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
