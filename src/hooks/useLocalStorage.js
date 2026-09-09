import { useCallback, useEffect, useRef, useState } from 'react';
import { readJSON, writeJSON } from '../utils/storage.js';

/**
 * localStorage-თან სინქრონიზებული state.
 * სხვა tab-ში ცვლილება ავტომატურად აისახება (`storage` event).
 */
export function useLocalStorage(key, initialValue) {
  const [value, setValue] = useState(() => readJSON(key, initialValue));
  const keyRef = useRef(key);
  keyRef.current = key;

  useEffect(() => {
    writeJSON(key, value);
  }, [key, value]);

  useEffect(() => {
    function handleStorage(event) {
      if (event.key !== keyRef.current) return;
      setValue(readJSON(keyRef.current, initialValue));
    }
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
    // initialValue-ს განზრახ არ ვაკვირდებით — ის მხოლოდ fallback-ია
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const reset = useCallback(() => setValue(initialValue), [initialValue]);

  return [value, setValue, reset];
}

export default useLocalStorage;
