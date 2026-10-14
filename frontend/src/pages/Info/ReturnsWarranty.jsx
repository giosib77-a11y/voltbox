import { useId } from 'react';
import { INFO_PAGES, SHOP_FACTS } from '../../constants/index.js';
import { t } from '../../i18n/index.js';
import Rich from '../../i18n/Rich.jsx';
import InfoPage, { InfoSection } from './InfoPage.jsx';
import { ContactInline } from './Contact.jsx';

/** დაბრუნება და გარანტია. */
export default function ReturnsWarranty() {
  const { returnPickup, warrantyPeriod } = SHOP_FACTS;
  const conditionsId = useId();
  const stepsId = useId();

  return (
    <InfoPage page={INFO_PAGES.returns} description={t('info.returns.description')}>
      <InfoSection title={t('info.returns.refundTitle')}>
        <p>{t('info.returns.refundIntro')}</p>

        <p id={conditionsId} className="font-semibold text-ink-900">
          {t('info.returns.conditions')}
        </p>
        <ul aria-labelledby={conditionsId} className="list-disc space-y-1.5 pl-5">
          <li>{t('info.returns.conditionUnused')}</li>
          <li>{t('info.returns.conditionPackaging')}</li>
        </ul>

        <p>
          <strong className="font-semibold text-ink-900">{t('info.returns.exceptionLabel')}</strong>{' '}
          {t('info.returns.exceptionText')}
        </p>

        <p id={stepsId} className="font-semibold text-ink-900">
          {t('info.returns.steps')}
        </p>
        <ol aria-labelledby={stepsId} className="list-decimal space-y-1.5 pl-5">
          <li>
            <Rich k="info.returns.stepContact" values={{ contact: <ContactInline /> }} />
          </li>
          {returnPickup && <li>{returnPickup}</li>}
          <li>{t('info.returns.stepRefund')}</li>
        </ol>

        <p>{t('info.returns.returnShipping')}</p>

        <p>{t('info.returns.cashRefund')}</p>
      </InfoSection>

      <InfoSection title={t('info.returns.warrantyTitle')}>
        <p>{t('info.returns.defective')}</p>

        {warrantyPeriod && <p>{t('info.returns.warrantyPeriod', { period: warrantyPeriod })}</p>}

        <p>{t('info.returns.warrantyExclusions')}</p>
      </InfoSection>
    </InfoPage>
  );
}
