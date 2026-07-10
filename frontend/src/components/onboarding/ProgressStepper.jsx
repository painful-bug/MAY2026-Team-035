import React from 'react';

export default function ProgressStepper({ currentStep, totalSteps }) {
  return (
    <div className="space-y-3" aria-label={`Step ${currentStep} of ${totalSteps}`}>
      <div className="flex items-center justify-between gap-4">
        <span className="text-[11px] font-extrabold uppercase tracking-widest text-indigo-600">
          Step {currentStep} of {totalSteps}
        </span>
        <span className="text-[11px] font-bold text-slate-400">
          {Math.round((currentStep / totalSteps) * 100)}% complete
        </span>
      </div>

      <div className="flex gap-2" aria-hidden="true">
        {Array.from({ length: totalSteps }, (_, index) => (
          <span
            key={index}
            className={`h-1.5 flex-1 rounded-full transition-colors duration-300 ${
              index < currentStep ? 'bg-indigo-600' : 'bg-slate-100'
            }`}
          />
        ))}
      </div>
    </div>
  );
}
