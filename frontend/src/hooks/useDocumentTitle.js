import { useEffect } from 'react';
import { SITE_NAME } from '../constants/index.js';

/**
 * გვერდის სათაურის დინამიური დაყენება.
 * @param {string} title — თუ ცარიელია, რჩება მხოლოდ საიტის სახელი
 */
export function useDocumentTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} · ${SITE_NAME}` : `${SITE_NAME} — ელექტრონიკის აქსესუარები`;
  }, [title]);
}

export default useDocumentTitle;
