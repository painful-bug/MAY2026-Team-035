import { useEffect, useRef } from 'react';

const siteKey = import.meta.env.VITE_TURNSTILE_SITE_KEY;

/** Optional Cloudflare Turnstile transport. Supabase validates its token. */
export default function TurnstileChallenge({ onToken }) {
  const node = useRef(null);
  useEffect(() => {
    if (!siteKey || !node.current) return undefined;
    let widgetId; let cancelled = false;
    const render = () => {
      if (cancelled || !window.turnstile || widgetId !== undefined) return;
      widgetId = window.turnstile.render(node.current, {
        sitekey: siteKey,
        callback: onToken,
        'expired-callback': () => onToken(''),
        'error-callback': () => onToken(''),
      });
    };
    const existing = document.querySelector('script[data-homebandhu-turnstile]');
    if (existing) { existing.addEventListener('load', render); render(); }
    else {
      const script = document.createElement('script');
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      script.async = true; script.defer = true; script.dataset.homebandhuTurnstile = 'true'; script.addEventListener('load', render); document.head.appendChild(script);
    }
    return () => { cancelled = true; if (widgetId !== undefined && window.turnstile) window.turnstile.remove(widgetId); };
  }, [onToken]);
  return siteKey ? <div ref={node} className="flex justify-center" /> : null;
}
