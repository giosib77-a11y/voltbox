import { useCallback, useEffect, useState } from 'react';
import * as api from '../services/api.js';

/**
 * მიწოდების წესები `GET /delivery`-დან — ქალაქები, ტარიფები, უფასოს ზღვარი.
 *
 * ერთი მოთხოვნა სესიაზე: header, მთავარი გვერდი, footer, კალათა და checkout
 * ერთსა და იმავე promise-ს იზიარებენ. ჩავარდნილი promise არ ინახება — შემდეგი
 * გამოძახება (ან `reload`) თავიდან ცდის.
 *
 * ციფრების ასლი frontend-ში არსად არ არის: სანამ წესები არ მოსულა, გვერდები
 * ფასს არ წერენ, რომ ძველი ან გამოგონილი რიცხვი არ აჩვენონ.
 */
let rulesPromise = null;

/** @returns {Promise<{cities:{name:string, fee:number}[], freeFrom:number, currency:string}>} */
export function loadDeliveryRules() {
  if (!rulesPromise) {
    rulesPromise = api.getDeliveryRules().catch((error) => {
      rulesPromise = null;
      throw error;
    });
  }
  return rulesPromise;
}

/** ტესტებისთვის: ყოველ ტესტს საკუთარი პასუხი აქვს. */
export function forgetDeliveryRules() {
  rulesPromise = null;
}

export function useDeliveryRules() {
  const [state, setState] = useState({ rules: null, error: null });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    loadDeliveryRules().then(
      (rules) => !cancelled && setState({ rules, error: null }),
      (error) => !cancelled && setState({ rules: null, error }),
    );
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const reload = useCallback(() => {
    setState({ rules: null, error: null });
    setAttempt((n) => n + 1);
  }, []);

  return { rules: state.rules, error: state.error, loading: !state.rules && !state.error, reload };
}
