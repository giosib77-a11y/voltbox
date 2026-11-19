import { useId } from 'react';
import { CONTACT, INFO_PAGES } from '../../constants/index.js';
import { t } from '../../i18n/index.js';
import Rich from '../../i18n/Rich.jsx';
import InfoPage, { InfoSection } from './InfoPage.jsx';
import { ContactInline } from './Contact.jsx';

/** A line of the sample withdrawal notice, each its own i18n key. */
const FORM_LINES = ['formStatement', 'formOrder', 'formReceived', 'formName', 'formDate'];

/**
 * დაბრუნება და გარანტია.
 *
 * What the page says follows the Georgian consumer law: 14 calendar days to
 * withdraw without a reason (the product may be inspected as in a shop, and the
 * packaging is only a request), the only exception the sealed hygiene product,
 * and the legal 2-year guarantee next to the manufacturer's warranty.
 */
export default function ReturnsWarranty() {
  const stepsId = useId();
  const form = [
    t('info.returns.formTo', { email: CONTACT.email }),
    ...FORM_LINES.map((line) => t(`info.returns.${line}`)),
  ].join('\n');

  return (
    <InfoPage page={INFO_PAGES.returns} description={t('info.returns.description')}>
      <InfoSection title={t('info.returns.refundTitle')}>
        <p>{t('info.returns.refundIntro')}</p>

        <p>{t('info.returns.inspection')}</p>

        <p>{t('info.returns.packagingRequest')}</p>

        <p>
          <strong className="font-semibold text-ink-900">{t('info.returns.exceptionLabel')}</strong>{' '}
          {t('info.returns.exceptionText')}
        </p>

        <p id={stepsId} className="font-semibold text-ink-900">
          {t('info.returns.steps')}
        </p>
        <ol aria-labelledby={stepsId} className="list-decimal space-y-1.5 pl-5 marker:text-primary-700">
          <li>
            <Rich k="info.returns.stepContact" values={{ contact: <ContactInline /> }} />
          </li>
          <li>{t('info.returns.stepPickup')}</li>
          <li>{t('info.returns.stepSend')}</li>
          <li>{t('info.returns.stepRefund')}</li>
        </ol>

        <p>{t('info.returns.refundIncludes')}</p>

        <p>{t('info.returns.refundMethod')}</p>

        <p>{t('info.returns.returnShipping')}</p>

        <p>
          <strong className="font-semibold text-ink-900">{t('info.returns.damagedLabel')}</strong>{' '}
          {t('info.returns.damagedText')}
        </p>
      </InfoSection>

      <InfoSection title={t('info.returns.formTitle')}>
        <p>{t('info.returns.formIntro')}</p>
        {/* Plain selectable text, so it can be copied into an email as it is. */}
        <pre
          className="whitespace-pre-wrap break-words rounded-card border border-line bg-ink-100 px-4 py-3 font-sans text-sm leading-relaxed text-ink-900"
        >
          {form}
        </pre>
      </InfoSection>

      <InfoSection title={t('info.returns.warrantyTitle')}>
        <p>{t('info.returns.defective')}</p>

        <p>{t('info.returns.defectRemedy')}</p>

        <p>{t('info.returns.manufacturerWarranty')}</p>

        <p>{t('info.returns.warrantyExclusions')}</p>
      </InfoSection>
    </InfoPage>
  );
}
