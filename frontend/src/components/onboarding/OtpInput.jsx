import React, { useRef } from 'react';

const OTP_LENGTH = 6;

export default function OtpInput({ value, onChange, hasError = false }) {
  const inputRefs = useRef([]);

  const updateDigits = (startIndex, inputValue) => {
    const incomingDigits = inputValue.replace(/\D/g, '');
    const digits = value.padEnd(OTP_LENGTH, ' ').split('');

    if (!incomingDigits) {
      digits[startIndex] = ' ';
      onChange(digits.join('').replace(/ /g, '').slice(0, OTP_LENGTH));
      return;
    }

    incomingDigits
      .slice(0, OTP_LENGTH - startIndex)
      .split('')
      .forEach((digit, offset) => {
        digits[startIndex + offset] = digit;
      });

    const nextValue = digits.join('').replace(/ /g, '').slice(0, OTP_LENGTH);
    onChange(nextValue);
    inputRefs.current[
      Math.min(startIndex + incomingDigits.length, OTP_LENGTH - 1)
    ]?.focus();
  };

  const handleKeyDown = (event, index) => {
    if (event.key === 'Backspace') {
      event.preventDefault();
      const digits = value.split('');

      if (digits[index]) {
        digits.splice(index, 1);
        onChange(digits.join(''));
        inputRefs.current[index]?.focus();
      } else if (index > 0) {
        digits.splice(index - 1, 1);
        onChange(digits.join(''));
        inputRefs.current[index - 1]?.focus();
      }
    }

    if (event.key === 'ArrowLeft' && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }

    if (event.key === 'ArrowRight' && index < OTP_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handlePaste = (event) => {
    event.preventDefault();
    const pastedDigits = event.clipboardData
      .getData('text')
      .replace(/\D/g, '')
      .slice(0, OTP_LENGTH);

    onChange(pastedDigits);
    inputRefs.current[Math.min(pastedDigits.length, OTP_LENGTH - 1)]?.focus();
  };

  return (
    <div className="flex justify-center gap-2 sm:gap-3" onPaste={handlePaste}>
      {Array.from({ length: OTP_LENGTH }, (_, index) => (
        <input
          key={index}
          ref={(element) => {
            inputRefs.current[index] = element;
          }}
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          maxLength={OTP_LENGTH}
          autoComplete={index === 0 ? 'one-time-code' : 'off'}
          autoFocus={index === 0}
          value={value[index] ?? ''}
          onChange={(event) => updateDigits(index, event.target.value)}
          onKeyDown={(event) => handleKeyDown(event, index)}
          onFocus={(event) => event.target.select()}
          aria-label={`OTP digit ${index + 1}`}
          className={`h-12 w-10 rounded-xl border bg-white text-center text-lg font-extrabold text-slate-800 outline-none transition-all focus:ring-2 focus:ring-indigo-100 sm:h-14 sm:w-12 ${
            hasError
              ? 'border-rose-300 focus:border-rose-400'
              : 'border-slate-200 focus:border-indigo-500'
          }`}
        />
      ))}
    </div>
  );
}
